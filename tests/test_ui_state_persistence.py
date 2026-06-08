"""Streamlit 刷新后的 UI 业务状态持久化测试。"""

import streamlit as st

from memory.tenant_memory_service import TenantMemoryService
from memory.ui_state_service import UIStateService
from frontend.legacy import (
    apply_persistent_ui_state,
    resolve_selection_index,
    resolve_startup_session_id,
    validate_restored_job_selection,
    validate_restored_target_role_selection,
)
from frontend.navigation import set_current_page
from frontend.state import normalize_current_page


VALID_JD = (
    "岗位职责：负责 AI Agent 平台后端服务设计、开发和优化，参与 RAG 检索链路建设。"
    "任职要求：熟悉 Python、FastAPI、LangGraph、Redis、Docker，有大模型应用经验优先。"
)
"""测试岗位创建时使用的有效 JD。"""


def test_refresh_preserves_candidate_id() -> None:
    """刷新恢复后 candidate_id 应保持不变。"""

    reset_streamlit_state()
    service = UIStateService()
    session_id = "session_refresh_candidate"
    service.save_ui_state(session_id, {"actor_type": "candidate", "candidate_id": "candidate_keep"})

    apply_persistent_ui_state(service.load_ui_state(session_id))

    assert st.session_state["candidate_id"] == "candidate_keep"


def test_refresh_preserves_company_id() -> None:
    """刷新恢复后 company_id 应保持不变。"""

    reset_streamlit_state()
    service = UIStateService()
    session_id = "session_refresh_company"
    service.save_ui_state(session_id, {"actor_type": "hr", "company_id": "company_keep"})

    apply_persistent_ui_state(service.load_ui_state(session_id))

    assert st.session_state["company_id"] == "company_keep"


def test_refresh_preserves_selected_job() -> None:
    """HR 选择岗位 A 后刷新，仍应恢复岗位 A。"""

    reset_streamlit_state()
    tenant_service = TenantMemoryService()
    job_a = tenant_service.create_job_profile("company_refresh_job", "AI Agent 工程师", VALID_JD)
    job_b = tenant_service.create_job_profile("company_refresh_job", "RAG 工程师", VALID_JD)
    UIStateService().save_ui_state(
        "session_refresh_job",
        {
            "actor_type": "hr",
            "company_id": "company_refresh_job",
            "selected_job_id": job_a["job_id"],
        },
    )

    apply_persistent_ui_state(UIStateService().load_ui_state("session_refresh_job"))
    jobs = tenant_service.list_job_profiles("company_refresh_job")
    index = resolve_selection_index(jobs, "job_id", "selected_job_id")

    assert jobs[index]["job_id"] == job_a["job_id"]
    assert jobs[index]["job_id"] != job_b["job_id"]


def test_refresh_preserves_selected_target_role() -> None:
    """Candidate 选择目标岗位 A 后刷新，仍应恢复目标岗位 A。"""

    reset_streamlit_state()
    tenant_service = TenantMemoryService()
    role_a = tenant_service.create_candidate_target_role("candidate_refresh_role", "AI Agent 工程师")
    role_b = tenant_service.create_candidate_target_role("candidate_refresh_role", "RAG 工程师")
    UIStateService().save_ui_state(
        "session_refresh_role",
        {
            "actor_type": "candidate",
            "candidate_id": "candidate_refresh_role",
            "selected_target_role_id": role_a["target_role_id"],
        },
    )

    apply_persistent_ui_state(UIStateService().load_ui_state("session_refresh_role"))
    roles = tenant_service.list_candidate_target_roles("candidate_refresh_role")
    index = resolve_selection_index(roles, "target_role_id", "selected_target_role_id")

    assert roles[index]["target_role_id"] == role_a["target_role_id"]
    assert roles[index]["target_role_id"] != role_b["target_role_id"]


def test_refresh_invalid_job_selection_is_cleared() -> None:
    """恢复到已停用岗位时，应清空 selected_job_id。"""

    reset_streamlit_state()
    tenant_service = TenantMemoryService()
    job = tenant_service.create_job_profile("company_invalid_refresh_job", "AI Agent 工程师", VALID_JD)
    tenant_service.deactivate_job_profile("company_invalid_refresh_job", job["job_id"])
    st.session_state["session_id"] = "session_invalid_job"
    st.session_state["actor_type"] = "hr"
    st.session_state["company_id"] = "company_invalid_refresh_job"
    st.session_state["selected_job_id"] = job["job_id"]

    validate_restored_job_selection()

    assert not st.session_state.get("selected_job_id")


def test_refresh_invalid_target_role_selection_is_cleared() -> None:
    """恢复到已停用目标岗位时，应清空 selected_target_role_id。"""

    reset_streamlit_state()
    tenant_service = TenantMemoryService()
    role = tenant_service.create_candidate_target_role("candidate_invalid_refresh_role", "AI Agent 工程师")
    tenant_service.deactivate_candidate_target_role("candidate_invalid_refresh_role", role["target_role_id"])
    st.session_state["session_id"] = "session_invalid_role"
    st.session_state["actor_type"] = "candidate"
    st.session_state["candidate_id"] = "candidate_invalid_refresh_role"
    st.session_state["selected_target_role_id"] = role["target_role_id"]

    validate_restored_target_role_selection()

    assert not st.session_state.get("selected_target_role_id")


def test_query_param_session_id_restores_state() -> None:
    """query params 中的 session_id 应优先于最近本地会话。"""

    session_id = resolve_startup_session_id(
        current_session_id="",
        query_session_id="session_from_query",
        last_session_id="session_from_last_local",
    )

    assert session_id == "session_from_query"


def test_current_page_persisted_and_restored() -> None:
    """刷新恢复后 current_page 应保持为监控中心。"""

    reset_streamlit_state()
    service = UIStateService()
    session_id = "session_refresh_page"
    service.save_ui_state(session_id, {"actor_type": "candidate", "current_page": "监控中心"})

    apply_persistent_ui_state(service.load_ui_state(session_id))

    assert st.session_state["current_page"] == "监控中心"


def test_current_analysis_status_persisted_and_restored() -> None:
    """刷新恢复后 current_analysis_id 和 task_status 应保持不变。"""

    reset_streamlit_state()
    service = UIStateService()
    session_id = "session_refresh_analysis_status"
    service.save_ui_state(
        session_id,
        {
            "actor_type": "candidate",
            "candidate_id": "candidate_status",
            "current_analysis_id": "analysis_status_001",
            "task_status": "GENERATING",
        },
    )

    apply_persistent_ui_state(service.load_ui_state(session_id))

    assert st.session_state["current_analysis_id"] == "analysis_status_001"
    assert st.session_state["task_status"] == "GENERATING"


def test_set_current_page_updates_single_source() -> None:
    """导航变更应只更新 current_page 这一处页面状态。"""

    reset_streamlit_state()
    st.session_state["session_id"] = "session_nav_update"
    st.session_state["current_page"] = "新建分析"

    set_current_page("历史分析", rerun=False)

    assert st.session_state["current_page"] == "历史分析"
    legacy_page_key = "last" + "_page"
    assert legacy_page_key not in st.session_state


def test_invalid_current_page_falls_back_to_new_analysis() -> None:
    """恢复到无效 current_page 时应安全回到新建分析。"""

    reset_streamlit_state()
    st.session_state["current_page"] = "不存在的页面"

    normalize_current_page()

    assert st.session_state["current_page"] == "新建分析"


def reset_streamlit_state() -> None:
    """清理 Streamlit session_state，避免测试之间互相影响。"""

    for key in list(st.session_state.keys()):
        del st.session_state[key]
