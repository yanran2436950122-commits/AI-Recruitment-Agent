"""审计日志 Repository，统一封装 audit_logs 数据访问。"""

from typing import Any, Dict, List

from memory.postgres_memory import PostgresMemory


class AuditLogRepository:
    """负责历史中心审计日志的保存和查询。"""

    def __init__(self, storage: PostgresMemory = None) -> None:
        """初始化审计日志存储适配器。"""

        self.storage = storage or PostgresMemory()

    def save(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """保存一条审计日志。"""

        return self.storage.save_audit_log(log)

    def list_by_owner(
        self,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
        analysis_id: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """按租户范围读取审计日志。"""

        return self.storage.get_audit_logs(actor_type, candidate_id, company_id, analysis_id, limit)
