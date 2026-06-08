"""前端 UI 业务关键状态 Repository，封装 Redis 和 JSON fallback。"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict

from app.config import MEMORY_DIR, REDIS_URL


logger = logging.getLogger(__name__)


class UIStateRepository:
    """负责 UI 业务关键状态的持久化和恢复。"""

    def __init__(self, fallback_dir: Path = None) -> None:
        """初始化 Redis 客户端和本地 JSON fallback 目录。"""

        self.fallback_dir = fallback_dir or MEMORY_DIR / "ui_state"
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        self.client = self._build_client()
        self.loaded_from = "new"
        if not self.client:
            logger.info("UI state 使用本地 JSON fallback：%s", self.fallback_dir)

    def save(self, session_id: str, state: Dict[str, Any]) -> str:
        """保存指定 session_id 的 UI 状态。"""

        if not session_id:
            return "new"
        if self.client:
            try:
                self.client.set(self._key(session_id), json.dumps(state, ensure_ascii=False))
                self.client.set(self._last_session_key(), session_id)
                return "redis"
            except Exception as exc:
                logger.warning("UI state Redis 写入失败，降级本地 JSON：%s", exc)
        self._write_local(session_id, state)
        self._write_last_session_id(session_id)
        return "local_json"

    def get_by_id(self, session_id: str) -> Dict[str, Any]:
        """根据 session_id 读取 UI 状态。"""

        if not session_id:
            self.loaded_from = "new"
            return {}
        if self.client:
            try:
                raw = self.client.get(self._key(session_id))
                if raw:
                    self.loaded_from = "redis"
                    data = json.loads(raw)
                    return data if isinstance(data, dict) else {}
            except Exception as exc:
                logger.warning("UI state Redis 读取失败，降级本地 JSON：%s", exc)
        data = self._read_local(session_id)
        self.loaded_from = "local_json" if data else "new"
        return data

    def delete(self, session_id: str) -> None:
        """删除指定 session_id 的 UI 状态。"""

        if not session_id:
            return
        if self.client:
            try:
                self.client.delete(self._key(session_id))
            except Exception as exc:
                logger.warning("UI state Redis 删除失败：%s", exc)
        path = self._local_path(session_id)
        if path.exists():
            path.unlink()

    def get_last_session_id(self) -> str:
        """读取最近一次保存的 session_id。"""

        if self.client:
            try:
                value = self.client.get(self._last_session_key())
                if value:
                    return str(value)
            except Exception as exc:
                logger.warning("UI state 最近会话 Redis 读取失败：%s", exc)
        path = self.fallback_dir / "last_session.json"
        if not path.exists():
            return ""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("UI state 最近会话 JSON 损坏：%s", path)
            return ""
        return str(data.get("session_id") or "")

    def _build_client(self):
        """创建 Redis 客户端，连接失败时返回 None。"""

        try:
            import redis
        except ImportError:
            return None
        try:
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            return client
        except Exception as exc:
            logger.info("UI state Redis 不可用，使用本地 JSON fallback：%s", exc)
            return None

    def _key(self, session_id: str) -> str:
        """构造 Redis UI 状态键。"""

        return f"ai_recruitment:ui_state:{session_id}"

    def _last_session_key(self) -> str:
        """构造最近会话 Redis 键。"""

        return "ai_recruitment:ui_state:last_session"

    def _safe_session_id(self, session_id: str) -> str:
        """把 session_id 转换成安全文件名。"""

        return "".join(ch for ch in session_id if ch.isalnum() or ch in "-_") or "default"

    def _local_path(self, session_id: str) -> Path:
        """构造本地 UI 状态文件路径。"""

        return self.fallback_dir / f"{self._safe_session_id(session_id)}.json"

    def _write_local(self, session_id: str, state: Dict[str, Any]) -> None:
        """写入本地 JSON UI 状态。"""

        payload = {"updated_at": time.time(), "state": state}
        self._local_path(session_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_local(self, session_id: str) -> Dict[str, Any]:
        """读取本地 JSON UI 状态。"""

        path = self._local_path(session_id)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("UI state JSON 损坏，已忽略：%s", path)
            return {}
        state = payload.get("state")
        return state if isinstance(state, dict) else {}

    def _write_last_session_id(self, session_id: str) -> None:
        """写入最近一次保存的 session_id。"""

        path = self.fallback_dir / "last_session.json"
        path.write_text(
            json.dumps({"session_id": session_id, "updated_at": time.time()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
