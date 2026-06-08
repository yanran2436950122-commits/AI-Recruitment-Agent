"""Candidate 侧 API 路由。"""

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS
from app.dependencies import get_manager_agent, get_memory_service
from services.file_storage_service import FileStorageService


router = APIRouter(prefix="/candidate", tags=["candidate"])
"""Candidate 侧路由对象。"""


@router.post("/analyze")
async def analyze_candidate(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
    candidate_id: str = Form("anonymous"),
    session_id: str = Form("default"),
    target_role_id: str = Form(""),
) -> dict:
    """执行 Candidate 侧简历匹配分析。"""

    if not jd_text.strip():
        raise HTTPException(status_code=400, detail="岗位 JD 不能为空")
    role = get_memory_service().get_candidate_target_role(candidate_id, target_role_id)
    if not role:
        raise HTTPException(status_code=400, detail="请先创建或选择目标岗位")
    saved_path = await save_upload_file(resume_file)
    state = get_manager_agent().run(
        resume_file_path=str(saved_path),
        jd_text=jd_text,
        user_id=candidate_id,
        candidate_id=candidate_id,
        session_id=session_id,
        thread_id=session_id,
        user_query=jd_text,
        resume_file_name=resume_file.filename or saved_path.name,
        original_filename=resume_file.filename or saved_path.name,
        content_type=resume_file.content_type or "",
        target_role_id=target_role_id,
        role_name=role.get("role_name") or "",
    )
    if state.get("error"):
        raise HTTPException(status_code=500, detail=state["error"])
    return build_candidate_response(state)


@router.post("/target-roles/{candidate_id}")
def create_candidate_target_role(
    candidate_id: str,
    role_name: str = Form(...),
    description: str = Form(""),
) -> dict:
    """创建 Candidate 求职方向。"""

    return get_memory_service().create_candidate_target_role(candidate_id, role_name, description)


@router.get("/target-roles/{candidate_id}")
def list_candidate_target_roles(candidate_id: str) -> dict:
    """读取 Candidate 自己的求职方向列表。"""

    return {"target_roles": get_memory_service().list_candidate_target_roles(candidate_id)}


@router.put("/target-roles/{candidate_id}/{target_role_id}")
def update_candidate_target_role(
    candidate_id: str,
    target_role_id: str,
    role_name: str = Form(...),
    description: str = Form(""),
) -> dict:
    """更新 Candidate 求职方向。"""

    role = get_memory_service().update_candidate_target_role(
        candidate_id,
        target_role_id,
        role_name,
        description,
    )
    if not role:
        raise HTTPException(status_code=404, detail="目标岗位不存在或无权访问")
    return role


@router.delete("/target-roles/{candidate_id}/{target_role_id}")
def deactivate_candidate_target_role(candidate_id: str, target_role_id: str) -> dict:
    """停用 Candidate 求职方向。"""

    deleted = get_memory_service().deactivate_candidate_target_role(candidate_id, target_role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="目标岗位不存在或无权停用")
    return {"deleted": True, "target_role_id": target_role_id}


@router.get("/memory/{candidate_id}")
def get_candidate_memory(candidate_id: str) -> dict:
    """查看 Candidate 私有记忆。"""

    return get_memory_service().get_user_memory(candidate_id)


@router.get("/analysis/{candidate_id}")
def list_candidate_analysis(candidate_id: str, page: int = 1, page_size: int = 10) -> dict:
    """查看 Candidate 自己的历史分析记录。"""

    return get_memory_service().list_analysis_records(
        actor_type="candidate",
        candidate_id=candidate_id,
        page=page,
        page_size=page_size,
    )


@router.get("/analysis/{candidate_id}/{analysis_id}")
def get_candidate_analysis(candidate_id: str, analysis_id: str) -> dict:
    """查看 Candidate 自己的历史分析详情。"""

    record = get_memory_service().get_analysis_record(
        analysis_id=analysis_id,
        actor_type="candidate",
        candidate_id=candidate_id,
        action_user_id=candidate_id,
    )
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在或无权访问")
    return record


@router.delete("/analysis/{candidate_id}/{analysis_id}")
def delete_candidate_analysis(candidate_id: str, analysis_id: str) -> dict:
    """软删除 Candidate 自己的历史分析记录。"""

    deleted = get_memory_service().delete_analysis_record(
        analysis_id=analysis_id,
        actor_type="candidate",
        candidate_id=candidate_id,
        action_user_id=candidate_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="分析记录不存在或无权删除")
    return {"deleted": True, "analysis_id": analysis_id}


@router.delete("/memory/{candidate_id}")
def delete_candidate_memory(candidate_id: str) -> dict:
    """清除 Candidate 私有长期记忆。"""

    get_memory_service().clear_user_memory(candidate_id)
    return {"deleted": True, "candidate_id": candidate_id}


async def save_upload_file(upload: UploadFile) -> Path:
    """把上传简历先保存到 data/uploads/tmp 并返回文件路径。"""

    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"仅支持 {sorted(ALLOWED_EXTENSIONS)} 文件")
    content = await upload.read()
    try:
        return FileStorageService().save_temp_upload(content, upload.filename or f"resume{suffix}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def build_candidate_response(state: dict) -> dict:
    """构造 Candidate 侧接口响应。"""

    return {
        "analysis_id": state.get("analysis_id"),
        "file_id": state.get("file_id"),
        "original_filename": state.get("original_filename"),
        "stored_filename": state.get("stored_filename"),
        "resume_hash": state.get("resume_hash"),
        "match_score": state.get("match_score"),
        "base_match_score": state.get("base_match_score"),
        "candidate_display_score": state.get("candidate_display_score"),
        "match_reason": state.get("match_reason"),
        "missing_skills": state.get("missing_skills") or [],
        "optimized_resume": state.get("optimized_resume") or "",
        "interview_questions": state.get("interview_questions") or [],
        "final_report": state.get("final_report"),
        "analysis_record": state.get("analysis_record") or {},
        "document_parse_result": state.get("document_parse_result") or {},
        "llm_used": bool(state.get("llm_used")),
    }
