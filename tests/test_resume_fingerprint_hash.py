"""结构化简历指纹 Hash 测试。"""

from pathlib import Path

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService
from services.file_storage_service import FileStorageService
from tools.score_tool import parse_profile
from utils.hash_utils import build_raw_text_hash, build_resume_fingerprint, normalize_resume_fingerprint


PDF_LIKE_TEXT = """
姓名 张三
电话 138-0000-
1234
邮箱 zhangsan@example.com
技能 Python FastAPI LangGraph RAG Docker
• 主导核心业务系统的架构设计与核心
开发。
""".strip()
"""模拟 PDF 解析后的断行文本。"""

DOCX_LIKE_TEXT = """
姓名 张三
电话 138-0000-1234
邮箱 zhangsan@example.com
技能 Docker RAG LangGraph FastAPI Python
 主导核心业务系统的架构设计与核心开发。
""".strip()
"""模拟 DOCX 解析后的表格/项目符号文本。"""


def test_same_content_pdf_docx_fingerprint_should_be_same() -> None:
    """同内容 PDF-like 与 DOCX-like 简历应生成相同 resume_fingerprint_hash。"""

    pdf_fingerprint = build_resume_fingerprint(parse_profile(PDF_LIKE_TEXT))
    docx_fingerprint = build_resume_fingerprint(parse_profile(DOCX_LIKE_TEXT))

    assert pdf_fingerprint == docx_fingerprint


def test_normalize_resume_fingerprint_rules() -> None:
    """fingerprint payload 应规范化电话、邮箱、文本和列表字段。"""

    payloads = normalize_resume_fingerprint(
        {
            "name": " 张　三 ",
            "email": " ZhangSan@Example.COM ",
            "phone": "138-0000-\n1234",
            "work_companies": [" B 公司 ", "A公司", "B 公司"],
            "project_names": [" 核心 项目", "核心项目"],
            "skills": ["Python", "python", "RAG"],
            "education": [" 本科 ", "本科"],
        }
    )

    assert payloads["fingerprint_payload"] == {
        "name": "张三",
        "email": "zhangsan@example.com",
        "phone": "13800001234",
        "work_companies": ["a公司", "b公司"],
        "project_names": ["核心项目"],
    }
    assert payloads["fingerprint_debug_payload"] == {
        "skills": ["python", "rag"],
        "education": ["本科"],
    }


def test_skills_and_education_do_not_change_fingerprint_hash() -> None:
    """skills 和 education 只进入 debug payload，不影响强 fingerprint hash。"""

    base = {
        "name": "张三",
        "email": "zhangsan@example.com",
        "phone": "13800001234",
        "work_companies": ["A公司"],
        "project_names": ["核心项目"],
        "skills": ["Python"],
        "education": ["本科"],
    }
    changed_debug_only = {
        **base,
        "skills": ["Java", "Kubernetes"],
        "education": ["硕士"],
    }

    assert build_resume_fingerprint(base) == build_resume_fingerprint(changed_debug_only)


def test_raw_text_hash_can_differ_when_fingerprint_same() -> None:
    """原始文本 Hash 可不同，但结构化简历指纹应相同。"""

    assert build_raw_text_hash(PDF_LIKE_TEXT) != build_raw_text_hash(DOCX_LIKE_TEXT)
    assert build_resume_fingerprint(parse_profile(PDF_LIKE_TEXT)) == build_resume_fingerprint(parse_profile(DOCX_LIKE_TEXT))


