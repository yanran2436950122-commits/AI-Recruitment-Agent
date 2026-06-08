"""上传文件生命周期管理 API。"""

from fastapi import APIRouter, HTTPException, Query

from services.file_storage_service import FileStorageService


router = APIRouter(prefix="/files", tags=["files"])
"""文件生命周期管理路由。"""


@router.post("/cleanup")
def cleanup_files() -> dict:
    """清理过期 tmp 文件和过期 active 文件。"""

    return FileStorageService().cleanup_expired_files()


@router.delete("/{file_id}")
def delete_uploaded_file(
    file_id: str,
    actor_type: str = Query(...),
    candidate_id: str = Query(""),
    company_id: str = Query(""),
) -> dict:
    """按 file_id 软删除文件，Candidate/HR 必须满足租户权限。"""

    deleted = FileStorageService().mark_file_deleted(
        file_id=file_id,
        actor_type=actor_type,
        candidate_id=candidate_id,
        company_id=company_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="文件不存在或无权删除")
    return {"deleted": True, "file_id": file_id}
