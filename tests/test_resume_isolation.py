"""同 Session 多简历上传隔离测试。"""

from pathlib import Path

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService
from tests.document_fixtures import write_demo_docx, write_demo_pdf
from utils.hash_utils import build_resume_fingerprint


RESUME_A = """
Candidate: Alice Parser
Role: AI Agent Engineer
Skills: Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker.
Project: Built resume parsing and scoring workflow for recruitment automation.
Impact: Delivered scoring trace, interview generation, and memory isolation.
Education: Computer Science.
""".strip()

RESUME_B = """
Candidate: Bob Platform
Role: Cloud Backend Engineer
Skills: Java, Spring, Kubernetes, AWS, Microservice, Linux, Git.
Project: Built cloud platform services, deployment pipelines, and production observability.
Impact: Improved service stability and reduced incident recovery time.
Education: Software Engineering.
""".strip()

JD_TEXT = (
    "Need engineer with Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker, "
    "Java, Spring, Kubernetes, AWS, microservice, Linux, and Git experience."
)


def test_same_session_resume_info_does_not_cross_pollute(tmp_path: Path, monkeypatch) -> None:
    """同一 session 连续上传 A.pdf 与 B.docx 时，B 结果不得包含 A 的简历画像。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    pdf_path = tmp_path / "alice.pdf"
    docx_path = tmp_path / "bob.docx"
    write_demo_pdf(pdf_path, RESUME_A)
    write_demo_docx(docx_path, RESUME_B)
    role = TenantMemoryService().create_candidate_target_role(
        candidate_id="candidate_isolation",
        role_name="AI Agent 工程师",
    )

    manager = ManagerAgent()
    session_id = "resume_isolation_session"
    result_a = manager.run(
        resume_file_path=str(pdf_path),
        jd_text=JD_TEXT,
        candidate_id="candidate_isolation",
        session_id=session_id,
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    result_b = manager.run(
        resume_file_path=str(docx_path),
        jd_text=JD_TEXT,
        candidate_id="candidate_isolation",
        session_id=session_id,
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert result_a["analysis_id"] != result_b["analysis_id"]
    assert result_a["resume_hash"] == build_resume_fingerprint(result_a["resume_info"])
    assert result_b["resume_hash"] == build_resume_fingerprint(result_b["resume_info"])
    assert result_b["resume_hash"] == result_b["resume_fingerprint_hash"]
    assert "Alice" in result_a["resume_text"]
    assert "Bob" in result_b["resume_text"]
    assert "Alice" not in result_b["resume_text"]
    assert "java" in [skill.lower() for skill in result_b["resume_info"]["skills"]]
    assert result_b["scoring_trace"]["resume_hash"] == result_b["resume_hash"]
    assert result_b["scoring_trace"]["resume_fingerprint_hash"] == result_b["resume_fingerprint_hash"]
    assert result_b["scoring_trace"]["resume_preview"] == result_b["resume_text"][:300]
