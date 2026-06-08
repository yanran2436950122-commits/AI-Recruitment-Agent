"""Streamlit 前端模块化重构验收测试。"""

import ast
import importlib
from pathlib import Path

import streamlit as st

from frontend.legacy import (
    apply_created_job_state,
    build_analysis_file_display,
    build_history_selector_key,
    sync_history_selector_state,
)
from frontend.navigation import set_current_page
from frontend.state import get_candidate_context, get_hr_context


ROOT = Path(__file__).resolve().parents[1]
"""项目根目录。"""


def test_streamlit_entry_is_thin() -> None:
    """streamlit_app.py 应只作为兼容入口且小于 20 行。"""

    path = ROOT / "streamlit_app.py"
    text = path.read_text(encoding="utf-8")

    assert len(text.splitlines()) < 20
    assert "from frontend.app import main" in text
    assert "set_page_config" not in text


def test_set_page_config_called_once() -> None:
    """全项目只能在 frontend/app.py 调用一次 set_page_config。"""

    matches = []
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        has_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "set_page_config"
            for node in ast.walk(tree)
        )
        if has_call:
            matches.append(path.relative_to(ROOT).as_posix())

    assert matches == ["frontend/app.py"]


def test_navigation_single_click() -> None:
    """导航更新应立即写入 current_page，供下一次 rerun 渲染。"""

    reset_streamlit_state()
    st.session_state["session_id"] = "session_navigation_refactor"
    st.session_state["current_page"] = "新建分析"

    set_current_page("监控中心", rerun=False)

    assert st.session_state["current_page"] == "监控中心"


def test_history_file_display_prefers_analysis_record_filename() -> None:
    """历史详情应优先展示本次 analysis 的原始文件，而不是主简历文件。"""

    record = {
        "analysis_id": "analysis_docx",
        "original_filename": "resume.docx",
        "created_at": "2026-06-06T12:03:56+00:00",
        "document_parse_result": {"file_type": "docx"},
        "resume_fingerprint_hash": "fingerprint_same",
    }
    metadata = {
        "original_filename": "resume.pdf",
        "stored_filename": "analysis_pdf_candidate_resume_fingerprint.pdf",
        "created_at": "2026-06-05T12:03:56+00:00",
        "resume_fingerprint_hash": "fingerprint_same",
    }

    display = build_analysis_file_display(record, metadata)

    assert display["analysis_original_filename"] == "resume.docx"
    assert display["analysis_file_type"] == "docx"
    assert display["canonical_original_filename"] == "resume.pdf"
    assert display["is_duplicate_resume"] is True


def test_history_selector_sync_single_click_state() -> None:
    """历史下拉变化时应立即同步 current_analysis_id。"""

    reset_streamlit_state()
    st.session_state["session_id"] = "session_history_selector"
    selector_key = build_history_selector_key("选择历史记录")
    st.session_state[selector_key] = "analysis_new"

    sync_history_selector_state(selector_key)

    assert st.session_state["current_analysis_id"] == "analysis_new"


def test_job_create_success_advances_form_version_without_clearing_selection() -> None:
    """岗位创建成功后推进表单版本以清空输入框，同时保留新选中岗位。"""

    reset_streamlit_state()
    job = {"job_id": "job_new", "job_name": "AI Agent 工程师", "jd_text": "有效 JD"}

    apply_created_job_state(job, form_version=3)

    assert st.session_state["create_job_form_version"] == 4
    assert st.session_state["selected_job_id"] == "job_new"
    assert st.session_state["selected_job_name"] == "AI Agent 工程师"
    assert "岗位创建成功" in st.session_state["job_create_success_message"]


def test_candidate_debug_context_clean() -> None:
    """Candidate Context 不应包含 company_id/job_id/job_name。"""

    reset_streamlit_state()
    st.session_state.update(
        {
            "actor_type": "candidate",
            "candidate_id": "candidate_debug",
            "selected_target_role_id": "target_debug",
            "selected_role_name": "AI Agent 工程师",
            "session_id": "session_debug",
        }
    )

    context = get_candidate_context()

    assert "company_id" not in context
    assert "job_id" not in context
    assert "job_name" not in context


def test_hr_debug_context_clean() -> None:
    """HR Context 不应包含 candidate_id/target_role_id/role_name。"""

    reset_streamlit_state()
    st.session_state.update(
        {
            "actor_type": "hr",
            "company_id": "company_debug",
            "selected_job_id": "job_debug",
            "selected_job_name": "AI Agent 工程师",
            "session_id": "session_debug",
        }
    )

    context = get_hr_context()

    assert "candidate_id" not in context
    assert "target_role_id" not in context
    assert "role_name" not in context


def test_pages_import_without_side_effects() -> None:
    """导入页面模块不应触发 set_page_config 或主流程。"""

    for module_name in [
        "frontend.pages.new_analysis",
        "frontend.pages.history",
        "frontend.pages.job_management",
        "frontend.pages.target_roles",
        "frontend.pages.knowledge_base",
        "frontend.pages.monitoring",
        "frontend.pages.debug",
    ]:
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute) and node.attr == "set_page_config"
        ]
        assert calls == []


def reset_streamlit_state() -> None:
    """清理 Streamlit session_state，避免测试串扰。"""

    for key in list(st.session_state.keys()):
        del st.session_state[key]
