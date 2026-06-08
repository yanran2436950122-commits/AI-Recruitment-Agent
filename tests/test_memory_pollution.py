"""记忆层污染防护测试。"""

from pathlib import Path

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService
from memory.postgres_memory import PostgresMemory
from memory.redis_memory import RedisMemory
from tests.document_fixtures import write_demo_docx, write_demo_pdf
from utils.hash_utils import build_resume_fingerprint


RESUMES = [
    (
        "a.pdf",
        "Candidate: Alpha\nSkills: Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker.\n"
        "Project: Built recruitment scoring workflow, document parsing, analysis records, and debug trace.\n"
        "Impact: Improved AI recruitment consistency and protected session memory isolation.\n",
    ),
    (
        "b.docx",
        "Candidate: Beta\nSkills: Java, Spring, Kubernetes, AWS, Microservice, Linux, Git.\n"
        "Project: Built backend platform services, deployment automation, and reliability tooling.\n"
        "Impact: Improved service scalability and incident response quality.\n",
    ),
    (
        "c.pdf",
        "Candidate: Gamma\nSkills: Python, Docker, Kubernetes, PostgreSQL, Redis, Chroma, Milvus.\n"
        "Project: Built vector database retrieval, RAG pipelines, and Streamlit analysis console.\n"
        "Impact: Improved interview question generation and recruitment report quality.\n",
    ),
]

JD_TEXT = (
    "Need backend and AI platform engineer with Python, FastAPI, LangGraph, RAG, Redis, "
    "PostgreSQL, Docker, Java, Spring, Kubernetes, AWS, Microservice, Chroma, and Milvus."
)

FORBIDDEN_SESSION_KEYS = {
    "resume_text",
    "resume_info",
    "match_score",
    "match_reason",
    "missing_skills",
    "optimized_resume",
}


def test_continuous_uploads_keep_memory_and_analysis_records_isolated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """连续上传 A、B、C 时，分析编号、简历哈希和 Session Memory 不应互相污染。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    manager = ManagerAgent()
    session_id = "memory_pollution_session"
    candidate_id = "candidate_memory_pollution"
    role = TenantMemoryService().create_candidate_target_role(
        candidate_id=candidate_id,
        role_name="AI 平台工程师",
    )
    results = []

    for filename, text in RESUMES:
        path = tmp_path / filename
        if path.suffix == ".docx":
            write_demo_docx(path, text)
        else:
            write_demo_pdf(path, text)
        results.append(
            manager.run(
                resume_file_path=str(path),
                jd_text=JD_TEXT,
                candidate_id=candidate_id,
                session_id=session_id,
                target_role_id=role["target_role_id"],
                role_name=role["role_name"],
            )
        )

    analysis_ids = [result["analysis_id"] for result in results]
    resume_hashes = [result["resume_hash"] for result in results]
    assert len(set(analysis_ids)) == 3
    assert len(set(resume_hashes)) == 3
    for result in results:
        assert result["resume_hash"] == build_resume_fingerprint(result["resume_info"])
        assert result["resume_hash"] == result["resume_fingerprint_hash"]
        assert result["debug_trace"]["analysis_id"] == result["analysis_id"]
        assert result["debug_trace"]["resume_hash"] == result["resume_hash"]

    session_memory = RedisMemory().get_session(session_id) or {}
    assert session_memory["current_analysis_id"] == analysis_ids[-1]
    assert not FORBIDDEN_SESSION_KEYS.intersection(session_memory)

    records = PostgresMemory().get_analysis_records(candidate_id=candidate_id, limit=10)
    record_ids = {record.get("analysis_id") for record in records}
    assert set(analysis_ids).issubset(record_ids)
