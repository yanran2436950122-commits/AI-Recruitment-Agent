"""面试智能体：使用 RAG 上下文和大模型生成面试题。"""

from typing import List

from graph.state import AgentState, TASK_STATUS_FAILED, TASK_STATUS_GENERATING
from llm.client import chat_completion, normalize_string_list, parse_json_object


class InterviewAgent:
    """负责生成 RAG 增强定制面试题的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """检索相关知识，并优先使用大模型生成面试题。"""

        try:
            context = state.get("rag_context") or ""
            llm_questions = self._generate_questions_with_llm(state, context)
            questions = llm_questions or self._generate_questions_locally(state, context)
            return {
                **state,
                "interview_questions": questions,
                "llm_used": bool(state.get("llm_used")) or bool(llm_questions),
                "task_status": TASK_STATUS_GENERATING,
                "error": None,
            }
        except Exception as exc:
            return {**state, "task_status": TASK_STATUS_FAILED, "error": f"面试智能体生成失败: {exc}"}

    def _generate_questions_with_llm(self, state: AgentState, context: str) -> List[str]:
        """调用大模型结合 RAG 上下文生成面试题。"""

        system_prompt = "你是招聘系统中的技术面试官，只输出 JSON。"
        user_prompt = f"""
请结合简历、JD 和 RAG 上下文生成定制面试题，必须分为基础题、项目题、Agent/RAG专项题、追问题。
输出 JSON：
{{
  "interview_questions": [
    "【基础题】问题1",
    "【项目题】问题2",
    "【Agent/RAG专项题】问题3",
    "【追问题】问题4"
  ]
}}

简历解析：{state.get("resume_info") or {}}
JD 解析：{state.get("jd_info") or {}}
缺失技能：{state.get("missing_skills") or []}
RAG 上下文：{context}
"""
        parsed = parse_json_object(chat_completion(system_prompt, user_prompt))
        return normalize_string_list((parsed or {}).get("interview_questions"))

    def _generate_questions_locally(self, state: AgentState, context: str) -> List[str]:
        """在没有大模型时使用本地规则生成兜底面试题。"""

        jd_info = state.get("jd_info") or {}
        resume_info = state.get("resume_info") or {}
        required_skills = jd_info.get("required_skills", []) or ["岗位核心能力"]
        resume_summary = resume_info.get("summary", "候选人简历")
        context_hint = context[:120] if context else "知识库暂无命中，使用通用面试框架。"

        return [
            f"【基础题】请解释 {required_skills[0]} 的核心概念和常见应用场景。",
            f"【项目题】JD 关注 {', '.join(required_skills[:3])}，请说明你过往项目中最能证明这些能力的案例。",
            f"【项目题】基于简历摘要“{resume_summary[:80]}”，请拆解一个关键项目的技术方案、难点和结果。",
            f"【Agent/RAG专项题】知识库参考：{context_hint}。请说明你会如何设计检索、重排和生成链路。",
            "【追问题】如果系统质量和交付周期冲突，你会如何平衡短期交付与长期维护？",
        ]
