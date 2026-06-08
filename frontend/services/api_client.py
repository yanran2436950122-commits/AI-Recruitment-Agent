"""前端页面使用的服务调用适配器。"""

from pathlib import Path
from typing import Dict, List

from frontend import legacy


def analyze_candidate(resume_file_path: str, jd_text: str, identity_config: Dict[str, str], file_name: str, content_type: str = "") -> Dict[str, object]:
    """执行 Candidate 分析。"""

    return legacy.analyze_resume_for_candidate(resume_file_path, jd_text, identity_config, file_name, content_type)


def analyze_hr(resume_file_path: str, jd_text: str, identity_config: Dict[str, str], file_name: str, content_type: str = "") -> Dict[str, object]:
    """执行 HR 分析。"""

    return legacy.analyze_resume_for_hr(resume_file_path, jd_text, identity_config, file_name, content_type)


def analyze_by_identity(resume_file_path: str, jd_text: str, identity_config: Dict[str, str], file_name: str, content_type: str = "") -> Dict[str, object]:
    """按 actor_type 分派分析流程。"""

    if identity_config.get("actor_type") == "hr":
        return analyze_hr(resume_file_path, jd_text, identity_config, file_name, content_type)
    return analyze_candidate(resume_file_path, jd_text, identity_config, file_name, content_type)


def save_uploaded_resume(uploaded_file) -> Path:
    """保存上传文件到 tmp 生命周期目录。"""

    return legacy.save_uploaded_resume(uploaded_file)


def list_analysis_records(*args, **kwargs) -> Dict[str, object]:
    """读取历史分析记录。"""

    return legacy.get_history_service().list_analysis_records(*args, **kwargs)


def get_analysis_detail(*args, **kwargs) -> Dict[str, object]:
    """读取历史分析详情。"""

    return legacy.get_history_service().get_analysis_record(*args, **kwargs)


def create_job(*args, **kwargs) -> Dict[str, object]:
    """创建 HR 岗位。"""

    return legacy.get_history_service().create_job_profile(*args, **kwargs)


def update_job(*args, **kwargs) -> Dict[str, object]:
    """更新 HR 岗位。"""

    return legacy.get_history_service().update_job_profile(*args, **kwargs)


def deactivate_job(*args, **kwargs) -> bool:
    """停用 HR 岗位。"""

    return legacy.get_history_service().deactivate_job_profile(*args, **kwargs)


def list_jobs(*args, **kwargs) -> List[Dict[str, object]]:
    """读取 HR 岗位。"""

    return legacy.get_history_service().list_job_profiles(*args, **kwargs)


def create_target_role(*args, **kwargs) -> Dict[str, object]:
    """创建 Candidate 目标岗位。"""

    return legacy.get_history_service().create_candidate_target_role(*args, **kwargs)


def update_target_role(*args, **kwargs) -> Dict[str, object]:
    """更新 Candidate 目标岗位。"""

    return legacy.get_history_service().update_candidate_target_role(*args, **kwargs)


def deactivate_target_role(*args, **kwargs) -> bool:
    """停用 Candidate 目标岗位。"""

    return legacy.get_history_service().deactivate_candidate_target_role(*args, **kwargs)


def list_target_roles(*args, **kwargs) -> List[Dict[str, object]]:
    """读取 Candidate 目标岗位。"""

    return legacy.get_history_service().list_candidate_target_roles(*args, **kwargs)


def cleanup_files() -> Dict[str, int]:
    """清理过期上传文件。"""

    from services.file_storage_service import FileStorageService

    return FileStorageService().cleanup_expired_files()


def delete_file(file_id: str, actor_type: str, candidate_id: str = "", company_id: str = "") -> bool:
    """按权限软删除上传文件。"""

    from services.file_storage_service import FileStorageService

    return FileStorageService().mark_file_deleted(file_id, actor_type, candidate_id, company_id)


def ingest_knowledge_base() -> Dict[str, int]:
    """导入知识库。"""

    return legacy.ingest_knowledge_base()


def get_monitoring_summary() -> Dict[str, object]:
    """读取监控摘要。"""

    return legacy.get_monitor_service().get_run_summary()
