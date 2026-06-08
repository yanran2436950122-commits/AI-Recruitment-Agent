"""Streamlit 前端整体布局。"""

import streamlit as st

from frontend.components.sidebar import render_sidebar
from frontend.navigation import render_navigation
from frontend.pages import debug, history, job_management, knowledge_base, monitoring, new_analysis, target_roles


def render_app() -> None:
    """渲染侧边栏、导航和当前页面。"""

    st.title("AI Recruitment Agent")
    with st.sidebar:
        identity_config, llm_config = render_sidebar()
        st.divider()
        st.header("导航")
    current_page = render_navigation()
    if current_page == "历史分析":
        history.render_page(identity_config)
    elif current_page == "岗位管理 / 目标岗位管理":
        if identity_config.get("actor_type") == "hr":
            job_management.render_page(identity_config)
        else:
            target_roles.render_page(identity_config)
    elif current_page == "知识库":
        knowledge_base.render_page()
    elif current_page == "监控中心":
        monitoring.render_page()
    elif current_page == "调试信息":
        debug.render_page(identity_config)
    else:
        new_analysis.render_page(identity_config, llm_config)
