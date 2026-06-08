"""Candidate 与 HR 基础评分一致性测试。"""

from pathlib import Path

from agents.hr_manager_agent import HRManagerAgent
from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService


def test_candidate_and_hr_base_score_consistency(tmp_path: Path) -> None:
    """同一份简历和 JD 在 Candidate 与 HR 工作流中必须产生相同基础分。"""

    resume = tmp_path / "resume.txt"
    resume.write_text(
        "候选人: 王五\n技能: Python FastAPI LangGraph RAG Redis PostgreSQL\n"
        "项目: 企业招聘 Agent 平台，负责 RAG 检索、API 开发和数据存储。",
        encoding="utf-8",
    )
    jd_text = "招聘 AI Agent 工程师，要求 Python、FastAPI、LangGraph、RAG、Redis 和 PostgreSQL。"
    service = TenantMemoryService()
    role = service.create_candidate_target_role(
        candidate_id="candidate_consistency",
        role_name="AI Agent 工程师",
    )
    job = service.create_job_profile(
        company_id="company_consistency",
        job_name="AI Agent 工程师",
        jd_text=jd_text,
        created_by="company_consistency",
    )

    candidate_result = ManagerAgent().run(
        resume_file_path=str(resume),
        jd_text=jd_text,
        candidate_id="candidate_consistency",
        session_id="candidate_consistency_session",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    hr_result = HRManagerAgent().run(
        resume_file_path=str(resume),
        jd_text="",
        company_id="company_consistency",
        job_id=job["job_id"],
        session_id="hr_consistency_session",
    )

    assert candidate_result["base_match_score"] == hr_result["base_match_score"]
    assert candidate_result["match_score"] == hr_result["match_score"]
    if candidate_result["final_display_score"] != hr_result["final_display_score"]:
        assert "hr_adjusted_score" in hr_result
        assert "hr_risk_factors" in hr_result
    assert candidate_result["scoring_trace"]["source_agent"] == "MatchScoringAgent"
    assert hr_result["scoring_trace"]["source_agent"] == "MatchScoringAgent"
