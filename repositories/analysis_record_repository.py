"""分析记录 Repository，统一封装 analysis_records 数据访问。"""

from typing import Any, Dict, List

from memory.postgres_memory import PostgresMemory


class AnalysisRecordRepository:
    """负责分析记录的保存、查询和软删除。"""

    def __init__(self, storage: PostgresMemory = None) -> None:
        """初始化分析记录存储适配器。"""

        self.storage = storage or PostgresMemory()

    def save(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """保存一条新的分析记录，禁止覆盖旧 analysis_id。"""

        return self.storage.save_analysis_record(record)

    def get_by_id(
        self,
        analysis_id: str,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
    ) -> Dict[str, Any]:
        """按 analysis_id 和租户范围读取分析记录。"""

        return self.storage.get_analysis_record_by_id(analysis_id, actor_type, candidate_id, company_id) or {}

    def list_by_owner(
        self,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        target_role_id: str = "",
        status: str = "active",
        search: str = "",
        sort_by: str = "created_at",
        descending: bool = True,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按 Candidate 或 HR 租户读取分析记录列表。"""

        return self.storage.get_analysis_records(
            actor_type=actor_type,
            candidate_id=candidate_id,
            company_id=company_id,
            job_id=job_id,
            target_role_id=target_role_id,
            status=status,
            search=search,
            sort_by=sort_by,
            descending=descending,
            limit=limit,
            offset=offset,
        )

    def count_by_owner(
        self,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        target_role_id: str = "",
        status: str = "active",
        search: str = "",
    ) -> int:
        """统计指定租户范围内的分析记录数量。"""

        return self.storage.count_analysis_records(
            actor_type=actor_type,
            candidate_id=candidate_id,
            company_id=company_id,
            job_id=job_id,
            target_role_id=target_role_id,
            status=status,
            search=search,
        )

    def update_status(
        self,
        analysis_id: str,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
        status: str = "deleted",
    ) -> bool:
        """更新分析记录状态，当前 fallback 仅支持软删除。"""

        if status == "deleted":
            return self.soft_delete(analysis_id, actor_type, candidate_id, company_id)
        return False

    def soft_delete(
        self,
        analysis_id: str,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
    ) -> bool:
        """按租户范围软删除分析记录。"""

        return self.storage.soft_delete_analysis_record(analysis_id, actor_type, candidate_id, company_id)
