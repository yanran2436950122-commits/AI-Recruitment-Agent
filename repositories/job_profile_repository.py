"""企业岗位 Repository，统一封装 job_profiles 数据访问。"""

from typing import Any, Dict, List

from memory.postgres_memory import PostgresMemory


class JobProfileRepository:
    """负责企业岗位画像的创建、查询、更新和停用。"""

    def __init__(self, storage: PostgresMemory = None) -> None:
        """初始化岗位存储适配器。"""

        self.storage = storage or PostgresMemory()

    def save(self, company_id: str, job_name: str, jd_text: str, created_by: str = "") -> Dict[str, Any]:
        """创建企业岗位画像。"""

        return self.storage.create_job_profile(company_id, job_name, jd_text, created_by)

    def get_by_id(self, company_id: str, job_id: str) -> Dict[str, Any]:
        """按 company_id 和 job_id 读取岗位画像。"""

        return self.storage.get_job_profile(company_id, job_id) or {}

    def list_by_owner(self, company_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """读取企业可见的岗位画像列表。"""

        return self.storage.list_job_profiles(company_id, status=status)

    def update(
        self,
        company_id: str,
        job_id: str,
        job_name: str,
        jd_text: str,
        created_by: str = "",
    ) -> Dict[str, Any]:
        """更新岗位画像并保留 JD 版本历史。"""

        return self.storage.update_job_profile(company_id, job_id, job_name, jd_text, created_by) or {}

    def mark_inactive(self, company_id: str, job_id: str) -> bool:
        """停用企业岗位。"""

        return self.storage.deactivate_job_profile(company_id, job_id)

    def restore(self, company_id: str, job_id: str) -> bool:
        """恢复已停用岗位。"""

        return self.storage.restore_job_profile(company_id, job_id)
