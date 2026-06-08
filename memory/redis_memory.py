"""Redis 会话记忆实现，连接失败时自动使用本地文件降级。"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import MEMORY_DIR, REDIS_URL


class RedisMemory:
    """用于读写短期会话记忆的适配器。"""

    def __init__(self) -> None:
        """初始化 Redis 客户端或本地降级目录。"""

        self._client = self._build_client()
        self._fallback_dir = MEMORY_DIR / "sessions"
        self._fallback_dir.mkdir(parents=True, exist_ok=True)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """根据会话编号读取当前会话记忆。"""

        if not session_id:
            return None
        if self._client:
            try:
                raw = self._client.get(self._key(session_id))
                return json.loads(raw) if raw else None
            except Exception:
                pass
        return self._read_local(session_id)

    def save_session(self, session_id: str, data: Dict[str, Any], ttl: int = 86400) -> None:
        """保存当前会话记忆，并设置默认过期时间。"""

        if not session_id:
            return
        payload = json.dumps(data, ensure_ascii=False)
        if self._client:
            try:
                self._client.setex(self._key(session_id), ttl, payload)
                return
            except Exception:
                pass
        self._write_local(session_id, data, ttl)

    def update_session(self, session_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """合并更新当前会话记忆并返回更新后的数据。"""

        current = self.get_session(session_id) or {}
        current.update(patch)
        self.save_session(session_id, current)
        return current

    def clear_session(self, session_id: str) -> None:
        """清除指定会话记忆。"""

        if not session_id:
            return
        if self._client:
            try:
                self._client.delete(self._key(session_id))
            except Exception:
                pass
        path = self._local_path(session_id)
        if path.exists():
            path.unlink()

    def _build_client(self):
        """创建 Redis 客户端，依赖不存在或连接失败时返回空值。"""

        try:
            import redis
        except ImportError:
            return None
        try:
            client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            return client
        except Exception:
            return None

    def _key(self, session_id: str) -> str:
        """构造 Redis 存储键。"""

        return f"ai_recruitment:session:{session_id}"

    def _local_path(self, session_id: str) -> Path:
        """构造本地会话记忆文件路径。"""

        safe_id = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
        return self._fallback_dir / f"{safe_id}.json"

    def _read_local(self, session_id: str) -> Optional[Dict[str, Any]]:
        """读取本地降级会话记忆。"""

        path = self._local_path(session_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        expires_at = payload.get("_expires_at")
        if expires_at and float(expires_at) < time.time():
            path.unlink()
            return None
        data = payload.get("data")
        return data if isinstance(data, dict) else None

    def _write_local(self, session_id: str, data: Dict[str, Any], ttl: int) -> None:
        """写入本地降级会话记忆。"""

        payload = {"_expires_at": time.time() + ttl, "data": data}
        self._local_path(session_id).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
