"""求职者匹配解释智能体：基于统一基础分生成求职者视角解释。"""

from graph.state import AgentState
from llm.client import chat_completion, get_last_llm_error, normalize_string_list, parse_json_object


class MatchAgent:
    """负责补充求职者解释和学习建议，不重新计算基础分。"""

    def run(self, state: AgentState) -> AgentState:
        """读取基础评分结果并生成 Candidate 侧解释。"""

        llm_result = self._explain_with_llm(state)
        match_reason = str(llm_result.get("match_reason") or state.get("match_reason") or "")
        learning_suggestions = normalize_string_list(llm_result.get("learning_suggestions"))
        return {
            **state,
            "match_reason": match_reason,
            "learning_suggestions": learning_suggestions or state.get("learning_suggestions") or [],
            "candidate_display_score": state.get("base_match_score"),
            "final_display_score": state.get("base_match_score"),
            "match_score": state.get("base_match_score"),
            "llm_used": bool(state.get("llm_used")) or bool(llm_result),
            "llm_error": "" if llm_result else get_last_llm_error(),
            "error": None,
        }

    def _explain_with_llm(self, state: AgentState) -> dict:
        """调用大模型生成求职者视角解释，但不允许修改基础分。"""

        system_prompt = "你是求职者侧的岗位匹配解释专家，只输出 JSON。"
        user_prompt = f"""
请基于统一规则基础分生成求职者视角解释，不要修改基础分。
输出 JSON：
{{
  "match_reason": "解释技能覆盖、项目相关性和短板",
  "learning_suggestions": ["学习建议1", "学习建议2"]
}}

基础匹配分：{state.get("base_match_score")}
评分明细：{state.get("score_detail")}
缺失技能：{state.get("missing_skills") or []}
简历画像：{state.get("resume_info") or {}}
JD 画像：{state.get("jd_info") or {}}
RAG 上下文：{state.get("rag_context") or ""}
"""
        return parse_json_object(chat_completion(system_prompt, user_prompt)) or {}
