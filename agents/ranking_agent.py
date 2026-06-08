"""候选人排序智能体：为 HR 侧流程生成排序理由。"""

from graph.state import AgentState


class RankingAgent:
    """负责基于匹配分和企业偏好生成排序信息的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """生成单候选人排序摘要，后续可扩展为多候选人排序。"""

        base_score = float(state.get("base_match_score") or 0)
        hr_adjusted_score = float(state.get("hr_adjusted_score") or base_score)
        risk_factors = state.get("hr_risk_factors") or []
        strategy = ((state.get("company_memory") or {}).get("profile") or {}).get(
            "hiring_strategy",
            "综合匹配",
        )
        reason = (
            f"基础匹配分为 {base_score}，HR 风险调整分为 {hr_adjusted_score}，"
            f"企业招聘策略为 {strategy}，风险因素：{', '.join(risk_factors) if risk_factors else '暂无'}。"
        )
        return {**state, "ranking_result": reason, "error": None}
