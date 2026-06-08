"""Candidate / HR Actor Context 隔离测试。"""

import streamlit as st

from agents.hr_manager_agent import HRManagerAgent
from agents.manager_agent import ManagerAgent
from frontend.state import get_candidate_context, get_hr_context, set_actor_type
from tools.context_validator import ContextValidator


def test_candidate_context_clean() -> None:
    """Candidate Context 不应包含 company_id 和 job_id。"""

    context = {
        "actor_type": "candidate",
        "candidate_id": "candidate_clean",
        "target_role_id": "target_role_clean",
        "role_name": "AI Agent 工程师",
        "session_id": "session_clean",
    }

    ContextValidator().validate(context)

    assert "company_id" not in context
    assert "job_id" not in context


def test_hr_context_clean() -> None:
    """HR Context 不应包含 candidate_id 和 target_role_id。"""

    context = {
        "actor_type": "hr",
        "company_id": "company_clean",
        "job_id": "job_clean",
        "job_name": "AI Agent 工程师",
        "session_id": "session_clean",
    }

    ContextValidator().validate(context)

    assert "candidate_id" not in context
    assert "target_role_id" not in context


def test_switch_hr_to_candidate() -> None:
    """HR 切换到 Candidate 时只清理岗位临时选择，不删除企业身份。"""

    reset_streamlit_state()
    st.session_state["actor_type"] = "hr"
    st.session_state["company_id"] = "company_old"
    st.session_state["selected_job_id"] = "job_old"
    st.session_state["selected_job_name"] = "旧岗位"

    set_actor_type("candidate")

    assert st.session_state["company_id"] == "company_old"
    assert "selected_job_id" not in st.session_state
    st.session_state["candidate_id"] = "candidate_new"
    context = get_candidate_context()
    assert "company_id" not in context
    assert "job_id" not in context


def test_switch_candidate_to_hr() -> None:
    """Candidate 切换到 HR 时只清理目标岗位临时选择，不删除候选人身份。"""

    reset_streamlit_state()
    st.session_state["actor_type"] = "candidate"
    st.session_state["candidate_id"] = "candidate_old"
    st.session_state["selected_target_role_id"] = "target_role_old"
    st.session_state["selected_role_name"] = "旧方向"

    set_actor_type("hr")

    assert st.session_state["candidate_id"] == "candidate_old"
    assert "selected_target_role_id" not in st.session_state
    st.session_state["company_id"] = "company_new"
    st.session_state["selected_job_id"] = "job_new"
    context = get_hr_context()
    assert "candidate_id" not in context
    assert "target_role_id" not in context


def test_context_validator() -> None:
    """ContextValidator 应检测 Candidate 和 HR 的污染字段。"""

    validator = ContextValidator()

    try:
        validator.validate({"actor_type": "candidate", "candidate_id": "c1", "company_id": "company_bad"})
    except ValueError as exc:
        assert "Candidate Context 污染" in str(exc)
    else:
        raise AssertionError("Candidate 出现 company_id 时必须报错")

    try:
        validator.validate({"actor_type": "hr", "company_id": "company_1", "candidate_id": "candidate_bad"})
    except ValueError as exc:
        assert "HR Context 污染" in str(exc)
    else:
        raise AssertionError("HR 出现 candidate_id 时必须报错")


def test_workflow_initial_states_are_clean() -> None:
    """ManagerAgent 和 HRManagerAgent 构造的 initial_state 应符合各自 Context 边界。"""

    manager = ManagerAgent()
    hr_manager = HRManagerAgent()

    assert manager.context_validator
    assert hr_manager.context_validator


def reset_streamlit_state() -> None:
    """清理 Streamlit session_state，避免测试之间互相影响。"""

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["session_id"] = "session_context_test"
