"""简历 fingerprint hash 稳定性与反向保护测试。"""

from pathlib import Path

from agents.resume_agent import ResumeAgent
from services.file_storage_service import FileStorageService
from tests.document_fixtures import write_demo_docx, write_demo_pdf
from tools.score_tool import parse_profile, parse_profile_with_audit
from utils.fingerprint_debug_export import build_fingerprint_payload_compare_rows
from utils.hash_utils import build_resume_fingerprint, normalize_resume_fingerprint


STABLE_RESUME_TEXT = "\n".join(
    [
        "Name: Stable Candidate",
        "Email: Stable.Candidate@Example.COM",
        "Phone: 138-0000-1234",
        "Company: Alpha AI Lab",
        "Project: Agent Platform",
        "Skills: Python FastAPI RAG LangGraph",
        "Education: BSc Computer Science",
    ]
)
"""跨格式测试使用的稳定英文简历样例。"""


def test_same_docx_uploaded_twice_has_same_fingerprint_payload_and_hash(tmp_path: Path, monkeypatch) -> None:
    """同一份 DOCX 连续上传两次时，强指纹载荷和 Hash 必须一致。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    first_path = tmp_path / "run1" / "resume.docx"
    second_path = tmp_path / "run2" / "resume.docx"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    write_demo_docx(first_path, STABLE_RESUME_TEXT)
    write_demo_docx(second_path, STABLE_RESUME_TEXT)
    agent = build_resume_agent(tmp_path)

    first = run_resume_agent(agent, first_path, "resume.docx")
    second = run_resume_agent(agent, second_path, "resume.docx")

    assert first["fingerprint_payload_used_for_hash"] == second["fingerprint_payload_used_for_hash"]
    assert first["fingerprint_payload_json_used_for_hash"] == second["fingerprint_payload_json_used_for_hash"]
    assert first["resume_fingerprint_hash"] == second["resume_fingerprint_hash"]
    assert first["resume_hash"] == second["resume_hash"]
    assert first["resume_hash_source"] == "sha256(fingerprint_payload_json_used_for_hash)"
    assert first["field_extraction_audit"]["phone"]["extracted_value"] == "13800001234"
    assert first["field_extraction_audit"]["name"]["extracted_value"] == "Stable Candidate"


def test_same_content_pdf_and_docx_have_same_fingerprint_payload_and_hash(tmp_path: Path, monkeypatch) -> None:
    """同内容 PDF 与 DOCX 的强指纹载荷和 Hash 必须一致。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    pdf_path = tmp_path / "resume.pdf"
    docx_path = tmp_path / "resume.docx"
    write_demo_pdf(pdf_path, STABLE_RESUME_TEXT)
    write_demo_docx(docx_path, STABLE_RESUME_TEXT)
    agent = build_resume_agent(tmp_path)

    pdf_state = run_resume_agent(agent, pdf_path, "resume.pdf")
    docx_state = run_resume_agent(agent, docx_path, "resume.docx")

    assert pdf_state["fingerprint_payload_used_for_hash"] == docx_state["fingerprint_payload_used_for_hash"]
    assert pdf_state["resume_fingerprint_hash"] == docx_state["resume_fingerprint_hash"]
    assert pdf_state["resume_hash"] == docx_state["resume_hash"]
    assert pdf_state["field_extraction_audit"]["phone"]["extracted_value"] == docx_state["field_extraction_audit"]["phone"]["extracted_value"]
    assert pdf_state["field_extraction_audit"]["name"]["extracted_value"] == docx_state["field_extraction_audit"]["name"]["extracted_value"]


def test_dates_are_not_extracted_as_phone() -> None:
    """日期、年月和项目时间不得被误识别为 phone。"""

    text = "\n".join(
        [
            "Name: Date Candidate",
            "Project: Risk Engine 2020-07 至 2019/07",
            "Experience: 07/2019 - 08/2021",
            "Skills: Python FastAPI",
        ]
    )
    profile, audit = parse_profile_with_audit(text)

    assert profile["phone"] == ""
    assert audit["phone"]["extracted_value"] == ""
    assert any(candidate["value"] == "072019" for candidate in audit["phone"]["candidate_values"])
    assert "未找到高置信手机号" in audit["phone"]["reject_reason"] or "疑似年月日期" in audit["phone"]["reject_reason"]


def test_only_skills_change_does_not_change_fingerprint_hash() -> None:
    """只修改 skills 时，强指纹载荷和 Hash 不应变化。"""

    base = stable_resume_info()
    changed = {**base, "skills": ["Java", "Kubernetes"]}

    assert normalize_resume_fingerprint(base)["fingerprint_payload_used_for_hash"] == normalize_resume_fingerprint(changed)["fingerprint_payload_used_for_hash"]
    assert build_resume_fingerprint(base) == build_resume_fingerprint(changed)
    assert normalize_resume_fingerprint(base)["fingerprint_debug_payload_not_used_for_hash"] != normalize_resume_fingerprint(changed)["fingerprint_debug_payload_not_used_for_hash"]


def test_only_education_change_does_not_change_fingerprint_hash() -> None:
    """只修改 education 时，resume_fingerprint_hash 不应变化。"""

    base = stable_resume_info()
    changed = {**base, "education": ["MSc AI"]}

    assert build_resume_fingerprint(base) == build_resume_fingerprint(changed)


