"""记忆工具封装。"""

from typing import Any, Dict

from graph.state import AgentState
from memory.memory_service import MemoryService


def load_user_context(user_id: str, session_id: str, query: str) -> Dict[str, Any]:
    """加载用户上下文记忆。"""

    return MemoryService().load_memory(user_id=user_id, session_id=session_id, query=query)


def save_user_context(state: AgentState) -> None:
    """保存用户上下文记忆。"""

    MemoryService().save_memory_after_run(state)
