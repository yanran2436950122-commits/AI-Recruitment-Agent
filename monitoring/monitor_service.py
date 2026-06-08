"""Observability V1 监控服务与节点装饰器。"""

import json
import time
import traceback
import zipfile
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List
from uuid import uuid4
from xml.sax.saxutils import escape

from app.config import BASE_DIR
from monitoring.local_telemetry_provider import LocalTelemetryProvider
from monitoring.telemetry_provider import TelemetryProvider


CURRENT_RUN_ID: ContextVar[str] = ContextVar("current_run_id", default="")
"""当前执行上下文中的 run_id，供 LLM/RAG 指标复用。"""

CURRENT_ANALYSIS_ID: ContextVar[str] = ContextVar("current_analysis_id", default="")
"""当前执行上下文中的 analysis_id。"""

RUN_START_TIMES: Dict[str, float] = {}
"""运行开始时间缓存，用于计算 duration_ms。"""


class MonitorService:
    """统一可观测性服务，封装 Run Log、Node Log、Error Trace 和导出。"""

    def __init__(self, provider: TelemetryProvider = None) -> None:
        """初始化监控服务，默认使用本地 SQLite Provider。"""

        self.provider = provider or LocalTelemetryProvider()
        self.docs_dir = BASE_DIR / "docs"
        self.exports_dir = BASE_DIR / "exports"
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def start_run(self, actor_type: str, workflow_name: str, analysis_id: str = "") -> str:
        """开始记录一次工作流运行并返回 run_id。"""

        run_id = f"run_{uuid4().hex}"
        now = utc_now()
        RUN_START_TIMES[run_id] = time.perf_counter()
        CURRENT_RUN_ID.set(run_id)
        CURRENT_ANALYSIS_ID.set(analysis_id or "")
        self.provider.record_run(
            {
                "run_id": run_id,
                "analysis_id": analysis_id or "",
                "actor_type": actor_type,
                "workflow_name": workflow_name,
                "start_time": now,
                "end_time": "",
                "duration_ms": 0,
                "status": "running",
                "created_at": now,
            }
        )
        self.record_metric("total_runs_started", 1, {"actor_type": actor_type, "workflow_name": workflow_name})
        return run_id

    def end_run(self, run_id: str, status: str, analysis_id: str = "", actor_type: str = "", workflow_name: str = "") -> None:
        """结束一次工作流运行并更新 run_logs。"""

        start = RUN_START_TIMES.pop(run_id, time.perf_counter())
        duration_ms = round((time.perf_counter() - start) * 1000, 3)
        now = utc_now()
        if analysis_id:
            CURRENT_ANALYSIS_ID.set(analysis_id)
        self.provider.record_run(
            {
                "run_id": run_id,
                "analysis_id": analysis_id or CURRENT_ANALYSIS_ID.get(),
                "actor_type": actor_type,
                "workflow_name": workflow_name,
                "start_time": "",
                "end_time": now,
                "duration_ms": duration_ms,
                "status": status,
                "created_at": now,
            }
        )
        self.record_metric(f"run_{status}", 1, {"actor_type": actor_type, "workflow_name": workflow_name})

    def log_node_execution(
        self,
        run_id: str,
        analysis_id: str,
        node_name: str,
        start_time: str,
        end_time: str,
        duration_ms: float,
        status: str,
        input_size: int,
        output_size: int,
    ) -> None:
        """记录一次节点执行。"""

        self.provider.record_node(
            {
                "run_id": run_id,
                "analysis_id": analysis_id,
                "node_name": node_name,
                "start_time": start_time,
                "end_time": end_time,
                "duration_ms": duration_ms,
                "status": status,
                "input_size": input_size,
                "output_size": output_size,
            }
        )

    def log_error(
        self,
        run_id: str = "",
        analysis_id: str = "",
        node_name: str = "",
        error_type: str = "",
        error_message: str = "",
        stack_trace: str = "",
    ) -> str:
        """记录异常追踪并返回 error_id。"""

        error_id = f"error_{uuid4().hex}"
        self.provider.record_error(
            {
                "error_id": error_id,
                "run_id": run_id or CURRENT_RUN_ID.get(),
                "analysis_id": analysis_id or CURRENT_ANALYSIS_ID.get(),
                "node_name": node_name,
                "error_type": error_type or "ApplicationError",
                "error_message": error_message,
                "stack_trace": stack_trace,
                "created_at": utc_now(),
            }
        )
        self.record_metric("error_trace_created", 1, {"node_name": node_name, "error_type": error_type})
        return error_id

    def record_metric(self, metric_name: str, metric_value: float, labels: Dict[str, Any] = None) -> None:
        """记录一个通用指标点。"""

        self.provider.record_metric(
            {
                "metric_id": f"metric_{uuid4().hex}",
                "metric_name": metric_name,
                "metric_value": float(metric_value),
                "labels": json.dumps(labels or {}, ensure_ascii=False),
                "created_at": utc_now(),
            }
        )

    def record_rag_metric(
        self,
        retrieval_count: int,
        retrieval_hit_count: int,
        retrieval_time_ms: float,
        run_id: str = "",
        analysis_id: str = "",
    ) -> None:
        """记录 RAG 检索次数、命中次数和耗时。"""

        miss_count = max(int(retrieval_count) - int(retrieval_hit_count), 0)
        provider = self.provider
        if hasattr(provider, "record_rag_metric"):
            provider.record_rag_metric(
                {
                    "metric_id": f"rag_{uuid4().hex}",
                    "run_id": run_id or CURRENT_RUN_ID.get(),
                    "analysis_id": analysis_id or CURRENT_ANALYSIS_ID.get(),
                    "retrieval_count": int(retrieval_count),
                    "retrieval_hit_count": int(retrieval_hit_count),
                    "retrieval_miss_count": miss_count,
                    "retrieval_time_ms": round(float(retrieval_time_ms), 3),
                    "created_at": utc_now(),
                }
            )

    def record_llm_metric(
        self,
        success: bool,
        response_time_ms: float,
        fallback: bool = False,
        run_id: str = "",
        analysis_id: str = "",
    ) -> None:
        """记录 LLM 调用成功、失败、耗时和降级次数。"""

        provider = self.provider
        if hasattr(provider, "record_llm_metric"):
            provider.record_llm_metric(
                {
                    "metric_id": f"llm_{uuid4().hex}",
                    "run_id": run_id or CURRENT_RUN_ID.get(),
                    "analysis_id": analysis_id or CURRENT_ANALYSIS_ID.get(),
                    "llm_calls": 1,
                    "llm_failures": 0 if success else 1,
                    "response_time_ms": round(float(response_time_ms), 3),
                    "fallback_calls": 1 if fallback else 0,
                    "created_at": utc_now(),
                }
            )

    def get_run_summary(self) -> Dict[str, Any]:
        """返回监控中心总览指标。"""

        if hasattr(self.provider, "summary"):
            return self.provider.summary()
        return {}

    def get_recent_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """读取最近 Run Log。"""

        return self.provider.fetch_rows("run_logs", limit=limit)

    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """读取最近 Error Trace。"""

        return self.provider.fetch_rows("error_traces", limit=limit)

    def get_analysis_detail(self, analysis_id: str) -> Dict[str, Any]:
        """读取指定 analysis_id 的运行详情、节点时间线和异常。"""

        if not hasattr(self.provider, "fetch_run"):
            return {}
        run = self.provider.fetch_run(analysis_id)
        nodes = self.provider.fetch_nodes(analysis_id=analysis_id)
        errors = self.provider.fetch_errors(analysis_id=analysis_id)
        return {"run": run, "nodes": nodes, "errors": errors}

    def export_excel(self) -> Dict[str, str]:
        """导出 run_logs、error_traces 和 analysis_records 为 Excel 文件。"""

        paths = {
            "run_logs": self.exports_dir / "run_logs.xlsx",
            "error_traces": self.exports_dir / "error_traces.xlsx",
            "analysis_records": self.exports_dir / "analysis_records.xlsx",
        }
        write_xlsx(paths["run_logs"], self.provider.fetch_rows("run_logs", limit=10000))
        write_xlsx(paths["error_traces"], self.provider.fetch_rows("error_traces", limit=10000))
        write_xlsx(paths["analysis_records"], self._load_analysis_records_for_export())
        return {name: str(path) for name, path in paths.items()}

    def append_running_diary(
        self,
        problem: str,
        root_cause: str,
        fix_solution: str,
        verification_result: str,
    ) -> Path:
        """自动追加运行日记。"""

        path = self.docs_dir / "RUNNING_LOG.md"
        ensure_markdown_header(path, "# Running Log\n")
        entry = (
            f"\n## {datetime.now().date()}\n\n"
            f"- 问题：{problem}\n"
            f"- 根因：{root_cause}\n"
            f"- 修复方案：{fix_solution}\n"
            f"- 验证结果：{verification_result}\n"
        )
        path.write_text(path.read_text(encoding="utf-8") + entry, encoding="utf-8")
        return path

    def append_bug_report(
        self,
        bug_id: str,
        title: str,
        symptom: str,
        root_cause: str,
        fix_solution: str,
        status: str,
    ) -> Path:
        """自动追加 BUG 追踪记录。"""

        path = self.docs_dir / "BUG_REPORT.md"
        ensure_markdown_header(path, "# Bug Report\n")
        entry = (
            f"\n## {bug_id} - {title}\n\n"
            f"- 现象：{symptom}\n"
            f"- 根因：{root_cause}\n"
            f"- 修复方案：{fix_solution}\n"
            f"- 状态：{status}\n"
        )
        path.write_text(path.read_text(encoding="utf-8") + entry, encoding="utf-8")
        return path

    def _load_analysis_records_for_export(self) -> List[Dict[str, Any]]:
        """从既有长期记忆导出分析记录，避免 Excel 成为主存储。"""

        try:
            from memory.postgres_memory import PostgresMemory

            return PostgresMemory().get_analysis_records(limit=10000)
        except Exception:
            return []


