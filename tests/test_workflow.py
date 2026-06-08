"""招聘分析工作流测试。"""

from pathlib import Path

from graph.router import route_after_match
from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService


def test_route_after_match_passes_to_interview() -> None:
    """匹配分大于等于 70 时应先路由到面试上下文检索节点。"""

    assert route_after_match({"match_score": 70, "retry_count": 0}) == "retrieve_interview_context"


def test_route_after_match_retries_when_low_score() -> None:
    """低分且仍有重试次数时应先路由到优秀简历案例检索节点。"""

    assert route_after_match({"match_score": 40, "retry_count": 2}) == "retrieve_resume_examples"


def test_route_after_match_stops_after_max_retries() -> None:
    """低分且已达到三次重试后应直接路由到报告智能体。"""

    assert route_after_match({"match_score": 40, "retry_count": 3}) == "report_agent"


def test_workflow_returns_final_report(tmp_path: Path) -> None:
    """完整工作流应能为 TXT 简历生成匹配分和最终报告。"""

    resume = tmp_path / "resume.txt"
    resume.write_text(
        "候选人: 张三\n技能: Python FastAPI LangGraph RAG Docker\n项目: AI 招聘系统 API 开发。",
        encoding="utf-8",
    )
    jd_text = "招聘 Python 后端工程师，要求 FastAPI、LangGraph、RAG、Docker 和 API 设计经验。"
    role = TenantMemoryService().create_candidate_target_role(
        candidate_id="workflow_candidate",
        role_name="Python 后端工程师",
    )

    state = ManagerAgent().run(
        resume_file_path=str(resume),
        jd_text=jd_text,
        candidate_id="workflow_candidate",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert state["match_score"] >= 70
    assert state["interview_questions"]
    assert "AI 招聘匹配综合报告" in state["final_report"]
