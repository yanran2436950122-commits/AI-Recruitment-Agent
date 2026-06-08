"""上传文件生命周期管理测试。"""

import os
import time
from pathlib import Path

from agents.manager_agent import ManagerAgent
from memory.tenant_memory_service import TenantMemoryService
from services.file_storage_service import FileStorageService


VALID_JD = (
    "岗位职责：负责 AI Agent 平台后端服务设计、开发和优化，参与 RAG 检索链路建设。"
    "任职要求：熟悉 Python、FastAPI、LangGraph、Redis、Docker，有大模型应用经验优先。"
)
"""用于测试工作流的有效 JD。"""

RESUME_TEXT = (
    "张三，AI Agent 工程师。熟悉 Python、FastAPI、LangGraph、RAG、Redis、Docker。"
    "负责过智能招聘平台、向量检索、面试题生成和监控系统建设。"
)
"""用于测试文件生命周期的简历文本。"""


def test_file_saved_with_readable_name(tmp_path: Path) -> None:
    """正式保存后的文件名应包含 analysis_id、actor_type、原始文件名和 hash。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "My Resume!.txt")

    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_20260608_abcd",
        actor_type="candidate",
        original_filename="My Resume!.txt",
        resume_hash="f3a9c812abcdef",
        candidate_id="candidate_file_name",
    )

    assert "analysis_20260608_abcd_candidate_My_Resume_f3a9c812.txt" == metadata["stored_filename"]
    assert Path(metadata["file_path"]).exists()


def test_uploaded_file_metadata_created(tmp_path: Path) -> None:
    """保存上传文件后应创建 uploaded_files metadata。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "resume.txt")

    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_metadata",
        actor_type="hr",
        original_filename="resume.txt",
        resume_hash="abc12345ffff",
        company_id="company_meta",
        job_id="job_meta",
        content_type="text/plain",
    )
    loaded = service.get_file_metadata(metadata["file_id"], actor_type="hr", company_id="company_meta")

    assert loaded["analysis_id"] == "analysis_metadata"
    assert loaded["content_type"] == "text/plain"
    assert loaded["status"] == "active"


def test_analysis_record_links_file(tmp_path: Path, monkeypatch) -> None:
    """完整分析结束后 analysis_record 应关联 file_id 和原始文件名。"""

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    resume = write_source_file(tmp_path, "candidate_resume.txt")
    service = TenantMemoryService()
    role = service.create_candidate_target_role("candidate_file_link", "AI Agent 工程师")

    state = ManagerAgent().run(
        resume_file_path=str(resume),
        resume_file_name="candidate_resume.txt",
        original_filename="candidate_resume.txt",
        jd_text=VALID_JD,
        candidate_id="candidate_file_link",
        session_id="session_file_link",
        target_role_id=role["target_role_id"],
        role_name=role["role_name"],
    )

    record = state["analysis_record"]

    assert record["file_id"]
    assert record["original_filename"] == "candidate_resume.txt"
    assert record["resume_hash"] == state["resume_hash"]


def test_tmp_file_cleanup(tmp_path: Path) -> None:
    """超过 24 小时的 tmp 文件应被清理。"""

    service = build_test_file_service(tmp_path)
    tmp_file = service.save_temp_upload(b"hello", "resume.txt")
    old_time = time.time() - 26 * 3600
    os.utime(tmp_file, (old_time, old_time))

    result = service.cleanup_expired_files()

    assert result["tmp_deleted"] == 1
    assert not tmp_file.exists()


def test_expired_file_cleanup(tmp_path: Path) -> None:
    """过期 active 文件应被删除原文件并标记为 expired。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "expired.txt")
    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_expired",
        actor_type="candidate",
        original_filename="expired.txt",
        resume_hash="expired1",
        candidate_id="candidate_expired",
        active_days=-1,
    )

    result = service.cleanup_expired_files()
    loaded = service.get_file_metadata(
        metadata["file_id"],
        actor_type="candidate",
        candidate_id="candidate_expired",
    )

    assert result["expired_files"] == 1
    assert loaded["status"] == "expired"
    assert not Path(metadata["file_path"]).exists()


def test_delete_file_soft_delete(tmp_path: Path) -> None:
    """删除文件应软删除 metadata 并移除原始文件。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "delete.txt")
    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_delete",
        actor_type="candidate",
        original_filename="delete.txt",
        resume_hash="delete12",
        candidate_id="candidate_delete",
    )

    deleted = service.mark_file_deleted(
        metadata["file_id"],
        actor_type="candidate",
        candidate_id="candidate_delete",
    )
    loaded = service.get_file_metadata(
        metadata["file_id"],
        actor_type="candidate",
        candidate_id="candidate_delete",
    )

    assert deleted is True
    assert loaded["status"] == "deleted"
    assert not Path(metadata["file_path"]).exists()


def test_candidate_cannot_access_other_file(tmp_path: Path) -> None:
    """Candidate 不能访问其他 Candidate 的文件 metadata。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "private.txt")
    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_private",
        actor_type="candidate",
        original_filename="private.txt",
        resume_hash="private1",
        candidate_id="candidate_owner",
    )

    other = service.get_file_metadata(
        metadata["file_id"],
        actor_type="candidate",
        candidate_id="candidate_other",
    )

    assert other == {}


def test_hr_cannot_access_other_company_file(tmp_path: Path) -> None:
    """HR 不能访问其他 company_id 下的文件 metadata。"""

    service = build_test_file_service(tmp_path)
    source = write_source_file(tmp_path, "hr.txt")
    metadata = service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_hr_private",
        actor_type="hr",
        original_filename="hr.txt",
        resume_hash="hrhash12",
        company_id="company_owner",
        job_id="job_owner",
    )

    other = service.get_file_metadata(
        metadata["file_id"],
        actor_type="hr",
        company_id="company_other",
    )

    assert other == {}


def build_test_file_service(tmp_path: Path) -> FileStorageService:
    """构造使用临时目录的文件生命周期服务。"""

    service = FileStorageService()
    service.upload_root = tmp_path / "uploads"
    service.tmp_dir = service.upload_root / "tmp"
    service.metadata_path = tmp_path / "memory" / "uploaded_files.json"
    service.upload_root.mkdir(parents=True, exist_ok=True)
    service.tmp_dir.mkdir(parents=True, exist_ok=True)
    service.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    return service


def write_source_file(tmp_path: Path, filename: str) -> Path:
    """写入测试源文件。"""

    path = tmp_path / filename
    path.write_text(RESUME_TEXT, encoding="utf-8")
    return path