def monitor_node(node_name: str) -> Callable:
    """为 LangGraph 节点生成监控装饰器。"""

    def decorator(func: Callable) -> Callable:
        """包装节点函数并自动记录 Node Log 与 Error Trace。"""

        def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
            """执行被监控节点并记录耗时、状态和异常。"""

            service = get_monitor_service()
            run_id = state.get("run_id") or CURRENT_RUN_ID.get()
            analysis_id = state.get("analysis_id") or CURRENT_ANALYSIS_ID.get()
            input_size = safe_json_size(state)
            start_perf = time.perf_counter()
            start_time = utc_now()
            try:
                result = func(state)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start_perf) * 1000, 3)
                service.log_node_execution(
                    run_id=run_id,
                    analysis_id=analysis_id,
                    node_name=node_name,
                    start_time=start_time,
                    end_time=utc_now(),
                    duration_ms=duration_ms,
                    status="failed",
                    input_size=input_size,
                    output_size=0,
                )
                service.log_error(
                    run_id=run_id,
                    analysis_id=analysis_id,
                    node_name=node_name,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    stack_trace=traceback.format_exc(),
                )
                raise
            duration_ms = round((time.perf_counter() - start_perf) * 1000, 3)
            result_analysis_id = result.get("analysis_id") or analysis_id
            if result_analysis_id:
                CURRENT_ANALYSIS_ID.set(result_analysis_id)
            status = "failed" if result.get("error") else "success"
            service.log_node_execution(
                run_id=result.get("run_id") or run_id,
                analysis_id=result_analysis_id,
                node_name=node_name,
                start_time=start_time,
                end_time=utc_now(),
                duration_ms=duration_ms,
                status=status,
                input_size=input_size,
                output_size=safe_json_size(result),
            )
            if result.get("error"):
                service.log_error(
                    run_id=result.get("run_id") or run_id,
                    analysis_id=result_analysis_id,
                    node_name=node_name,
                    error_type="NodeError",
                    error_message=str(result.get("error")),
                    stack_trace="",
                )
            record_rag_metric_if_needed(service, node_name, result, duration_ms)
            return result

        return wrapper

    return decorator


