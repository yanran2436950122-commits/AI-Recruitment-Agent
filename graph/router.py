"""LangGraph 工作流的条件路由规则。"""

from app.config import MATCH_PASS_SCORE, MAX_RETRY_COUNT
from graph.state import AgentState


def route_after_match(state: AgentState) -> str:
    """在匹配智能体执行完成后选择下一个节点。

    匹配分达标时直接进入面试题生成；低分时最多进入三次简历优化与重新匹配；
    达到重试上限后，工作流会基于已收集的信息生成最终报告。
    """

    match_score = float(state.get("base_match_score") or state.get("match_score") or 0)
    retry_count = int(state.get("retry_count") or 0)

    if match_score >= MATCH_PASS_SCORE:
        return "retrieve_interview_context"
    if retry_count < MAX_RETRY_COUNT:
        return "retrieve_resume_examples"
    return "report_agent"
