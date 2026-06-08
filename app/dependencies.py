"""FastAPI 依赖注入辅助函数。"""

from functools import lru_cache

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService


@lru_cache(maxsize=1)
def get_manager_agent() -> ManagerAgent:
    """创建并缓存工作流管理智能体。"""

    return ManagerAgent()


@lru_cache(maxsize=1)
def get_memory_service() -> TenantMemoryService:
    """创建并缓存统一记忆服务。"""

    return TenantMemoryService()
