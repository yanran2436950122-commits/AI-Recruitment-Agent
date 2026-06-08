"""新建分析页面。"""

import streamlit as st

from frontend import legacy
from frontend.services import api_client
from graph.state import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_GENERATING


def render_page(identity_config: dict, llm_config: dict) -> None:
    """渲染 Candidate/HR 新建分析页面。"""

    with st.sidebar:
        st.divider()
        resume_file, jd_text, submitted = legacy.render_input_sidebar(identity_config)
    if not submitted:
        legacy.render_empty_state()
        return
    if resume_file is None:
        st.error("请先上传 PDF、DOCX 或 TXT 简历。")
        return
    if not jd_text.strip():
        st.error("请先输入岗位 JD。")
        return
    legacy.configure_llm_environment(llm_config)
    st.session_state["task_status"] = TASK_STATUS_GENERATING
    legacy.persist_ui_state()
    with st.spinner("智能体工作流正在分析，请稍等..."):
        resume_path = api_client.save_uploaded_resume(resume_file)
        state = api_client.analyze_by_identity(
            str(resume_path),
            jd_text,
            identity_config,
            resume_file.name,
            getattr(resume_file, "type", "") or "",
        )
    if state.get("error"):
        st.session_state["task_status"] = TASK_STATUS_FAILED
        legacy.persist_ui_state()
        st.error(state["error"])
        return
    if state.get("analysis_id"):
        st.session_state["current_analysis_id"] = state.get("analysis_id")
        st.session_state["task_status"] = state.get("task_status") or TASK_STATUS_COMPLETED
        legacy.persist_ui_state()
    legacy.render_result(state)
