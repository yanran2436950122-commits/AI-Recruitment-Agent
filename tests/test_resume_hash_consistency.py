"""跨格式简历 Hash 兼容测试。"""

from pathlib import Path

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService
from services.file_storage_service import FileStorageService
from tools.score_tool import parse_profile
from utils.hash_utils import build_canonical_resume_hash, build_raw_text_hash, build_resume_fingerprint


PDF_LIKE_TEXT = """
电话 138-0000-
1234
主导核心业务系统的架构设计与核心
开发。
• 管理 6 人后端团队。
""".strip()
"""模拟 PDF 解析后的断行文本。"""

DOCX_LIKE_TEXT = """
电话 138-0000-1234
主导核心业务系统的架构设计与核心开发。
 管理 6 人后端团队。
""".strip()
"""模拟 DOCX 解析后的表格/项目符号文本。"""


def test_same_content_pdf_docx_should_have_same_canonical_resume_hash() -> None:
    """同内容 PDF-like 与 DOCX-like 文本应生成相同 canonical_resume_hash。"""

    assert build_canonical_resume_hash(PDF_LIKE_TEXT) == build_canonical_resume_hash(DOCX_LIKE_TEXT)


def test_same_content_pdf_docx_raw_text_hash_can_be_different() -> None:
    """同内容不同格式的 raw_text_hash 可以不同，这是用于调试解析差异的信号。"""

    assert build_raw_text_hash(PDF_LIKE_TEXT) != build_raw_text_hash(DOCX_LIKE_TEXT)


def test_resume_hash_equals_resume_fingerprint_hash(tmp_path: Path, monkeypatch) -> None:
    """工作流输出中 resume_hash 必须等于 resume_fingerprint_hash。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(
        "张三 Python FastAPI LangGraph RAG Redis Docker 项目经历：主导核心业务系统开发。",
        encoding="utf-8",
    )
    role = TenantMemoryService().create_candidate_target_role("candidate_hash_equal", "AI Agent 工程师")

    state = ManagerAgent().run(
        resume_file_path=str(resume_path),
        resume_file_name="resume.txt",
        jd_text="招聘 Python FastAPI LangGraph RAG Redis Docker 工程师，要求有项目开发经验。",
        candidate_id="candidate_hash_equal",
        session_id="session_hash_equal",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert state["resume_hash"] == state["resume_fingerprint_hash"]
    assert state["resume_hash"] == build_resume_fingerprint(state["resume_info"])
    assert state["canonical_text_hash"] == build_canonical_resume_hash(state["resume_text"])
    assert state["raw_text_hash"] == build_raw_text_hash(state["resume_text"])
    assert state["debug_trace"]["resume_fingerprint_hash"] == state["resume_fingerprint_hash"]


def test_file_dedup_uses_resume_fingerprint_hash(tmp_path: Path) -> None:
    """文件去重应使用 resume_fingerprint_hash，而不是 raw_text_hash。"""

    service = build_service(tmp_path)
    pdf_source = write_file(tmp_path, "resume_pdf.txt", PDF_LIKE_TEXT)
    docx_source = write_file(tmp_path, "resume_docx.txt", DOCX_LIKE_TEXT)
    fingerprint_hash = build_resume_fingerprint(parse_profile(PDF_LIKE_TEXT))

    first = service.save_uploaded_file(
        source_path=str(pdf_source),
        analysis_id="analysis_pdf",
        actor_type="candidate",
        original_filename="resume.pdf",
        resume_hash=fingerprint_hash,
        raw_text_hash=build_raw_text_hash(PDF_LIKE_TEXT),
        canonical_text_hash="canonical_pdf",
        resume_fingerprint_hash=fingerprint_hash,
        candidate_id="candidate_canonical_dedup",
    )
    second = service.save_uploaded_file(
        source_path=str(docx_source),
        analysis_id="analysis_docx",
        actor_type="candidate",
        original_filename="resume.docx",
        resume_hash=fingerprint_hash,
        raw_text_hash=build_raw_text_hash(DOCX_LIKE_TEXT),
        canonical_text_hash="canonical_docx",
        resume_fingerprint_hash=fingerprint_hash,
        candidate_id="candidate_canonical_dedup",
    )

    assert first["file_id"] == second["file_id"]
    assert second["dedup_hit"] is True
    assert second["dedup_source_file_id"] == first["file_id"]
    assert len(list((tmp_path / "uploads").rglob("*.*"))) == 1


def test_analysis_id_still_unique_when_file_dedup_hit(tmp_path: Path, monkeypatch) -> None:
    """同一 fingerprint 简历重复分析时应复用 file_id，但 analysis_id 必须保持唯一。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    first_resume = write_file(tmp_path, "first.txt", PDF_LIKE_TEXT + "\nPython FastAPI LangGraph RAG 项目经历")
    second_resume = write_file(tmp_path, "second.txt", DOCX_LIKE_TEXT + "\nPython FastAPI LangGraph RAG 项目经历")
    role = TenantMemoryService().create_candidate_target_role("candidate_analysis_unique", "AI Agent 工程师")
    manager = ManagerAgent()

    first = manager.run(
        resume_file_path=str(first_resume),
        resume_file_name="first.pdf",
        original_filename="first.pdf",
        jd_text="招聘 Python FastAPI LangGraph RAG 工程师，要求有核心系统开发经验。",
        candidate_id="candidate_analysis_unique",
        session_id="session_analysis_unique",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    second = manager.run(
        resume_file_path=str(second_resume),
        resume_file_name="second.docx",
        original_filename="second.docx",
        jd_text="招聘 Python FastAPI LangGraph RAG 工程师，要求有核心系统开发经验。",
        candidate_id="candidate_analysis_unique",
        session_id="session_analysis_unique",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert first["analysis_id"] != second["analysis_id"]
    assert first["file_id"] == second["file_id"]
    assert first["resume_hash"] == second["resume_hash"]


def build_service(tmp_path: Path) -> FileStorageService:
    """构造使用临时目录的文件生命周期服务。"""

    service = FileStorageService()
    service.upload_root = tmp_path / "uploads"
    service.tmp_dir = service.upload_root / "tmp"
    service.metadata_path = tmp_path / "memory" / "uploaded_files.json"
    service.upload_root.mkdir(parents=True, exist_ok=True)
    service.tmp_dir.mkdir(parents=True, exist_ok=True)
    service.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    return service


def write_file(tmp_path: Path, filename: str, text: str) -> Path:
    """写入测试文件。"""

    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return path
