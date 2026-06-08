"""上传文件 resume_hash 去重测试。"""

from pathlib import Path

from memory.memory_service import MemoryService
from services.file_storage_service import FileStorageService


def test_same_tenant_same_resume_hash_reuses_active_file(tmp_path: Path) -> None:
    """同一 Candidate 重复上传同一份简历时应复用 active file_id。"""

    service = build_service(tmp_path)
    first_source = write_resume(tmp_path, "first.txt")
    second_source = write_resume(tmp_path, "second.txt")

    first = service.save_uploaded_file(
        source_path=str(first_source),
        analysis_id="analysis_first",
        actor_type="candidate",
        original_filename="first.txt",
        resume_hash="samehash123456",
        candidate_id="candidate_dedup",
    )
    second = service.save_uploaded_file(
        source_path=str(second_source),
        analysis_id="analysis_second",
        actor_type="candidate",
        original_filename="second.txt",
        resume_hash="samehash123456",
        candidate_id="candidate_dedup",
    )

    stored_files = list((tmp_path / "uploads").rglob("*.txt"))

    assert second["file_id"] == first["file_id"]
    assert second["duplicate_reused"] is True
    assert len(stored_files) == 1


def test_same_hash_across_tenants_does_not_reuse_file(tmp_path: Path) -> None:
    """不同租户即使 resume_hash 相同也不能复用原始文件。"""

    service = build_service(tmp_path)
    first_source = write_resume(tmp_path, "candidate_a.txt")
    second_source = write_resume(tmp_path, "candidate_b.txt")

    first = service.save_uploaded_file(
        source_path=str(first_source),
        analysis_id="analysis_a",
        actor_type="candidate",
        original_filename="candidate_a.txt",
        resume_hash="samehash123456",
        candidate_id="candidate_a",
    )
    second = service.save_uploaded_file(
        source_path=str(second_source),
        analysis_id="analysis_b",
        actor_type="candidate",
        original_filename="candidate_b.txt",
        resume_hash="samehash123456",
        candidate_id="candidate_b",
    )

    assert second["file_id"] != first["file_id"]


def test_delete_one_analysis_keeps_shared_file_active(tmp_path: Path) -> None:
    """多个 analysis_id 引用同一 file_id 时，删除其中一个不应删除共享文件。"""

    file_service = build_service(tmp_path)
    source = write_resume(tmp_path, "shared.txt")
    metadata = file_service.save_uploaded_file(
        source_path=str(source),
        analysis_id="analysis_shared_a",
        actor_type="candidate",
        original_filename="shared.txt",
        resume_hash="sharedhash123",
        candidate_id="candidate_shared_file",
    )
    memory_service = MemoryService()
    memory_service.file_storage_service = file_service
    for analysis_id in ["analysis_shared_a", "analysis_shared_b"]:
        memory_service.analysis_record_repository.save(
            {
                "analysis_id": analysis_id,
                "actor_type": "candidate",
                "candidate_id": "candidate_shared_file",
                "file_id": metadata["file_id"],
                "resume_hash": "sharedhash123",
                "status": "active",
            }
        )

    deleted = memory_service.delete_analysis_record(
        analysis_id="analysis_shared_a",
        actor_type="candidate",
        candidate_id="candidate_shared_file",
    )
    loaded = file_service.get_file_metadata(
        metadata["file_id"],
        actor_type="candidate",
        candidate_id="candidate_shared_file",
    )

    assert deleted is True
    assert loaded["status"] == "active"


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


def write_resume(tmp_path: Path, filename: str) -> Path:
    """写入测试简历源文件。"""

    path = tmp_path / filename
    path.write_text("Python FastAPI LangGraph RAG 项目经历 招聘系统", encoding="utf-8")
    return path
