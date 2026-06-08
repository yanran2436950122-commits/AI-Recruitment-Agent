"""Observability V1 可观测性系统测试。"""

from pathlib import Path

from monitoring.local_telemetry_provider import LocalTelemetryProvider
from monitoring.monitor_service import MonitorService


def test_run_log_created(tmp_path: Path) -> None:
    """start_run 和 end_run 应创建并更新 Run Log。"""

    service = build_test_monitor(tmp_path)
    run_id = service.start_run("candidate", "CandidateWorkflow")
    service.end_run(run_id, "success", analysis_id="analysis_run_log", actor_type="candidate", workflow_name="CandidateWorkflow")

    rows = service.get_recent_runs()

    assert rows
    assert rows[0]["run_id"] == run_id
    assert rows[0]["status"] == "success"


def test_node_log_created(tmp_path: Path) -> None:
    """log_node_execution 应创建 Node Log。"""

    service = build_test_monitor(tmp_path)
    run_id = service.start_run("candidate", "CandidateWorkflow")
    service.log_node_execution(
        run_id=run_id,
        analysis_id="analysis_node_log",
        node_name="ResumeAgent",
        start_time="2026-06-06T00:00:00Z",
        end_time="2026-06-06T00:00:01Z",
        duration_ms=100,
        status="success",
        input_size=10,
        output_size=20,
    )

    nodes = service.provider.fetch_nodes(run_id=run_id)

    assert nodes
    assert nodes[0]["node_name"] == "ResumeAgent"


def test_error_trace_created(tmp_path: Path) -> None:
    """log_error 应创建 Error Trace。"""

    service = build_test_monitor(tmp_path)
    error_id = service.log_error(
        run_id="run_error_trace",
        analysis_id="analysis_error_trace",
        node_name="ResumeAgent",
        error_type="DocxParseError",
        error_message="DOCX 表格解析失败",
        stack_trace="trace",
    )

    errors = service.get_recent_errors()

    assert errors
    assert errors[0]["error_id"] == error_id
    assert errors[0]["error_type"] == "DocxParseError"


def test_metrics_updated(tmp_path: Path) -> None:
    """record_metric、run 统计和成功率应可被汇总。"""

    service = build_test_monitor(tmp_path)
    run_id = service.start_run("hr", "HRWorkflow")
    service.record_metric("custom_metric", 3, {"scope": "test"})
    service.end_run(run_id, "success", analysis_id="analysis_metrics", actor_type="hr", workflow_name="HRWorkflow")

    summary = service.get_run_summary()

    assert summary["total_runs"] == 1
    assert summary["success_runs"] == 1
    assert summary["success_rate"] == 100.0


def test_dashboard_summary(tmp_path: Path) -> None:
    """get_run_summary 应返回 Dashboard 所需字段。"""

    service = build_test_monitor(tmp_path)
    run_id = service.start_run("candidate", "CandidateWorkflow")
    service.log_node_execution(
        run_id=run_id,
        analysis_id="analysis_dashboard",
        node_name="MatchScoringAgent",
        start_time="start",
        end_time="end",
        duration_ms=50,
        status="success",
        input_size=1,
        output_size=2,
    )
    service.record_rag_metric(retrieval_count=1, retrieval_hit_count=0, retrieval_time_ms=12)
    service.record_llm_metric(success=False, response_time_ms=30, fallback=True)
    service.end_run(run_id, "failed", analysis_id="analysis_dashboard", actor_type="candidate", workflow_name="CandidateWorkflow")

    summary = service.get_run_summary()

    assert "agent_metrics" in summary
    assert "rag_metrics" in summary
    assert "llm_metrics" in summary
    assert summary["failed_runs"] == 1


def test_excel_export(tmp_path: Path) -> None:
    """export_excel 应生成三份 XLSX 文件。"""

    service = build_test_monitor(tmp_path)
    service.exports_dir = tmp_path / "exports"
    service.exports_dir.mkdir(parents=True, exist_ok=True)
    run_id = service.start_run("candidate", "CandidateWorkflow")
    service.end_run(run_id, "success", analysis_id="analysis_export", actor_type="candidate", workflow_name="CandidateWorkflow")

    paths = service.export_excel()

    assert set(paths) == {"run_logs", "error_traces", "analysis_records"}
    assert all(Path(path).exists() and Path(path).suffix == ".xlsx" for path in paths.values())


def test_running_diary_append(tmp_path: Path) -> None:
    """append_running_diary 应自动追加运行日记。"""

    service = build_test_monitor(tmp_path)
    service.docs_dir = tmp_path / "docs"
    path = service.append_running_diary(
        problem="测试问题",
        root_cause="测试根因",
        fix_solution="测试修复",
        verification_result="测试通过",
    )

    text = path.read_text(encoding="utf-8")

    assert "测试问题" in text
    assert "测试通过" in text


def test_bug_report_append(tmp_path: Path) -> None:
    """append_bug_report 应自动追加 BUG 追踪记录。"""

    service = build_test_monitor(tmp_path)
    service.docs_dir = tmp_path / "docs"
    path = service.append_bug_report(
        bug_id="BUG-TEST-001",
        title="测试 BUG",
        symptom="测试现象",
        root_cause="测试根因",
        fix_solution="测试修复",
        status="closed",
    )

    text = path.read_text(encoding="utf-8")

    assert "BUG-TEST-001" in text
    assert "closed" in text


def build_test_monitor(tmp_path: Path) -> MonitorService:
    """构造使用临时 SQLite 数据库的监控服务。"""

    return MonitorService(LocalTelemetryProvider(tmp_path / "app.db"))
