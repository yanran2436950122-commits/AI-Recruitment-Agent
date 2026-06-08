"""Candidate 目标岗位 Repository，统一封装 target_roles 数据访问。"""

from typing import Any, Dict, List

from memory.postgres_memory import PostgresMemory


class TargetRoleRepository:
    """负责 Candidate 求职方向的创建、查询、更新和停用。"""

    def __init__(self, storage: PostgresMemory = None) -> None:
        """初始化目标岗位存储适配器。"""

        self.storage = storage or PostgresMemory()

    def save(self, candidate_id: str, role_name: str, description: str = "") -> Dict[str, Any]:
        """创建 Candidate 求职方向。"""

        return self.storage.create_candidate_target_role(candidate_id, role_name, description)

    def get_by_id(self, candidate_id: str, target_role_id: str) -> Dict[str, Any]:
        """按 candidate_id 和 target_role_id 读取求职方向。"""

        return self.storage.get_candidate_target_role(candidate_id, target_role_id) or {}

    def list_by_owner(self, candidate_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """读取 Candidate 自己的求职方向列表。"""

        return self.storage.list_candidate_target_roles(candidate_id, status=status)

    def update(
        self,
        candidate_id: str,
        target_role_id: str,
        role_name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """更新 Candidate 求职方向。"""

        return self.storage.update_candidate_target_role(candidate_id, target_role_id, role_name, description) or {}

    def mark_inactive(self, candidate_id: str, target_role_id: str) -> bool:
        """停用 Candidate 求职方向。"""

        return self.storage.deactivate_candidate_target_role(candidate_id, target_role_id)

    def restore(self, candidate_id: str, target_role_id: str) -> bool:
        """恢复已停用求职方向。"""

        return self.storage.restore_candidate_target_role(candidate_id, target_role_id)
