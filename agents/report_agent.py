"""报告智能体：生成最终综合报告。"""

from typing import Iterable, List

from graph.state import AgentState, TASK_STATUS_COMPLETED, TASK_STATUS_FAILED
from llm.client import chat_completion


class ReportAgent:
    """负责汇总前序工作流输出的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """生成 API 返回的最终报告，并优先使用大模型润色。"""

        try:
            local_report = self._compose_report(state)
            llm_report = self._compose_report_with_llm(state, local_report)
            return {
                **state,
                "final_report": llm_report or local_report,
                "llm_used": bool(state.get("llm_used")) or bool(llm_report),
                "task_status": TASK_STATUS_COMPLETED,
                "error": None,
            }
        except Exception as exc:
            return {**state, "task_status": TASK_STATUS_FAILED, "error": f"报告智能体生成失败: {exc}"}

    def _compose_report_with_llm(self, state: AgentState, local_report: str) -> str:
        """调用大模型生成更自然的综合报告。"""

        system_prompt = "你是招聘系统中的候选人评估报告专家，输出 Markdown。"
        user_prompt = f"""
请基于以下工作流状态和本地报告，生成一份结构清晰、结论明确的中文综合报告。
报告必须包含：当前匹配度、优势、缺失项、简历优化建议、面试题、下一步学习建议、与历史记录的对比。
如果引用 RAG 上下文，请标明来源。

工作流状态：
{state}

本地报告：
{local_report}
"""
        return chat_completion(system_prompt, user_prompt) or ""

    def _compose_report(self, state: AgentState) -> str:
        """基于共享状态组装可读的 Markdown 报告。"""

        match_score = state.get("base_match_score") or state.get("match_score")
        final_display_score = state.get("final_display_score") or match_score
        match_reason = state.get("match_reason") or "暂无匹配说明。"
        missing_skills = state.get("missing_skills") or []
        suggestions = state.get("optimization_suggestions") or []
        questions = state.get("interview_questions") or []
        optimized_resume = state.get("optimized_resume") or ""
        historical_matches = state.get("historical_matches") or []
        retry_count = int(state.get("retry_count") or 0)
        llm_used = "是" if state.get("llm_used") else "否"
        history_summary = self._format_history(historical_matches)
        warning = state.get("warning") or ""

        sections = [
            "# AI 招聘匹配综合报告",
            (
                "## 匹配结论\n"
                f"- 基础匹配分: {match_score if match_score is not None else 0}\n"
                f"- 最终展示分: {final_display_score if final_display_score is not None else 0}\n"
                f"- 匹配理由: {match_reason}\n"
                f"- 优化重试次数: {retry_count}\n"
                f"- 是否使用大模型: {llm_used}"
            ),
            f"## 历史对比\n{history_summary}",
            f"## 解析与评分提示\n{warning or '暂无解析质量警告。'}",
            f"## 缺失能力\n{self._format_list(missing_skills, '暂无明显缺失能力。')}",
            f"## 优化建议\n{self._format_list(suggestions, '当前无需额外优化建议。')}",
            f"## 优化后简历摘要\n{optimized_resume[:800] if optimized_resume else '暂无优化后简历。'}",
            f"## 定制面试题\n{self._format_list(questions, '匹配分较低或流程提前结束，暂未生成面试题。')}",
            f"## 知识库来源\n{self._format_sources(state.get('retrieved_docs') or [])}",
        ]
        return "\n\n".join(sections)

    def _format_list(self, values: Iterable[str], empty_text: str) -> str:
        """格式化报告列表，并在为空时返回可读的占位文案。"""

        items: List[str] = [str(value) for value in values if value]
        if not items:
            return empty_text
        return "\n".join(f"- {item}" for item in items)

    def _format_history(self, historical_matches: list) -> str:
        """格式化历史匹配记录对比。"""

        if not historical_matches:
            return "暂无历史匹配记录。"
        lines = []
        for item in historical_matches[:5]:
            lines.append(
                f"- {item.get('created_at', '')}: 分数 {item.get('match_score', 0)}，"
                f"缺失 {', '.join(item.get('missing_skills', []) or [])}"
            )
        return "\n".join(lines)

    def _format_sources(self, docs: list) -> str:
        """格式化报告引用的知识库来源。"""

        sources = []
        for doc in docs:
            source = doc.get("source") or (doc.get("metadata") or {}).get("source")
            if source and source not in sources:
                sources.append(source)
        return self._format_list(sources, "本次报告未引用知识库来源。")
