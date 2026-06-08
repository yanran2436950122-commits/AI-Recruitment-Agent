"""AI 招聘平台的 FastAPI 入口。"""

from fastapi import FastAPI, File, Form, UploadFile

from api.candidate import analyze_candidate, router as candidate_router
from api.files import router as files_router
from api.hr import router as hr_router
from app.dependencies import get_memory_service
from rag.ingest import ingest_knowledge_base


app = FastAPI(title="AI Recruitment Agent", version="0.1.0")
"""FastAPI 应用实例。"""

app.include_router(candidate_router)
app.include_router(hr_router)
app.include_router(files_router)


@app.get("/health")
def health_check() -> dict:
    """返回用于部署探活的简单健康检查结果。"""

    return {"status": "ok"}


@app.post("/analyze")
async def analyze_resume_legacy(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
    user_id: str = Form("anonymous"),
    session_id: str = Form("default"),
) -> dict:
    """兼容旧版本的 Candidate 简历分析入口。"""

    return await analyze_candidate(
        resume_file=resume_file,
        jd_text=jd_text,
        candidate_id=user_id,
        session_id=session_id,
    )


@app.post("/knowledge/ingest")
def ingest_knowledge() -> dict:
    """导入 data/knowledge_base 到向量数据库。"""

    return ingest_knowledge_base()


@app.get("/memory/{user_id}")
def get_memory(user_id: str) -> dict:
    """查看用户画像、历史匹配记录和语义记忆摘要。"""

    return get_memory_service().get_user_memory(user_id)


@app.delete("/memory/{user_id}")
def delete_memory(user_id: str) -> dict:
    """清除指定用户的长期记忆和语义记忆。"""

    get_memory_service().clear_user_memory(user_id)
    return {"deleted": True, "user_id": user_id}
