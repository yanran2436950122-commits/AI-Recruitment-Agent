"""岗位画像智能体：为 HR 侧流程解析岗位画像。"""

from graph.state import AgentState
from tools.score_tool import parse_jd


class JobProfileAgent:
    """负责生成岗位画像的智能体。"""

    def run(self, state: AgentState) -> AgentState:
        """结合企业记忆和 JD 生成岗位画像。"""

        jd_info = state.get("jd_info") or parse_jd(state.get("jd_text") or "")
        company_memory = state.get("company_memory") or {}
        job_memory = state.get("job_memory") or {}
        jd_info["company_context"] = company_memory.get("profile", {})
        jd_info["job_context"] = job_memory.get("profile", {})
        return {**state, "jd_info": jd_info, "error": None}
