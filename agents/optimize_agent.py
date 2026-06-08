"""优化智能体：生成简历优化建议并支持重新匹配。"""

from graph.state import AgentState, TASK_STATUS_FAILED, TASK_STATUS_GENERATING
from llm.client import chat_completion, normalize_string_list, parse_json_object
from tools.score_tool import build_optimization_suggestions


class OptimizeAgent:
    """负责为低匹配场景生成优化建议的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """添加优化建议，并准备用于重新匹配的简历草稿。"""

        try:
            retry_count = int(state.get("retry_count") or 0) + 1
            missing_skills = state.get("missing_skills") or []
            suggestions = build_optimization_suggestions(missing_skills)
            llm_result = self._optimize_with_llm(state, suggestions)
            if llm_result:
                suggestions = normalize_string_list(
                    llm_result.get("optimization_suggestions") or suggestions
                )
            optimized_resume = str(
                (llm_result or {}).get("optimized_resume")
                or self._build_optimized_resume(state, suggestions)
            )
            return {
                **state,
                "retry_count": retry_count,
                "optimization_suggestions": suggestions,
                "optimized_resume": optimized_resume,
                "candidate_display_score": state.get("base_match_score"),
                "final_display_score": state.get("base_match_score"),
                "match_score": state.get("base_match_score"),
                "llm_used": bool(state.get("llm_used")) or bool(llm_result),
                "task_status": TASK_STATUS_GENERATING,
                "error": None,
            }
        except Exception as exc:
            return {**state, "task_status": TASK_STATUS_FAILED, "error": f"优化智能体优化失败: {exc}"}

    def _optimize_with_llm(self, state: AgentState, fallback_suggestions: list) -> dict:
        """调用大模型生成更贴近 JD 的简历优化建议。"""

        system_prompt = "你是招聘系统中的简历优化专家，只输出 JSON。"
        user_prompt = f"""
请基于 JD、简历和缺失技能生成优化建议，不能虚构候选人没有的经历。
输出 JSON：
{{
  "optimization_suggestions": [
    "原问题：...；修改建议：...；修改后示例：...；预期提升：..."
  ],
  "optimized_resume": "在原简历基础上追加优化提示后的文本"
}}

已有建议：{fallback_suggestions}
缺失技能：{state.get("missing_skills") or []}
用户画像：{state.get("user_profile") or {}}
优秀简历案例：{state.get("rag_context") or ""}
JD：{state.get("jd_text") or ""}
简历：{(state.get("resume_text") or "")[:5000]}
"""
        return parse_json_object(chat_completion(system_prompt, user_prompt)) or {}

    def _build_optimized_resume(self, state: AgentState, suggestions: list) -> str:
        """通过追加优化说明创建可重新匹配的简历草稿。"""

        resume_text = state.get("optimized_resume") or state.get("resume_text") or ""
        missing_skills = state.get("missing_skills") or []
        suggestion_text = "\n".join(f"- {item}" for item in suggestions)
        skill_hint = ", ".join(missing_skills)
        return (
            f"{resume_text}\n\n"
            "【针对 JD 的简历优化建议】\n"
            f"{suggestion_text}\n"
            f"建议补充关键词: {skill_hint}\n"
        )
