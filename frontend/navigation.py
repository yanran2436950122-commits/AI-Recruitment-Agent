"""前端导航状态管理。"""

import streamlit as st

from frontend.config import NAVIGATION_PAGES
from frontend.state import normalize_current_page, save_ui_state


def get_pages_for_actor(actor_type: str) -> list:
    """返回当前 actor 可用页面列表，当前版本两种身份共用页面集合。"""

    return list(NAVIGATION_PAGES)


def set_current_page(page_name: str, rerun: bool = False) -> None:
    """统一更新 current_page 并持久化，导航点击时立即 rerun。"""

    if page_name not in NAVIGATION_PAGES:
        page_name = "新建分析"
    if st.session_state.get("current_page") == page_name:
        return
    st.session_state["current_page"] = page_name
    save_ui_state()
    if rerun:
        st.rerun()


def render_navigation() -> str:
    """渲染侧边栏导航，并确保单次点击立即切换。"""

    normalize_current_page()
    pages = get_pages_for_actor(str(st.session_state.get("actor_type") or "candidate"))
    selected = st.sidebar.radio(
        "功能中心",
        pages,
        index=pages.index(st.session_state["current_page"]) if st.session_state["current_page"] in pages else 0,
        key="nav_radio",
        label_visibility="collapsed",
    )
    if selected != st.session_state["current_page"]:
        set_current_page(selected, rerun=True)
    return st.session_state["current_page"]
