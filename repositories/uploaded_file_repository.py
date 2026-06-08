"""上传文件 metadata Repository，隔离 JSON fallback 存储细节。"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from app.config import MEMORY_DIR


logger = logging.getLogger(__name__)


class UploadedFileRepository:
    """负责 uploaded_files metadata 的保存、查询和状态更新。"""

    def __init__(self, metadata_path: Path = None) -> None:
        """初始化 metadata JSON fallback 文件路径。"""

        self.metadata_path = metadata_path or MEMORY_DIR / "uploaded_files.json"
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("uploaded_files 使用本地 JSON fallback：%s", self.metadata_path)

    def save(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """保存或替换单条上传文件 metadata。"""

        data = self._load()
        files = data.setdefault("uploaded_files", [])
        files[:] = [item for item in files if item.get("file_id") != metadata.get("file_id")]
        files.append(metadata)
        self._save(data)
        return metadata

    def get_by_id(self, file_id: str) -> Dict[str, Any]:
        """按 file_id 读取上传文件 metadata。"""

        for item in self._load().get("uploaded_files", []):
            if item.get("file_id") == file_id:
                return item
        return {}

    def list_by_owner(
        self,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        status: str = "",
    ) -> List[Dict[str, Any]]:
        """按租户读取上传文件 metadata 列表。"""

        items = list(self._load().get("uploaded_files", []))
        if actor_type:
            items = [item for item in items if item.get("actor_type") == actor_type]
        if actor_type == "candidate":
            items = [item for item in items if item.get("candidate_id") == candidate_id]
        if actor_type == "hr":
            items = [item for item in items if item.get("company_id") == company_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return items

    def list_all(self) -> List[Dict[str, Any]]:
        """读取所有上传文件 metadata，供生命周期清理任务使用。"""

        return list(self._load().get("uploaded_files", []))

    def replace_all(self, items: List[Dict[str, Any]]) -> None:
        """整体替换上传文件 metadata 列表，供批量清理状态更新使用。"""

        self._save({"uploaded_files": list(items or [])})

    def find_active_by_hash(
        self,
        actor_type: str,
        resume_hash: str,
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
    ) -> Dict[str, Any]:
        """在同一租户下查找相同 resume_fingerprint_hash 的 active 文件。"""

        if not resume_hash:
            return {}
        for item in self.list_by_owner(actor_type, candidate_id, company_id, status="active"):
            if actor_type == "hr" and job_id and item.get("job_id") != job_id:
                continue
            if (item.get("resume_fingerprint_hash") or item.get("resume_hash")) == resume_hash:
                return item
        return {}

    def update_status(
        self,
        file_id: str,
        status: str,
        extra: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """更新上传文件状态并返回更新后的 metadata。"""

        data = self._load()
        for item in data.get("uploaded_files", []):
            if item.get("file_id") == file_id:
                item["status"] = status
                item.update(extra or {})
                self._save(data)
                return item
        return {}

    def soft_delete(self, file_id: str, extra: Dict[str, Any] = None) -> Dict[str, Any]:
        """软删除上传文件 metadata。"""

        return self.update_status(file_id, "deleted", extra=extra)

    def _load(self) -> Dict[str, Any]:
        """读取 uploaded_files JSON fallback。"""

        if not self.metadata_path.exists():
            return {"uploaded_files": []}
        try:
            data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("uploaded_files JSON 损坏，已降级为空集合：%s", self.metadata_path)
            return {"uploaded_files": []}
        data.setdefault("uploaded_files", [])
        return data

    def _save(self, data: Dict[str, Any]) -> None:
        """写入 uploaded_files JSON fallback。"""

        self.metadata_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