def test_resume_hash_equals_resume_fingerprint_hash(tmp_path: Path, monkeypatch) -> None:
    """工作流输出中 resume_hash 必须等于 resume_fingerprint_hash。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(PDF_LIKE_TEXT, encoding="utf-8")
    role = TenantMemoryService().create_candidate_target_role("candidate_fingerprint_equal", "AI Agent 工程师")

    state = ManagerAgent().run(
        resume_file_path=str(resume_path),
        resume_file_name="resume.txt",
        jd_text="招聘 Python FastAPI LangGraph RAG Docker 工程师，要求有核心系统开发经验。",
        candidate_id="candidate_fingerprint_equal",
        session_id="session_fingerprint_equal",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert state["resume_hash"] == state["resume_fingerprint_hash"]
    assert state["resume_hash"] == build_resume_fingerprint(state["resume_info"])
    assert state["debug_trace"]["resume_fingerprint_hash"] == state["resume_fingerprint_hash"]
    assert state["debug_trace"]["fingerprint_payload"] == state["fingerprint_payload"]
    assert state["debug_trace"]["field_extraction_audit"]["phone"]["extracted_value"] == "13800001234"
    assert state["debug_trace"]["field_extraction_audit"]["name"]["extracted_value"] == "张三"


def test_file_dedup_uses_resume_fingerprint_hash(tmp_path: Path) -> None:
    """文件去重应使用 resume_fingerprint_hash，而不是 raw/canonical 文本 Hash。"""

    service = build_service(tmp_path)
    pdf_source = write_file(tmp_path, "resume_pdf.txt", PDF_LIKE_TEXT)
    docx_source = write_file(tmp_path, "resume_docx.txt", DOCX_LIKE_TEXT)
    fingerprint = build_resume_fingerprint(parse_profile(PDF_LIKE_TEXT))

    first = service.save_uploaded_file(
        source_path=str(pdf_source),
        analysis_id="analysis_pdf",
        actor_type="candidate",
        original_filename="resume.pdf",
        resume_hash=fingerprint,
        raw_text_hash=build_raw_text_hash(PDF_LIKE_TEXT),
        canonical_text_hash="canonical_pdf",
        resume_fingerprint_hash=fingerprint,
        candidate_id="candidate_fingerprint_dedup",
    )
    second = service.save_uploaded_file(
        source_path=str(docx_source),
        analysis_id="analysis_docx",
        actor_type="candidate",
        original_filename="resume.docx",
        resume_hash=fingerprint,
        raw_text_hash=build_raw_text_hash(DOCX_LIKE_TEXT),
        canonical_text_hash="canonical_docx",
        resume_fingerprint_hash=fingerprint,
        candidate_id="candidate_fingerprint_dedup",
    )

    assert first["file_id"] == second["file_id"]
    assert second["dedup_hit"] is True
    assert second["dedup_source_file_id"] == first["file_id"]
    assert second["canonical_text_hash"] == "canonical_docx"
    assert len(list((tmp_path / "uploads").rglob("*.*"))) == 1


def test_analysis_id_still_unique_when_fingerprint_dedup_hit(tmp_path: Path, monkeypatch) -> None:
    """同一指纹简历重复分析时应复用 file_id，但 analysis_id 必须唯一。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    first_resume = write_file(tmp_path, "first.txt", PDF_LIKE_TEXT)
    second_resume = write_file(tmp_path, "second.txt", DOCX_LIKE_TEXT)
    role = TenantMemoryService().create_candidate_target_role("candidate_fingerprint_unique", "AI Agent 工程师")
    manager = ManagerAgent()

    first = manager.run(
        resume_file_path=str(first_resume),
        resume_file_name="first.pdf",
        original_filename="first.pdf",
        jd_text="招聘 Python FastAPI LangGraph RAG Docker 工程师，要求有核心系统开发经验。",
        candidate_id="candidate_fingerprint_unique",
        session_id="session_fingerprint_unique",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )
    second = manager.run(
        resume_file_path=str(second_resume),
        resume_file_name="second.docx",
        original_filename="second.docx",
        jd_text="招聘 Python FastAPI LangGraph RAG Docker 工程师，要求有核心系统开发经验。",
        candidate_id="candidate_fingerprint_unique",
        session_id="session_fingerprint_unique",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    assert first["analysis_id"] != second["analysis_id"]
    assert first["file_id"] == second["file_id"]
    assert first["resume_fingerprint_hash"] == second["resume_fingerprint_hash"]
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
