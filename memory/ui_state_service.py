"""Streamlit 前端业务关键状态持久化服务。"""

from typing import Any, Dict

from repositories.ui_state_repository import UIStateRepository


UI_STATE_KEYS = {
    "actor_type",
    "candidate_id",
    "company_id",
    "selected_target_role_id",
    "selected_job_id",
    "current_analysis_id",
    "current_page",
    "task_status",
}
"""允许持久化的前端业务关键状态字段。"""


class UIStateService:
    """负责保存和恢复 Streamlit 刷新后仍应保留的业务状态。"""

    def __init__(self) -> None:
        """初始化 UI 状态 Repository，并保留 loaded_from 调试字段。"""

        self.repository = UIStateRepository()
        self.loaded_from = "new"

    def save_ui_state(self, session_id: str, state: Dict[str, Any]) -> str:
        """保存指定 session_id 下的前端业务关键状态。"""

        if not session_id:
            return "new"
        saved_to = self.repository.save(session_id, self._sanitize_state(state))
        self.loaded_from = saved_to
        return saved_to

    def load_ui_state(self, session_id: str) -> Dict[str, Any]:
        """根据 session_id 恢复前端业务关键状态。"""

        if not session_id:
            self.loaded_from = "new"
            return {}
        state = self.repository.get_by_id(session_id)
        self.loaded_from = self.repository.loaded_from
        return self._sanitize_state(state)

    def clear_ui_state(self, session_id: str) -> None:
        """清除指定 session_id 下的前端业务关键状态。"""

        self.repository.delete(session_id)

    def get_last_session_id(self) -> str:
        """读取最近一次保存的 session_id，用于缺少 query params 时恢复。"""

        return self.repository.get_last_session_id()

    def _sanitize_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """只保留允许持久化的业务关键状态字段。"""

        return {
            key: str(value)
            for key, value in (state or {}).items()
            if key in UI_STATE_KEYS and value not in (None, "")
        }
