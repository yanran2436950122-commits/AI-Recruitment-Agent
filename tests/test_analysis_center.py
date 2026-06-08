"""历史分析中心的多租户隔离、记录生命周期和审计日志测试。"""

from pathlib import Path

from agents.hr_manager_agent import HRManagerAgent
from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService


RESUME_TEXT = (
    "Candidate: History User\n"
    "Skills: Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker, Chroma, Milvus.\n"
    "Project: Built AI recruitment workflows, analysis records, scoring trace, and memory isolation.\n"
    "Impact: Improved hiring analysis consistency and report replay quality.\n"
)

JD_TEXT = "Need AI Agent Engineer with Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker."


def test_candidate_history_center_only_returns_own_records(tmp_path: Path, monkeypatch) -> None:
    """Candidate 历史中心只能读取自己的分析记录。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    resume = write_resume(tmp_path, "candidate_history.txt", RESUME_TEXT)
    role_a = service.create_candidate_target_role("candidate_history_a", "AI Agent 工程师")
    role_b = service.create_candidate_target_role("candidate_history_b", "RAG 工程师")

    result_a = ManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="candidate_history.txt",
        jd_text=JD_TEXT,
        candidate_id="candidate_history_a",
        session_id="candidate_history_session_a",
        target_role_id=role_a["target_role_id"],
        role_name=role_a["role_name"],
    )
    result_b = ManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="candidate_history.txt",
        jd_text=JD_TEXT + " Chroma Milvus",
        candidate_id="candidate_history_b",
        session_id="candidate_history_session_b",
        target_role_id=role_b["target_role_id"],
        role_name=role_b["role_name"],
    )

    own_records = service.list_analysis_records(
        actor_type="candidate",
        candidate_id="candidate_history_a",
        page_size=20,
    )["records"]
    own_ids = {record["analysis_id"] for record in own_records}
    assert result_a["analysis_id"] in own_ids
    assert result_b["analysis_id"] not in own_ids


def test_hr_history_center_isolated_by_company(tmp_path: Path, monkeypatch) -> None:
    """HR 历史中心只能读取当前企业的候选人评估记录。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    resume = write_resume(tmp_path, "hr_history.txt", RESUME_TEXT)
    job_a = service.create_job_profile("company_history_a", "AI Agent 工程师", JD_TEXT)
    job_b = service.create_job_profile("company_history_b", "AI Agent 工程师", JD_TEXT)

    result_a = HRManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="hr_history.txt",
        jd_text="",
        company_id="company_history_a",
        job_id=job_a["job_id"],
        session_id="hr_history_session_a",
    )
    result_b = HRManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="hr_history.txt",
        jd_text="",
        company_id="company_history_b",
        job_id=job_b["job_id"],
        session_id="hr_history_session_b",
    )

    company_a_records = service.list_analysis_records(
        actor_type="hr",
        company_id="company_history_a",
        page_size=20,
    )["records"]
    company_a_ids = {record["analysis_id"] for record in company_a_records}
    assert result_a["analysis_id"] in company_a_ids
    assert result_b["analysis_id"] not in company_a_ids


def test_analysis_record_lifecycle_and_audit_logs(tmp_path: Path, monkeypatch) -> None:
    """同一 resume_hash 可产生多个 analysis_id，查看和删除会写入审计日志。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    resume = write_resume(tmp_path, "same_resume.txt", RESUME_TEXT)
    role = service.create_candidate_target_role("candidate_lifecycle", "AI Agent 工程师")
    first = ManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="same_resume.txt",
        jd_text=JD_TEXT,
        candidate_id="candidate_lifecycle",
        session_id="candidate_lifecycle_session",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    second = ManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="same_resume.txt",
        jd_text=JD_TEXT + " Milvus",
        candidate_id="candidate_lifecycle",
        session_id="candidate_lifecycle_session",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert first["resume_hash"] == second["resume_hash"]
    assert first["analysis_id"] != second["analysis_id"]

    detail = service.get_analysis_record(
        analysis_id=first["analysis_id"],
        actor_type="candidate",
        candidate_id="candidate_lifecycle",
        action_user_id="candidate_lifecycle",
    )
    assert detail["report_content"]

    deleted = service.delete_analysis_record(
        analysis_id=first["analysis_id"],
        actor_type="candidate",
        candidate_id="candidate_lifecycle",
        action_user_id="candidate_lifecycle",
    )
    assert deleted is True
    assert not service.get_analysis_record(
        analysis_id=first["analysis_id"],
        actor_type="candidate",
        candidate_id="candidate_lifecycle",
        action_user_id="candidate_lifecycle",
    )

    logs = service.get_audit_logs(actor_type="candidate", candidate_id="candidate_lifecycle")
    actions = {log["action"] for log in logs}
    assert {"view_report", "delete_record"}.issubset(actions)


def write_resume(tmp_path: Path, filename: str, text: str) -> Path:
    """写入测试简历文件并返回路径。"""

    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path
