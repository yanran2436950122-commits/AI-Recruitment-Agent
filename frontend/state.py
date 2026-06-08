"""Streamlit 前端状态和 Actor Context 管理。"""

from typing import Dict

import streamlit as st

from frontend.config import NAVIGATION_PAGES
from frontend import legacy


def initialize_app_state() -> None:
    """初始化 session_state、恢复 UI 状态并保证 current_page 有默认值。"""

    legacy.initialize_identity_state()
    st.session_state.setdefault("current_page", "新建分析")
    normalize_current_page()


def get_actor_type() -> str:
    """读取当前 actor_type。"""

    return str(st.session_state.get("actor_type") or "candidate")


def set_actor_type(actor_type: str) -> None:
    """切换 actor_type，并只清理对方的 UI 临时选择。"""

    legacy.switch_actor_context(actor_type)
    normalize_current_page()


def get_candidate_context() -> Dict[str, str]:
    """构造干净的 Candidate Context。"""

    return legacy.build_candidate_context_from_session()


def get_hr_context() -> Dict[str, str]:
    """构造干净的 HR Context。"""

    return legacy.build_hr_context_from_session()


def clear_invalid_context_on_actor_switch(actor_type: str) -> None:
    """actor 切换时清理无效 UI 临时字段，不删除持久身份数据。"""

    legacy.switch_actor_context(actor_type)


def restore_ui_state() -> None:
    """从 UIStateService 恢复状态，兼容旧调用。"""

    legacy.initialize_identity_state()


def save_ui_state() -> None:
    """保存当前 UI 业务关键状态。"""

    legacy.persist_ui_state()


def normalize_current_page() -> None:
    """确保 current_page 合法，非法时回到新建分析。"""

    if st.session_state.get("current_page") not in NAVIGATION_PAGES:
        st.session_state["current_page"] = "新建分析"
