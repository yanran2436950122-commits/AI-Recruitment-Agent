"""候选人评估智能体：基于 HR 风险调整分生成评估结论。"""

from graph.state import AgentState
from llm.client import chat_completion, get_last_llm_error


class EvaluationAgent:
    """负责生成候选人评估和招聘决策建议的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """根据基础分、HR 风险调整分和面试方案生成最终评估报告。"""

        base_score = float(state.get("base_match_score") or state.get("match_score") or 0)
        hr_adjusted_score = float(state.get("hr_adjusted_score") or base_score)
        risk_factors = state.get("hr_risk_factors") or []
        decision = state.get("hr_decision") or self._build_decision(hr_adjusted_score)
        report = self._build_report(state, base_score, hr_adjusted_score, risk_factors, decision)
        llm_report = self._evaluate_with_llm(state, report, decision)
        return {
            **state,
            "final_report": llm_report or report,
            "hiring_decision": decision,
            "hr_decision": decision,
            "final_display_score": hr_adjusted_score,
            "match_score": base_score,
            "llm_used": bool(state.get("llm_used")) or bool(llm_report),
            "llm_error": "" if llm_report else get_last_llm_error(),
            "error": None,
        }

    def _build_decision(self, hr_adjusted_score: float) -> str:
        """根据 HR 风险调整分生成招聘决策。"""

        if hr_adjusted_score >= 70:
            return "建议进入面试"
        if hr_adjusted_score >= 55:
            return "建议补充评估"
        return "建议暂缓"

    def _build_report(
        self,
        state: AgentState,
        base_score: float,
        hr_adjusted_score: float,
        risk_factors: list,
        decision: str,
    ) -> str:
        """构造 HR 侧兜底评估报告。"""

        risk_text = "\n".join(f"- {item}" for item in risk_factors) or "- 暂无额外风险扣分"
        questions_text = "\n".join(f"- {item}" for item in state.get("interview_questions") or [])
        return (
            "# HR 候选人评估报告\n\n"
            f"- 基础匹配分: {base_score}\n"
            f"- HR 风险调整分: {hr_adjusted_score}\n"
            f"- 解析警告: {state.get('warning') or '暂无'}\n"
            f"- 决策建议: {decision}\n"
            f"- 排序说明: {state.get('ranking_result') or ''}\n"
            f"- 缺失技能: {', '.join(state.get('missing_skills') or [])}\n\n"
            "## 风险扣分原因\n"
            f"{risk_text}\n\n"
            "## 面试设计\n"
            f"{questions_text}"
        )

    def _evaluate_with_llm(self, state: AgentState, fallback_report: str, decision: str) -> str:
        """调用大模型生成 HR 候选人评估报告。"""

        system_prompt = "你是企业招聘方的候选人评估专家，输出 Markdown。"
        user_prompt = f"""
请基于以下信息生成 HR 候选人评估报告，必须同时展示基础匹配分、HR 风险调整分和风险扣分原因。
不要修改基础匹配分。

决策建议：{decision}
基础匹配分：{state.get("base_match_score")}
HR 风险调整分：{state.get("hr_adjusted_score")}
风险因素：{state.get("hr_risk_factors") or []}
候选人画像：{state.get("resume_info") or {}}
岗位画像：{state.get("jd_info") or {}}
面试问题：{state.get("interview_questions") or []}
兜底报告：
{fallback_report}
"""
        return chat_completion(system_prompt, user_prompt) or ""
