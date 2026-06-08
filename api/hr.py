"""HR 侧 API 路由。"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from agents.hr_manager_agent import HRManagerAgent
from api.candidate import save_upload_file
from memory.tenant_memory_service import TenantMemoryService


router = APIRouter(prefix="/hr", tags=["hr"])
"""HR 侧路由对象。"""


@router.post("/screen")
async def screen_candidate(
    resume_file: UploadFile = File(...),
    company_id: str = Form(...),
    job_id: str = Form(...),
    session_id: str = Form("default_hr_session"),
) -> dict:
    """执行 HR 侧候选人筛选和评估。"""

    job = TenantMemoryService().get_job_profile(company_id, job_id)
    if not job or not (job.get("jd_text") or "").strip():
        raise HTTPException(status_code=400, detail="请先创建或选择岗位。")
    saved_path = await save_upload_file(resume_file)
    state = HRManagerAgent().run(
        resume_file_path=str(saved_path),
        jd_text="",
        company_id=company_id,
        job_id=job_id,
        session_id=session_id,
        resume_file_name=resume_file.filename or "",
        original_filename=resume_file.filename or "",
        content_type=resume_file.content_type or "",
    )
    if state.get("error"):
        raise HTTPException(status_code=500, detail=state["error"])
    return {
        "analysis_id": state.get("analysis_id"),
        "file_id": state.get("file_id"),
        "original_filename": state.get("original_filename"),
        "stored_filename": state.get("stored_filename"),
        "resume_hash": state.get("resume_hash"),
        "match_score": state.get("match_score"),
        "base_match_score": state.get("base_match_score"),
        "hr_adjusted_score": state.get("hr_adjusted_score"),
        "match_reason": state.get("match_reason"),
        "missing_skills": state.get("missing_skills") or [],
        "interview_questions": state.get("interview_questions") or [],
        "final_report": state.get("final_report"),
        "hiring_decision": state.get("hiring_decision"),
        "analysis_record": state.get("analysis_record") or {},
        "document_parse_result": state.get("document_parse_result") or {},
    }


@router.post("/jobs/{company_id}")
def create_job_profile(
    company_id: str,
    job_name: str = Form(...),
    jd_text: str = Form(...),
) -> dict:
    """创建 HR 企业招聘岗位。"""

    return TenantMemoryService().create_job_profile(
        company_id=company_id,
        job_name=job_name,
        jd_text=jd_text,
        created_by=company_id,
    )


@router.get("/jobs/{company_id}")
def list_job_profiles(company_id: str) -> dict:
    """读取当前企业岗位列表。"""

    return {"jobs": TenantMemoryService().list_job_profiles(company_id)}


@router.put("/jobs/{company_id}/{job_id}")
def update_job_profile(
    company_id: str,
    job_id: str,
    job_name: str = Form(...),
    jd_text: str = Form(...),
) -> dict:
    """更新企业招聘岗位并产生新的 JD 版本。"""

    job = TenantMemoryService().update_job_profile(
        company_id=company_id,
        job_id=job_id,
        job_name=job_name,
        jd_text=jd_text,
        created_by=company_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="岗位不存在或无权访问")
    return job


@router.delete("/jobs/{company_id}/{job_id}")
def deactivate_job_profile(company_id: str, job_id: str) -> dict:
    """停用企业招聘岗位。"""

    deleted = TenantMemoryService().deactivate_job_profile(company_id, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="岗位不存在或无权停用")
    return {"deleted": True, "job_id": job_id}


@router.get("/jobs/{company_id}/{job_id}/versions")
def list_job_versions(company_id: str, job_id: str) -> dict:
    """读取企业岗位 JD 版本历史。"""

    return {"versions": TenantMemoryService().list_job_versions(company_id, job_id)}


@router.get("/memory/company/{company_id}")
def get_company_memory(company_id: str) -> dict:
    """查看 Company 私有语义记忆。"""

    service = TenantMemoryService()
    return {
        "company_id": company_id,
        "semantic_memories": service.search_company_semantic_memory(company_id, company_id, top_k=20),
    }


@router.get("/analysis/company/{company_id}")
def list_company_analysis(
    company_id: str,
    job_id: str = "",
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """查看 HR 当前企业可访问的候选人评估历史。"""

    return TenantMemoryService().list_analysis_records(
        actor_type="hr",
        company_id=company_id,
        job_id=job_id,
        page=page,
        page_size=page_size,
    )


@router.get("/analysis/company/{company_id}/{analysis_id}")
def get_company_analysis(company_id: str, analysis_id: str) -> dict:
    """查看 HR 当前企业可访问的候选人评估详情。"""

    record = TenantMemoryService().get_analysis_record(
        analysis_id=analysis_id,
        actor_type="hr",
        company_id=company_id,
        action_user_id=company_id,
    )
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在或无权访问")
    return record


@router.delete("/analysis/company/{company_id}/{analysis_id}")
def delete_company_analysis(company_id: str, analysis_id: str) -> dict:
    """软删除 HR 当前企业可访问的候选人评估记录。"""

    deleted = TenantMemoryService().delete_analysis_record(
        analysis_id=analysis_id,
        actor_type="hr",
        company_id=company_id,
        action_user_id=company_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="分析记录不存在或无权删除")
    return {"deleted": True, "analysis_id": analysis_id}


@router.get("/memory/job/{job_id}")
def get_job_memory(job_id: str) -> dict:
    """查看 Job 私有语义记忆。"""

    service = TenantMemoryService()
    return {
        "job_id": job_id,
        "semantic_memories": service.search_job_semantic_memory(job_id, job_id, top_k=20),
    }
