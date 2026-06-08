"""记忆智能体：为 LangGraph 工作流加载和保存记忆。"""

from graph.state import AgentState
from memory.tenant_memory_service import TenantMemoryService


class MemoryAgent:
    """连接工作流和统一记忆服务的智能体。"""

    def __init__(self) -> None:
        """初始化记忆服务。"""

        self.service = TenantMemoryService()

    def load_memory_node(self, state: AgentState) -> AgentState:
        """加载会话记忆、用户画像、历史匹配和语义记忆。"""

        user_id = state.get("user_id") or "anonymous"
        session_id = state.get("session_id") or "default"
        query = state.get("user_query") or state.get("jd_text") or ""
        try:
            loaded = self.service.load_memory_for_actor(
                {**state, "user_id": user_id, "session_id": session_id, "user_query": query}
            )
            return {**state, **loaded, "error": None}
        except Exception as exc:
            return {**state, "error": None, "memory_error": f"加载记忆失败，已降级运行: {exc}"}

    def save_memory_node(self, state: AgentState) -> AgentState:
        """保存工作流产出的会话记忆、长期记忆和语义记忆。"""

        try:
            analysis_record = self.service.save_memory_for_actor(state)
            return {**state, "analysis_record": analysis_record or state.get("analysis_record"), "error": None}
        except Exception as exc:
            return {**state, "error": None, "memory_error": f"保存记忆失败，已降级运行: {exc}"}
