"""面试设计智能体：为 HR 侧流程设计面试方案。"""

from graph.state import AgentState
from llm.client import chat_completion, get_last_llm_error, normalize_string_list, parse_json_object


class InterviewDesignAgent:
    """负责根据岗位画像和候选人短板设计面试方案的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """生成 HR 使用的面试题和考察维度。"""

        missing_skills = state.get("missing_skills") or []
        required_skills = (state.get("jd_info") or {}).get("required_skills", [])
        questions = [
            f"【技能验证】请围绕 {skill} 设计一个真实业务场景并说明方案。"
            for skill in (missing_skills or required_skills[:3])
        ]
        questions.append("【综合评估】请说明候选人在项目复杂度、协作和交付风险上的表现。")
        llm_questions = self._design_with_llm(state, questions)
        return {
            **state,
            "interview_questions": llm_questions or questions,
            "llm_used": bool(state.get("llm_used")) or bool(llm_questions),
            "llm_error": "" if llm_questions else get_last_llm_error(),
            "error": None,
        }

    def _design_with_llm(self, state: AgentState, fallback_questions: list) -> list:
        """调用大模型生成更贴近岗位的 HR 面试方案。"""

        system_prompt = "你是企业招聘方的技术面试设计专家，只输出 JSON。"
        user_prompt = f"""
请为 HR 生成结构化面试方案，输出 JSON：
{{
  "interview_questions": [
    "【技能验证】...",
    "【项目深挖】...",
    "【风险核验】...",
    "【追问】..."
  ]
}}

兜底问题：{fallback_questions}
匹配分：{state.get("match_score")}
缺失技能：{state.get("missing_skills") or []}
JD 画像：{state.get("jd_info") or {}}
候选人画像：{state.get("resume_info") or {}}
"""
        parsed = parse_json_object(chat_completion(system_prompt, user_prompt))
        return normalize_string_list((parsed or {}).get("interview_questions"))