def test_email_change_changes_fingerprint_hash() -> None:
    """修改 email 时，强指纹载荷和 Hash 必须变化。"""

    base = stable_resume_info()
    changed = {**base, "email": "other@example.com"}

    assert normalize_resume_fingerprint(base)["fingerprint_payload_used_for_hash"] != normalize_resume_fingerprint(changed)["fingerprint_payload_used_for_hash"]
    assert build_resume_fingerprint(base) != build_resume_fingerprint(changed)


def test_phone_change_changes_fingerprint_hash() -> None:
    """修改 phone 时，强指纹载荷和 Hash 必须变化。"""

    base = stable_resume_info()
    changed = {**base, "phone": "139-0000-1234"}

    assert normalize_resume_fingerprint(base)["fingerprint_payload_used_for_hash"] != normalize_resume_fingerprint(changed)["fingerprint_payload_used_for_hash"]
    assert build_resume_fingerprint(base) != build_resume_fingerprint(changed)


def test_real_phone_change_after_profile_parse_changes_fingerprint_hash() -> None:
    """解析出的真实手机号变化时，fingerprint_hash 必须变化。"""

    first = parse_profile(STABLE_RESUME_TEXT)
    second = parse_profile(STABLE_RESUME_TEXT.replace("138-0000-1234", "139-0000-1234"))

    assert first["phone"] == "13800001234"
    assert second["phone"] == "13900001234"
    assert build_resume_fingerprint(first) != build_resume_fingerprint(second)


def test_project_names_change_changes_fingerprint_hash() -> None:
    """修改 project_names 时，resume_fingerprint_hash 必须变化。"""

    base = stable_resume_info()
    changed = {**base, "project_names": ["Different Platform"]}

    assert build_resume_fingerprint(base) != build_resume_fingerprint(changed)


def test_low_confidence_empty_identity_fields_do_not_deduplicate_files(tmp_path: Path) -> None:
    """稳定身份字段不足时标记低置信度，并禁止用空载荷强去重。"""

    service = build_service(tmp_path)
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("Python FastAPI backend service with API delivery.", encoding="utf-8")
    second.write_text("Java Spring payment platform with batch jobs.", encoding="utf-8")
    first_info = {"name": "", "email": "", "phone": "", "work_companies": [], "project_names": []}
    second_info = {"name": "", "email": "", "phone": "", "work_companies": [], "project_names": []}
    first_normalized = normalize_resume_fingerprint(first_info)
    second_normalized = normalize_resume_fingerprint(second_info)

    first_record = service.save_uploaded_file(
        source_path=str(first),
        analysis_id="analysis_low_1",
        actor_type="candidate",
        original_filename="first.txt",
        resume_hash=build_resume_fingerprint(first_info),
        resume_fingerprint_hash=build_resume_fingerprint(first_info),
        fingerprint_confidence=first_normalized["fingerprint_confidence"],
        candidate_id="candidate_low_confidence",
    )
    second_record = service.save_uploaded_file(
        source_path=str(second),
        analysis_id="analysis_low_2",
        actor_type="candidate",
        original_filename="second.txt",
        resume_hash=build_resume_fingerprint(second_info),
        resume_fingerprint_hash=build_resume_fingerprint(second_info),
        fingerprint_confidence=second_normalized["fingerprint_confidence"],
        candidate_id="candidate_low_confidence",
    )

    assert first_normalized["fingerprint_confidence"] == "low"
    assert second_normalized["fingerprint_confidence"] == "low"
    assert first_record["file_id"] != second_record["file_id"]
    assert first_record["dedup_hit"] is False
    assert second_record["dedup_hit"] is False


def test_fingerprint_payload_compare_rows_show_field_level_differences() -> None:
    """Excel 导出前的对比行应展示强字段、调试字段和 Hash 结果。"""

    rows = build_fingerprint_payload_compare_rows(
        {"resume_info": stable_resume_info()},
        {"resume_info": {**stable_resume_info(), "skills": ["Java"]}},
    )
    row_by_field = {row["field"]: row for row in rows}

    assert row_by_field["name"]["used_for_hash"] is True
    assert row_by_field["skills"]["used_for_hash"] is False
    assert row_by_field["skills"]["equal"] is False
    assert row_by_field["resume_fingerprint_hash"]["equal"] is True


def stable_resume_info() -> dict:
    """返回稳定字段完整的结构化简历样例。"""

    return {
        "name": "Stable Candidate",
        "email": "stable.candidate@example.com",
        "phone": "13800001234",
        "work_companies": ["Alpha AI Lab"],
        "project_names": ["Agent Platform"],
        "skills": ["Python", "FastAPI"],
        "education": ["BSc Computer Science"],
    }


def build_resume_agent(tmp_path: Path) -> ResumeAgent:
    """构造使用临时文件生命周期目录的 ResumeAgent。"""

    agent = ResumeAgent()
    agent.file_storage_service = build_service(tmp_path)
    return agent


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


def run_resume_agent(agent: ResumeAgent, path: Path, filename: str) -> dict:
    """运行 ResumeAgent 并返回状态。"""

    return agent.run(
        {
            "resume_file_path": str(path),
            "resume_file_name": filename,
            "original_filename": filename,
            "actor_type": "candidate",
            "candidate_id": "candidate_stability",
            "session_id": "session_stability",
        }
    )
