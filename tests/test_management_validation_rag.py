"""岗位管理、输入校验、选择恢复和 RAG 诊断测试。"""

import streamlit as st

from memory.tenant_memory_service import TenantMemoryService
from rag.ingest import get_knowledge_base_diagnostics
from rag.vector_store import VectorStoreClient
from frontend.legacy import clear_hr_selection, resolve_selection_index
from frontend.state import set_actor_type


VALID_JD = (
    "岗位职责：负责 AI Agent 平台后端服务设计、开发和优化，参与 RAG 检索链路建设。"
    "任职要求：熟悉 Python、FastAPI、LangGraph、Redis、Docker，有大模型应用经验优先。"
)


def test_deactivate_job_does_not_delete() -> None:
    """停用 job 后，job_profiles 仍存在且 status=inactive。"""

    service = TenantMemoryService()
    job = service.create_job_profile("company_deactivate_job", "AI Agent 工程师", VALID_JD)

    assert service.deactivate_job_profile("company_deactivate_job", job["job_id"]) is True
    inactive_jobs = service.list_job_profiles("company_deactivate_job", status="inactive")

    assert any(item["job_id"] == job["job_id"] and item["status"] == "inactive" for item in inactive_jobs)


def test_deactivate_last_job_clears_selection() -> None:
    """停用最后一个 active job 后，selected_job_id 应被前端清空。"""

    reset_streamlit_state()
    service = TenantMemoryService()
    job = service.create_job_profile("company_last_job", "RAG 工程师", VALID_JD)
    st.session_state["selected_job_id"] = job["job_id"]

    service.deactivate_job_profile("company_last_job", job["job_id"])
    active_jobs = service.list_job_profiles("company_last_job")
    if not active_jobs:
        clear_hr_selection()

    assert not st.session_state.get("selected_job_id")


def test_selected_job_persists_after_refresh() -> None:
    """用户选择 A 后，刷新时应恢复 A，而不是强制选择最近创建的 B。"""

    reset_streamlit_state()
    service = TenantMemoryService()
    job_a = service.create_job_profile("company_select_persist", "AI Agent 工程师", VALID_JD)
    job_b = service.create_job_profile("company_select_persist", "RAG 工程师", VALID_JD)
    st.session_state["selected_job_id"] = job_a["job_id"]
    jobs = service.list_job_profiles("company_select_persist")

    index = resolve_selection_index(jobs, "job_id", "selected_job_id")

    assert jobs[index]["job_id"] == job_a["job_id"]
    assert job_b["job_id"] != job_a["job_id"]


def test_switch_actor_does_not_delete_jobs() -> None:
    """切换 actor 不得删除 job_profiles。"""

    reset_streamlit_state()
    service = TenantMemoryService()
    service.create_job_profile("company_switch_keep_jobs", "AI Agent 工程师", VALID_JD)
    st.session_state["actor_type"] = "hr"
    st.session_state["company_id"] = "company_switch_keep_jobs"

    set_actor_type("candidate")

    assert service.list_job_profiles("company_switch_keep_jobs")


def test_switch_actor_does_not_delete_target_roles() -> None:
    """切换 actor 不得删除 target_roles。"""

    reset_streamlit_state()
    service = TenantMemoryService()
    service.create_candidate_target_role("candidate_switch_keep_roles", "AI Agent 工程师")
    st.session_state["actor_type"] = "candidate"
    st.session_state["candidate_id"] = "candidate_switch_keep_roles"

    set_actor_type("hr")

    assert service.list_candidate_target_roles("candidate_switch_keep_roles")


def test_invalid_job_name_rejected() -> None:
    """aaa、bbb、test 不允许作为 job_name。"""

    service = TenantMemoryService()
    for invalid_name in ["aaa", "bbb", "test"]:
        try:
            service.create_job_profile("company_invalid_name", invalid_name, VALID_JD)
        except ValueError:
            continue
        raise AssertionError(f"{invalid_name} 不应被保存为岗位名称")


def test_invalid_jd_rejected() -> None:
    """aaa、bbb、test 不允许作为 JD。"""

    service = TenantMemoryService()
    for invalid_jd in ["aaa", "bbb", "test"]:
        try:
            service.create_job_profile("company_invalid_jd", "AI Agent 工程师", invalid_jd)
        except ValueError:
            continue
        raise AssertionError(f"{invalid_jd} 不应被保存为 JD")


def test_valid_jd_accepted() -> None:
    """正常 JD 可以保存。"""

    job = TenantMemoryService().create_job_profile("company_valid_jd", "AI Agent 工程师", VALID_JD)

    assert job["job_name"] == "AI Agent 工程师"
    assert job["jd_text"] == VALID_JD


def test_rag_empty_diagnostics() -> None:
    """向量库为空时返回明确诊断。"""

    VectorStoreClient("shared_knowledge").delete_by_metadata({"scope": "shared"})

    diagnostics = get_knowledge_base_diagnostics(retrieval_query="RAG", retrieval_filters={"scope": "shared"})

    assert diagnostics["vector_store_doc_count"] == 0
    assert diagnostics["retrieval_warnings"]


def test_shared_rag_filter_does_not_require_tenant_id() -> None:
    """Shared Knowledge 检索不要求 candidate_id/company_id。"""

    store = VectorStoreClient("shared_knowledge")
    store.delete_by_metadata({"scope": "shared"})
    store.add_documents(
        [
            {
                "text": "LangGraph RAG 面试题：如何设计 AgentState 和条件路由？",
                "metadata": {"scope": "shared", "source": "unit-test"},
            }
        ]
    )

    docs = store.similarity_search("LangGraph RAG", filters={"scope": "shared"})

    assert docs
    assert all("candidate_id" not in doc["metadata"] and "company_id" not in doc["metadata"] for doc in docs)


def reset_streamlit_state() -> None:
    """清理 Streamlit session_state，避免测试之间互相影响。"""

    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state["session_id"] = "session_management_validation_rag"