def record_rag_metric_if_needed(
    service: MonitorService,
    node_name: str,
    state: Dict[str, Any],
    duration_ms: float,
) -> None:
    """对 RAG 检索节点补充 RAG Metrics。"""

    if not node_name.startswith("Retrieve"):
        return
    docs = state.get("retrieved_docs") or []
    service.record_rag_metric(
        retrieval_count=1,
        retrieval_hit_count=1 if docs else 0,
        retrieval_time_ms=duration_ms,
        run_id=state.get("run_id", ""),
        analysis_id=state.get("analysis_id", ""),
    )


def get_monitor_service() -> MonitorService:
    """返回进程内共享的监控服务实例。"""

    global _MONITOR_SERVICE
    try:
        return _MONITOR_SERVICE
    except NameError:
        _MONITOR_SERVICE = MonitorService()
        return _MONITOR_SERVICE


def utc_now() -> str:
    """返回 UTC ISO 时间字符串。"""

    return datetime.now(timezone.utc).isoformat()


def safe_json_size(value: Any) -> int:
    """计算对象 JSON 序列化后的字节长度，失败时降级为字符串长度。"""

    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    return len(text.encode("utf-8"))


def ensure_markdown_header(path: Path, header: str) -> None:
    """确保 Markdown 文件存在且包含标题。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(header, encoding="utf-8")


def write_xlsx(path: Path, rows: List[Dict[str, Any]]) -> None:
    """写入一个无需第三方依赖的简单 XLSX 文件。"""

    headers = sorted({key for row in rows for key in row.keys()}) if rows else ["empty"]
    sheet_xml = build_sheet_xml(headers, rows)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", XLSX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", XLSX_RELS)
        archive.writestr("xl/workbook.xml", XLSX_WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", XLSX_WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def build_sheet_xml(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    """构造 XLSX sheet XML。"""

    xml_rows = [build_xlsx_row(1, headers)]
    for index, row in enumerate(rows, start=2):
        xml_rows.append(build_xlsx_row(index, [row.get(header, "") for header in headers]))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )


def build_xlsx_row(row_index: int, values: List[Any]) -> str:
    """构造 XLSX 单行 XML。"""

    cells = []
    for column_index, value in enumerate(values, start=1):
        cell_ref = f"{column_name(column_index)}{row_index}"
        text = escape(str(value if value is not None else ""))
        cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
    return f'<row r="{row_index}">{"".join(cells)}</row>'


def column_name(index: int) -> str:
    """把列序号转换为 Excel 列名。"""

    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
"""XLSX 内容类型定义。"""

XLSX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
"""XLSX 根关系定义。"""

XLSX_WORKBOOK = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
"""XLSX 工作簿定义。"""

XLSX_WORKBOOK_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
"""XLSX 工作簿关系定义。"""
