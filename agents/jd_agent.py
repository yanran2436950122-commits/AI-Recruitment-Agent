"""JD 智能体：解析岗位描述。"""

from graph.state import AgentState
from llm.client import chat_completion, normalize_string_list, parse_json_object
from tools.score_tool import parse_jd


class JDAgent:
    """负责结构化输入岗位 JD 的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """从 JD 文本中提取必备技能、职责、加分项和关键词。"""

        try:
            jd_text = state.get("jd_text", "")
            user_profile = state.get("user_profile") or {}
            jd_info = parse_jd(jd_text)
            llm_jd_info = self._parse_jd_with_llm(jd_text)
            if llm_jd_info:
                jd_info.update(llm_jd_info)
            if user_profile:
                jd_info["user_target_context"] = user_profile.get("latest_target_summary", "")
            return {
                **state,
                "jd_info": jd_info,
                "llm_used": bool(state.get("llm_used")) or bool(llm_jd_info),
                "error": None,
            }
        except Exception as exc:
            return {**state, "error": f"JD 智能体解析失败: {exc}"}

    def _parse_jd_with_llm(self, jd_text: str) -> dict:
        """调用大模型提取 JD 结构化字段。"""

        system_prompt = "你是招聘系统中的岗位 JD 解析专家，只输出 JSON。"
        user_prompt = f"""
请解析以下岗位 JD，输出 JSON：
{{
  "required_skills": ["必备技能1", "必备技能2"],
  "responsibilities": ["职责1", "职责2"],
  "bonus_points": ["加分项1", "加分项2"],
  "keywords": ["关键词1", "关键词2"],
  "summary": "不超过120字的岗位摘要"
}}

JD 内容：
{jd_text[:6000]}
"""
        parsed = parse_json_object(chat_completion(system_prompt, user_prompt))
        if not parsed:
            return {}
        parsed["required_skills"] = normalize_string_list(parsed.get("required_skills"))
        parsed["responsibilities"] = normalize_string_list(parsed.get("responsibilities"))
        parsed["bonus_points"] = normalize_string_list(parsed.get("bonus_points"))
        parsed["keywords"] = normalize_string_list(parsed.get("keywords"))
        return parsed
