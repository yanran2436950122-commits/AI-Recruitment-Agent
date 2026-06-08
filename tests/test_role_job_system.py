"""岗位体系、目标岗位、JD 版本和跨租户隔离测试。"""

from pathlib import Path

from agents.hr_manager_agent import HRManagerAgent
from agents.manager_agent import ManagerAgent
from memory.redis_memory import RedisMemory
from memory.tenant_memory_service import TenantMemoryService


RESUME_TEXT = (
    "Candidate: Role Job User\n"
    "Skills: Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker, Chroma, Milvus.\n"
    "Project: Built recruitment agent platform with job management and analysis center.\n"
    "Impact: Improved hiring workflow consistency and tenant isolation.\n"
)

JD_AI = "Need AI Agent Engineer with Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker."
JD_RAG = "Need RAG Engineer with Python, LangGraph, RAG, Chroma, Milvus, PostgreSQL."


def test_hr_requires_job_before_screening(tmp_path: Path, monkeypatch) -> None:
    """没有 job_id 时，HR workflow 必须拒绝运行。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    resume = write_resume(tmp_path)

    state = HRManagerAgent().run(
        resume_file_path=str(resume),
        jd_text="",
        company_id="company_requires_job",
        job_id="",
        session_id="hr_requires_job_session",
    )

    assert state["error"] == "请先创建或选择岗位。"


def test_hr_selected_job_loads_jd(tmp_path: Path, monkeypatch) -> None:
    """HR 选择岗位后，workflow 必须使用 job_profile.jd_text。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    job = service.create_job_profile("company_loads_jd", "RAG 工程师", JD_RAG)
    resume = write_resume(tmp_path)

    state = HRManagerAgent().run(
        resume_file_path=str(resume),
        jd_text="this temporary jd must be ignored",
        company_id="company_loads_jd",
        job_id=job["job_id"],
        session_id="hr_loads_jd_session",
    )

    assert state["jd_text"] == JD_RAG
    assert state["jd_snapshot"] == JD_RAG
    assert state["job_name"] == "RAG 工程师"


def test_company_can_have_multiple_jobs() -> None:
    """同一个 company_id 下可以创建多个 job_profile。"""

    service = TenantMemoryService()
    service.create_job_profile("company_multi_jobs", "AI Agent 工程师", JD_AI)
    service.create_job_profile("company_multi_jobs", "RAG 工程师", JD_RAG)

    jobs = service.list_job_profiles("company_multi_jobs")

    assert {job["job_name"] for job in jobs}.issuperset({"AI Agent 工程师", "RAG 工程师"})


def test_hr_analysis_records_include_job(tmp_path: Path, monkeypatch) -> None:
    """HR analysis_record 必须包含 job_id、job_name、jd_version、jd_snapshot。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    job = service.create_job_profile("company_record_job", "AI Agent 工程师", JD_AI)
    resume = write_resume(tmp_path)

    state = HRManagerAgent().run(
        resume_file_path=str(resume),
        jd_text="",
        company_id="company_record_job",
        job_id=job["job_id"],
        session_id="hr_record_job_session",
    )
    record = state["analysis_record"]

    assert record["job_id"] == job["job_id"]
    assert record["job_name"] == "AI Agent 工程师"
    assert record["jd_version"] == 1
    assert record["jd_snapshot"] == JD_AI


def test_candidate_can_have_multiple_target_roles() -> None:
    """同一个 candidate_id 下可以创建多个 target_role。"""

    service = TenantMemoryService()
    service.create_candidate_target_role("candidate_multi_roles", "AI Agent 工程师")
    service.create_candidate_target_role("candidate_multi_roles", "Python 后端工程师")

    roles = service.list_candidate_target_roles("candidate_multi_roles")

    assert {role["role_name"] for role in roles}.issuperset({"AI Agent 工程师", "Python 后端工程师"})


def test_candidate_jd_snapshot_saved_per_analysis(tmp_path: Path, monkeypatch) -> None:
    """Candidate 每次输入 JD 后，analysis_record 必须保存本次 jd_snapshot。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    role = service.create_candidate_target_role("candidate_jd_snapshot", "AI Agent 工程师")
    resume = write_resume(tmp_path)

    state = ManagerAgent().run(
        resume_file_path=str(resume),
        jd_text=JD_AI,
        candidate_id="candidate_jd_snapshot",
        session_id="candidate_jd_snapshot_session",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert state["analysis_record"]["target_role_id"] == role["target_role_id"]
    assert state["analysis_record"]["role_name"] == role["role_name"]
    assert state["analysis_record"]["jd_snapshot"] == JD_AI


def test_candidate_target_role_does_not_bind_jd() -> None:
    """target_role 不应该固定绑定 jd_text。"""

    role = TenantMemoryService().create_candidate_target_role(
        "candidate_role_no_jd",
        "AI Agent 工程师",
        "求职方向，不是企业 JD。",
    )

    assert "jd_text" not in role


def test_cross_tenant_job_access_forbidden() -> None:
    """CompanyA 不能访问 CompanyB 的 job_profiles。"""

    service = TenantMemoryService()
    job = service.create_job_profile("company_a_forbidden", "AI Agent 工程师", JD_AI)

    assert not service.get_job_profile("company_b_forbidden", job["job_id"])


def test_cross_tenant_analysis_access_forbidden(tmp_path: Path, monkeypatch) -> None:
    """CandidateA 不能访问 CandidateB，CompanyA 不能访问 CompanyB 的 analysis_records。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    resume = write_resume(tmp_path)
    role = service.create_candidate_target_role("candidate_forbidden_a", "AI Agent 工程师")
    candidate_state = ManagerAgent().run(
        resume_file_path=str(resume),
        jd_text=JD_AI,
        candidate_id="candidate_forbidden_a",
        session_id="candidate_forbidden_session",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    job = service.create_job_profile("company_forbidden_a", "AI Agent 工程师", JD_AI)
    hr_state = HRManagerAgent().run(
        resume_file_path=str(resume),
        jd_text="",
        company_id="company_forbidden_a",
        job_id=job["job_id"],
        session_id="hr_forbidden_session",
    )

    assert not service.get_analysis_record(
        candidate_state["analysis_id"],
        actor_type="candidate",
        candidate_id="candidate_forbidden_b",
    )
    assert not service.get_analysis_record(
        hr_state["analysis_id"],
        actor_type="hr",
        company_id="company_forbidden_b",
    )


def test_session_does_not_store_business_result(tmp_path: Path, monkeypatch) -> None:
    """Session Memory 不得保存 resume_info、score、report 等业务结果。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    service = TenantMemoryService()
    role = service.create_candidate_target_role("candidate_session_clean", "AI Agent 工程师")
    resume = write_resume(tmp_path)
    session_id = "session_clean_role_job"
    ManagerAgent().run(
        resume_file_path=str(resume),
        jd_text=JD_AI,
        candidate_id="candidate_session_clean",
        session_id=session_id,
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    session_memory = RedisMemory().get_session(session_id) or {}

    forbidden_keys = {
        "resume_text",
        "resume_info",
        "jd_text",
        "match_score",
        "match_reason",
        "missing_skills",
        "report_content",
        "optimized_resume",
    }
    assert not forbidden_keys.intersection(session_memory)


def write_resume(tmp_path: Path) -> Path:
    """写入测试简历文件并返回路径。"""

    path = tmp_path / "role_job_resume.txt"
    path.write_text(RESUME_TEXT, encoding="utf-8")
    return path
