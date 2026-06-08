"""基于 SQLite 的本地可观测性 Provider。"""

import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from app.config import DATA_DIR
from monitoring.telemetry_provider import TelemetryProvider


APP_DB_PATH = DATA_DIR / "app.db"
"""Observability V1 使用的 SQLite 数据库路径。"""


class LocalTelemetryProvider(TelemetryProvider):
    """使用 data/app.db 保存运行日志、节点日志、错误和指标。"""

    def __init__(self, db_path: Path = APP_DB_PATH) -> None:
        """初始化 SQLite 数据库并确保表结构存在。"""

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def record_run(self, run: Dict[str, Any]) -> None:
        """插入或更新 run_logs。"""

        self._execute(
            """
            INSERT INTO run_logs (
                run_id, analysis_id, actor_type, workflow_name, start_time, end_time,
                duration_ms, status, created_at
            )
            VALUES (
                :run_id, :analysis_id, :actor_type, :workflow_name, :start_time, :end_time,
                :duration_ms, :status, :created_at
            )
            ON CONFLICT(run_id) DO UPDATE SET
                analysis_id=excluded.analysis_id,
                actor_type=excluded.actor_type,
                workflow_name=excluded.workflow_name,
                start_time=COALESCE(NULLIF(excluded.start_time, ''), run_logs.start_time),
                end_time=COALESCE(NULLIF(excluded.end_time, ''), run_logs.end_time),
                duration_ms=excluded.duration_ms,
                status=excluded.status
            """,
            run,
        )

    def record_node(self, node: Dict[str, Any]) -> None:
        """插入 node_logs。"""

        self._execute(
            """
            INSERT INTO node_logs (
                run_id, analysis_id, node_name, start_time, end_time,
                duration_ms, status, input_size, output_size
            )
            VALUES (
                :run_id, :analysis_id, :node_name, :start_time, :end_time,
                :duration_ms, :status, :input_size, :output_size
            )
            """,
            node,
        )

    def record_error(self, error: Dict[str, Any]) -> None:
        """插入 error_traces。"""

        self._execute(
            """
            INSERT INTO error_traces (
                error_id, run_id, analysis_id, node_name, error_type,
                error_message, stack_trace, created_at
            )
            VALUES (
                :error_id, :run_id, :analysis_id, :node_name, :error_type,
                :error_message, :stack_trace, :created_at
            )
            """,
            error,
        )

    def record_metric(self, metric: Dict[str, Any]) -> None:
        """插入 metrics。"""

        self._execute(
            """
            INSERT INTO metrics (
                metric_id, metric_name, metric_value, labels, created_at
            )
            VALUES (
                :metric_id, :metric_name, :metric_value, :labels, :created_at
            )
            """,
            metric,
        )

    def record_rag_metric(self, metric: Dict[str, Any]) -> None:
        """插入 RAG 检索指标。"""

        self._execute(
            """
            INSERT INTO rag_metrics (
                metric_id, run_id, analysis_id, retrieval_count, retrieval_hit_count,
                retrieval_miss_count, retrieval_time_ms, created_at
            )
            VALUES (
                :metric_id, :run_id, :analysis_id, :retrieval_count, :retrieval_hit_count,
                :retrieval_miss_count, :retrieval_time_ms, :created_at
            )
            """,
            metric,
        )

    def record_llm_metric(self, metric: Dict[str, Any]) -> None:
        """插入 LLM 调用指标。"""

        self._execute(
            """
            INSERT INTO llm_metrics (
                metric_id, run_id, analysis_id, llm_calls, llm_failures,
                response_time_ms, fallback_calls, created_at
            )
            VALUES (
                :metric_id, :run_id, :analysis_id, :llm_calls, :llm_failures,
                :response_time_ms, :fallback_calls, :created_at
            )
            """,
            metric,
        )

    def fetch_rows(self, table_name: str, limit: int = 20) -> List[Dict[str, Any]]:
        """读取指定表的最近记录。"""

        if table_name not in self._allowed_tables():
            raise ValueError(f"不支持读取表：{table_name}")
        return self._query(
            f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT ?",
            (int(limit),),
        )

    def fetch_nodes(self, run_id: str = "", analysis_id: str = "") -> List[Dict[str, Any]]:
        """按 run_id 或 analysis_id 读取节点时间线。"""

        if run_id:
            return self._query("SELECT * FROM node_logs WHERE run_id=? ORDER BY rowid ASC", (run_id,))
        if analysis_id:
            return self._query("SELECT * FROM node_logs WHERE analysis_id=? ORDER BY rowid ASC", (analysis_id,))
        return []

    def fetch_errors(self, run_id: str = "", analysis_id: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        """按 run_id 或 analysis_id 读取异常记录。"""

        if run_id:
            return self._query("SELECT * FROM error_traces WHERE run_id=? ORDER BY rowid DESC", (run_id,))
        if analysis_id:
            return self._query("SELECT * FROM error_traces WHERE analysis_id=? ORDER BY rowid DESC", (analysis_id,))
        return self.fetch_rows("error_traces", limit=limit)

    def fetch_run(self, analysis_id: str) -> Dict[str, Any]:
        """按 analysis_id 读取最近一次运行记录。"""

        rows = self._query(
            "SELECT * FROM run_logs WHERE analysis_id=? ORDER BY rowid DESC LIMIT 1",
            (analysis_id,),
        )
        return rows[0] if rows else {}

    def summary(self) -> Dict[str, Any]:
        """聚合运行、节点、RAG 和 LLM 指标摘要。"""

        run_rows = self._query(
            """
            SELECT
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success_runs,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_runs,
                AVG(duration_ms) AS average_duration
            FROM run_logs
            """
        )
        node_rows = self._query(
            """
            SELECT node_name, AVG(duration_ms) AS average_duration, COUNT(*) AS total
            FROM node_logs
            GROUP BY node_name
            ORDER BY average_duration DESC
            """
        )
        rag_rows = self._query(
            """
            SELECT
                COALESCE(SUM(retrieval_count), 0) AS retrieval_count,
                COALESCE(SUM(retrieval_hit_count), 0) AS retrieval_hit_count,
                COALESCE(SUM(retrieval_miss_count), 0) AS retrieval_miss_count,
                AVG(retrieval_time_ms) AS average_retrieval_time
            FROM rag_metrics
            """
        )
        llm_rows = self._query(
            """
            SELECT
                COALESCE(SUM(llm_calls), 0) AS llm_calls,
                COALESCE(SUM(llm_failures), 0) AS llm_failures,
                AVG(response_time_ms) AS average_response_time,
                COALESCE(SUM(fallback_calls), 0) AS fallback_calls
            FROM llm_metrics
            """
        )
        run_summary = run_rows[0] if run_rows else {}
        total_runs = int(run_summary.get("total_runs") or 0)
        success_runs = int(run_summary.get("success_runs") or 0)
        return {
            **run_summary,
            "total_runs": total_runs,
            "success_runs": success_runs,
            "failed_runs": int(run_summary.get("failed_runs") or 0),
            "success_rate": round(success_runs / total_runs * 100, 2) if total_runs else 0.0,
            "average_duration": round(float(run_summary.get("average_duration") or 0), 2),
            "agent_metrics": node_rows,
            "rag_metrics": rag_rows[0] if rag_rows else {},
            "llm_metrics": llm_rows[0] if llm_rows else {},
        }

    def _ensure_schema(self) -> None:
        """创建 Observability V1 所需 SQLite 表。"""

        statements = [
            """
            CREATE TABLE IF NOT EXISTS run_logs (
                run_id TEXT PRIMARY KEY,
                analysis_id TEXT,
                actor_type TEXT,
                workflow_name TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms REAL,
                status TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS node_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                analysis_id TEXT,
                node_name TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms REAL,
                status TEXT,
                input_size INTEGER,
                output_size INTEGER
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS error_traces (
                error_id TEXT PRIMARY KEY,
                run_id TEXT,
                analysis_id TEXT,
                node_name TEXT,
                error_type TEXT,
                error_message TEXT,
                stack_trace TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS metrics (
                metric_id TEXT PRIMARY KEY,
                metric_name TEXT,
                metric_value REAL,
                labels TEXT,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_metrics (
                metric_id TEXT PRIMARY KEY,
                run_id TEXT,
                analysis_id TEXT,
                retrieval_count INTEGER,
                retrieval_hit_count INTEGER,
                retrieval_miss_count INTEGER,
                retrieval_time_ms REAL,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS llm_metrics (
                metric_id TEXT PRIMARY KEY,
                run_id TEXT,
                analysis_id TEXT,
                llm_calls INTEGER,
                llm_failures INTEGER,
                response_time_ms REAL,
                fallback_calls INTEGER,
                created_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_records (
                analysis_id TEXT PRIMARY KEY,
                actor_type TEXT,
                payload TEXT,
                created_at TEXT
            )
            """,
        ]
        with sqlite3.connect(self.db_path) as connection:
            for statement in statements:
                connection.execute(statement)
            connection.commit()

    def _execute(self, sql: str, params: Dict[str, Any]) -> None:
        """执行单条写入 SQL。"""

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(sql, params)
            connection.commit()

    def _query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """执行查询并返回字典列表。"""

        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _allowed_tables(self) -> set:
        """返回 Dashboard 允许读取的表名。"""

        return {
            "run_logs",
            "node_logs",
            "error_traces",
            "metrics",
            "rag_metrics",
            "llm_metrics",
            "analysis_records",
        }
