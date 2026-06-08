"""Streamlit 前端应用入口。"""

import streamlit as st

st.set_page_config(
    page_title="AI Recruitment Agent",
    page_icon="🤖",
    layout="wide",
)

from frontend.layout import render_app
from frontend.state import initialize_app_state


def main() -> None:
    """初始化应用状态并渲染前端应用。"""

    initialize_app_state()
    render_app()
