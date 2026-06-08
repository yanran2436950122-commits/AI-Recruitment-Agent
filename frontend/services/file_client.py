"""文件生命周期前端服务适配器。"""

from services.file_storage_service import FileStorageService


def cleanup_files() -> dict:
    """清理过期上传文件。"""

    return FileStorageService().cleanup_expired_files()


def delete_file(file_id: str, actor_type: str, candidate_id: str = "", company_id: str = "") -> bool:
    """软删除指定上传文件。"""

    return FileStorageService().mark_file_deleted(file_id, actor_type, candidate_id, company_id)
