"""候选人筛选智能体：基于统一基础分生成 HR 初筛风险评估。"""

from graph.state import AgentState
from llm.client import chat_completion, get_last_llm_error, normalize_string_list, parse_json_object


class CandidateScreeningAgent:
    """负责 HR 侧风险调整和初筛解释，不解析文件也不计算基础分。"""

    def run(self, state: AgentState) -> AgentState:
        """读取统一基础分并生成 HR 风险调整分。"""

        base_score = float(state.get("base_match_score") or 0)
        risk_penalty, risk_factors = self._calculate_risk_penalty(state)
        hr_adjusted_score = max(0.0, round(base_score - risk_penalty, 2))
        llm_result = self._screen_with_llm(state, hr_adjusted_score, risk_factors)
        llm_risks = normalize_string_list(llm_result.get("hr_risk_factors"))
        if llm_risks:
            risk_factors = list(dict.fromkeys(risk_factors + llm_risks))
        match_reason = str(
            llm_result.get("match_reason")
            or self._build_hr_reason(base_score, hr_adjusted_score, risk_factors)
        )
        hr_decision = str(llm_result.get("hr_decision") or self._build_decision(hr_adjusted_score))
        return {
            **state,
            "hr_adjusted_score": hr_adjusted_score,
            "final_display_score": hr_adjusted_score,
            "hr_risk_factors": risk_factors,
            "hr_decision": hr_decision,
            "hiring_decision": hr_decision,
            "match_reason": match_reason,
            "match_score": state.get("base_match_score"),
            "llm_used": bool(state.get("llm_used")) or bool(llm_result),
            "llm_error": "" if llm_result else get_last_llm_error(),
            "error": None,
        }

    def _calculate_risk_penalty(self, state: AgentState) -> tuple:
        """根据缺失技能和岗位要求计算 HR 风险扣分。"""

        missing_skills = [str(skill).lower() for skill in state.get("missing_skills") or []]
        risk_penalty = 0
        risk_factors = []
        risk_rules = {
            "rag": ("缺少 RAG 经验", 5),
            "langgraph": ("缺少 LangGraph 经验", 5),
            "docker": ("缺少容器化交付经验", 3),
            "postgresql": ("缺少 PostgreSQL 经验", 3),
            "redis": ("缺少 Redis 经验", 3),
        }
        for skill, (reason, penalty) in risk_rules.items():
            if skill in missing_skills:
                risk_penalty += penalty
                risk_factors.append(reason)
        if not risk_factors and float(state.get("base_match_score") or 0) < 70:
            risk_penalty += 5
            risk_factors.append("基础匹配分低于面试推进阈值")
        return risk_penalty, risk_factors

    def _screen_with_llm(
        self,
        state: AgentState,
        hr_adjusted_score: float,
        risk_factors: list,
    ) -> dict:
        """调用大模型生成 HR 初筛解释，但不允许修改基础分。"""

        system_prompt = "你是企业招聘方的候选人初筛专家，只输出 JSON。"
        user_prompt = f"""
请基于统一基础分和风险扣分生成 HR 初筛解释，不要修改 base_match_score。
输出 JSON：
{{
  "match_reason": "面向 HR 的初筛解释",
  "hr_risk_factors": ["风险1", "风险2"],
  "hr_decision": "建议进入面试 / 建议补充评估 / 建议暂缓"
}}

基础匹配分：{state.get("base_match_score")}
HR 风险调整分：{hr_adjusted_score}
评分明细：{state.get("score_detail")}
规则风险因素：{risk_factors}
缺失技能：{state.get("missing_skills") or []}
简历画像：{state.get("resume_info") or {}}
JD 画像：{state.get("jd_info") or {}}
"""
        return parse_json_object(chat_completion(system_prompt, user_prompt)) or {}

    def _build_hr_reason(
        self,
        base_score: float,
        hr_adjusted_score: float,
        risk_factors: list,
    ) -> str:
        """构造 HR 侧兜底初筛解释。"""

        risks = "、".join(risk_factors) if risk_factors else "暂无明显额外风险"
        return f"基础匹配分 {base_score}，HR 风险调整分 {hr_adjusted_score}，风险因素：{risks}。"

    def _build_decision(self, hr_adjusted_score: float) -> str:
        """根据 HR 风险调整分生成兜底招聘决策。"""

        if hr_adjusted_score >= 70:
            return "建议进入面试"
        if hr_adjusted_score >= 55:
            return "建议补充评估"
        return "建议暂缓"
