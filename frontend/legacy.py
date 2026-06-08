"""用于交互式招聘分析的 Streamlit 前端入口。"""

import os
import re
from pathlib import Path
from typing import Dict, List
from uuid import uuid4

import streamlit as st

from agents.hr_manager_agent import HRManagerAgent
from agents.manager_agent import ManagerAgent
from app.config import ALLOWED_EXTENSIONS, DISPLAY_TIMEZONE
from graph.state import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_GENERATING
from llm.client import chat_completion, get_last_llm_error, get_llm_config
from memory.tenant_memory_service import TenantMemoryService
from memory.ui_state_service import UI_STATE_KEYS, UIStateService
from monitoring.monitor_service import get_monitor_service
from rag.ingest import (
    create_default_knowledge_base,
    get_knowledge_base_diagnostics,
    ingest_knowledge_base,
)
from rag.vector_store import VectorStoreClient
from services.file_storage_service import FileStorageService
from tools.context_validator import ContextValidator
from frontend.toggle_state import (
    build_toggle_button_key,
    build_toggle_state_key,
    get_bool_state,
    toggle_bool_state,
)
from utils.time_utils import format_display_time


MODEL_PRESETS = {
    "GPT-4o": {
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
    },
    "GPT-4o mini": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "GPT-4.1": {
        "model": "gpt-4.1",
        "base_url": "https://api.openai.com/v1",
    },
    "GPT-4.1 mini": {
        "model": "gpt-4.1-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "DeepSeek Chat": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
    },
    "DeepSeek Reasoner": {
        "model": "deepseek-reasoner",
        "base_url": "https://api.deepseek.com",
    },
    "Qwen Turbo": {
        "model": "qwen-turbo",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "Qwen Plus": {
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "Qwen Max": {
        "model": "qwen-max",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "GLM-4-Flash": {
        "model": "glm-4-flash",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "GLM-4-Plus": {
        "model": "glm-4-plus",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "Ollama 本地模型": {
        "model": "qwen2.5:7b",
        "base_url": "http://localhost:11434/v1",
    },
}

# 侧边栏中预置的 OpenAI 兼容模型配置。
CUSTOM_MODEL_LABEL = "自定义模型"
# 模型下拉菜单中的自定义模型选项。

CANDIDATE_ROLE = "求职者"
# 求职者身份，对应 Candidate 侧工作流。
HR_ROLE = "企业招聘者"
# 企业招聘者身份，对应 HR 侧工作流。

CONTEXT_VALIDATOR = ContextValidator()
# 前端用于清洗和校验 Candidate / HR Context 的工具。

NAVIGATION_PAGES = ["新建分析", "历史分析", "岗位管理 / 目标岗位管理", "知识库", "监控中心", "调试信息"]
"""Streamlit 前端唯一导航页面集合。"""


def main() -> None:
    """渲染 Streamlit 界面，并处理用户触发的分析请求。"""

    initialize_identity_state()
    st.session_state.setdefault("current_page", "新建分析")
    st.title("AI Recruitment Agent")
    render_ui_state_warning()

    with st.sidebar:
        identity_config = render_identity_sidebar()
        st.divider()
        render_page_navigation()
        page_name = st.session_state["current_page"]
        st.divider()
        llm_config = render_llm_sidebar()
        if page_name == "新建分析":
            st.divider()
            resume_file, jd_text, submitted = render_input_sidebar(identity_config)
        else:
            resume_file, jd_text, submitted = None, "", False
    identity_config = build_identity_config_from_session()

    if page_name == "历史分析":
        render_history_center(identity_config)
        return
    if page_name == "知识库":
        render_knowledge_page()
        return
    if page_name == "监控中心":
        render_monitoring_dashboard()
        return
    if page_name == "岗位管理 / 目标岗位管理":
        render_role_or_job_management(identity_config)
        return
    if page_name == "调试信息":
        render_debug_page(identity_config)
        return

    if submitted:
        if resume_file is None:
            st.error("请先上传 PDF、DOCX 或 TXT 简历。")
            return
        if not jd_text.strip():
            st.error("请先输入岗位 JD。")
            return

        configure_llm_environment(llm_config)
        st.session_state["task_status"] = TASK_STATUS_GENERATING
        persist_ui_state()
        with st.spinner("智能体工作流正在分析，请稍等..."):
            resume_path = save_uploaded_resume(resume_file)
            state = analyze_by_identity(
                str(resume_path),
                jd_text,
                identity_config,
                resume_file.name,
                getattr(resume_file, "type", "") or "",
            )

        if state.get("error"):
            st.session_state["task_status"] = TASK_STATUS_FAILED
            persist_ui_state()
            st.error(state["error"])
            return

        if state.get("analysis_id"):
            st.session_state["current_analysis_id"] = state.get("analysis_id")
            st.session_state["task_status"] = state.get("task_status") or TASK_STATUS_COMPLETED
            persist_ui_state()
        render_result(state)
    else:
        render_empty_state()


def render_page_navigation() -> str:
    """渲染左侧页面导航菜单，并在变更后立即 rerun。"""

    st.header("导航")
    normalize_current_page_for_actor()
    chosen_page = st.radio(
        "功能中心",
        NAVIGATION_PAGES,
        index=NAVIGATION_PAGES.index(st.session_state["current_page"]),
        key="nav_radio",
        label_visibility="collapsed",
    )
    if chosen_page != st.session_state["current_page"]:
        set_current_page(chosen_page, rerun=True)
    return st.session_state["current_page"]


def render_identity_sidebar() -> Dict[str, str]:
    """渲染身份选择侧边栏，并返回角色相关配置。"""

    st.header("身份")
    current_actor_type = st.session_state.get("actor_type", "candidate")
    actor_index = 1 if current_actor_type == "hr" else 0
    actor_type = st.selectbox("使用身份", [CANDIDATE_ROLE, HR_ROLE], index=actor_index)
    new_actor_type = "hr" if actor_type == HR_ROLE else "candidate"
    switch_actor_context(new_actor_type)

    if actor_type == CANDIDATE_ROLE:
        ensure_candidate_identity()
        render_identity_debug_panel()
        return build_candidate_context_from_session()

    company_name = st.text_input("公司名称", placeholder="请输入企业名称")
    ensure_hr_identity(company_name)
    render_identity_debug_panel()
    return build_hr_context_from_session()


def initialize_identity_state() -> None:
    """初始化并恢复身份相关的业务关键状态。"""

    if st.session_state.get("_ui_state_initialized"):
        return
    session_id = resolve_startup_session_id(
        current_session_id=st.session_state.get("session_id", ""),
        query_session_id=get_query_param("session_id"),
        last_session_id=get_ui_state_service().get_last_session_id(),
    )
    st.session_state["session_id"] = session_id
    set_session_query_param(session_id)
    restored_state = get_ui_state_service().load_ui_state(session_id)
    apply_persistent_ui_state(restored_state)
    st.session_state["ui_state_loaded_from"] = get_ui_state_service().loaded_from
    st.session_state.setdefault("actor_type", "candidate")
    st.session_state.setdefault("current_page", "新建分析")
    normalize_current_page_for_actor()
    validate_restored_selection()
    st.session_state["_ui_state_initialized"] = True
    persist_ui_state()


def resolve_startup_session_id(current_session_id: str, query_session_id: str, last_session_id: str) -> str:
    """按 session_state、query params、本地最近会话、新 UUID 的顺序确定 session_id。"""

    return current_session_id or query_session_id or last_session_id or f"session_{uuid4().hex}"


def apply_persistent_ui_state(restored_state: Dict[str, object]) -> None:
    """把持久化 UI 状态恢复到 st.session_state。"""

    for key, value in (restored_state or {}).items():
        if key in UI_STATE_KEYS and value:
            st.session_state[key] = value


def normalize_current_page_for_actor() -> None:
    """确保 current_page 是当前前端可用页面，无效时回到新建分析。"""

    if st.session_state.get("current_page") not in NAVIGATION_PAGES:
        st.session_state["current_page"] = "新建分析"


def set_current_page(page_name: str, rerun: bool = False) -> None:
    """统一更新当前页面状态并持久化，必要时立即重跑脚本。"""

    if page_name not in NAVIGATION_PAGES:
        page_name = "新建分析"
    if st.session_state.get("current_page") == page_name:
        return
    st.session_state["current_page"] = page_name
    persist_ui_state()
    if rerun:
        st.rerun()


def switch_actor_context(new_actor_type: str) -> None:
    """切换身份时清理另一个身份的上下文字段。"""

    previous_actor_type = st.session_state.get("actor_type")
    if previous_actor_type == new_actor_type:
        return
    st.session_state["actor_type"] = new_actor_type
    if new_actor_type == "candidate":
        clear_hr_context_from_session()
    else:
        clear_candidate_context_from_session()
    persist_ui_state()


def clear_candidate_context_from_session() -> None:
    """从 session_state 中清理 Candidate 页面临时选择，不删除候选人身份。"""

    for key in ["selected_target_role_id", "selected_role_name"]:
        st.session_state.pop(key, None)


def clear_hr_context_from_session() -> None:
    """从 session_state 中清理 HR 页面临时选择，不删除企业身份。"""

    for key in ["selected_job_id", "selected_job_name", "selected_job_jd_text"]:
        st.session_state.pop(key, None)


def ensure_candidate_identity() -> None:
    """确保求职者身份拥有系统自动生成的 candidate_id。"""

    if not st.session_state.get("candidate_id"):
        st.session_state["candidate_id"] = f"candidate_{uuid4().hex}"
        persist_ui_state()


def ensure_hr_identity(company_name: str) -> None:
    """确保 HR 身份拥有系统自动生成的 company_id 和 job_id。"""

    cleaned_name = company_name.strip()
    previous_name = st.session_state.get("company_name", "")
    if cleaned_name and cleaned_name != previous_name:
        st.session_state["company_name"] = cleaned_name
        st.session_state["company_id"] = build_company_id(cleaned_name)
        clear_hr_selection()
        persist_ui_state()
    elif not st.session_state.get("company_id"):
        st.session_state["company_id"] = f"company_{uuid4().hex}"
        persist_ui_state()


def build_company_id(company_name: str) -> str:
    """根据公司名称生成稳定且安全的 company_id。"""

    normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", company_name).strip("_")
    normalized = normalized[:32] or "company"
    return f"company_{normalized}_{uuid4().hex[:8]}"


def build_identity_config_from_session() -> Dict[str, str]:
    """从 session_state 读取当前身份配置，保持旧调用兼容。"""

    if st.session_state.get("actor_type") == "hr":
        return build_hr_context_from_session()
    return build_candidate_context_from_session()


def build_candidate_context_from_session() -> Dict[str, str]:
    """从 session_state 构造 CandidateContext。"""

    context = {
        "actor_type": st.session_state.get("actor_type", "candidate"),
        "candidate_id": st.session_state.get("candidate_id", ""),
        "target_role_id": st.session_state.get("selected_target_role_id", ""),
        "role_name": st.session_state.get("selected_role_name", ""),
        "session_id": st.session_state.get("session_id", ""),
        "current_analysis_id": st.session_state.get("current_analysis_id", ""),
    }
    CONTEXT_VALIDATOR.validate_candidate_context(context)
    return context


def build_hr_context_from_session() -> Dict[str, str]:
    """从 session_state 构造 HRContext。"""

    context = {
        "actor_type": "hr",
        "company_id": st.session_state.get("company_id", ""),
        "job_id": st.session_state.get("selected_job_id", ""),
        "job_name": st.session_state.get("selected_job_name", ""),
        "session_id": st.session_state.get("session_id", ""),
        "current_analysis_id": st.session_state.get("current_analysis_id", ""),
    }
    CONTEXT_VALIDATOR.validate_hr_context(context)
    return context


def render_identity_debug_panel() -> None:
    """在高级调试模式下只读展示系统生成的身份 ID。"""

    show_debug = st.checkbox("高级调试模式", value=False)
    if not show_debug:
        return
    st.text_input("actor_type", value=st.session_state.get("actor_type", ""), disabled=True)
    st.text_input("session_id", value=st.session_state.get("session_id", ""), disabled=True)
    st.text_input("current_page", value=st.session_state.get("current_page", ""), disabled=True)
    st.text_input("current_analysis_id", value=st.session_state.get("current_analysis_id", ""), disabled=True)
    st.text_input("task_status", value=st.session_state.get("task_status", ""), disabled=True)
    st.text_input("ui_state_loaded_from", value=st.session_state.get("ui_state_loaded_from", "new"), disabled=True)
    if st.session_state.get("actor_type") == "candidate":
        st.text_input("candidate_id", value=st.session_state.get("candidate_id", ""), disabled=True)
        st.text_input("target_role_id", value=st.session_state.get("selected_target_role_id", ""), disabled=True)
        st.text_input("role_name", value=st.session_state.get("selected_role_name", ""), disabled=True)
    else:
        st.text_input("company_id", value=st.session_state.get("company_id", ""), disabled=True)
        st.text_input("job_id", value=st.session_state.get("selected_job_id", ""), disabled=True)
        st.text_input("job_name", value=st.session_state.get("selected_job_name", ""), disabled=True)


def render_llm_sidebar() -> Dict[str, str]:
    """渲染大模型配置侧边栏，并返回用户选择的模型参数。"""

    current_config = get_llm_config()
    preset_names = list(MODEL_PRESETS.keys()) + [CUSTOM_MODEL_LABEL]

    st.header("模型配置")
    selected_name = st.selectbox("模型", preset_names, index=0)
    preset = MODEL_PRESETS.get(selected_name, {})
    default_model = preset.get("model") or current_config.model
    default_base_url = preset.get("base_url") or current_config.base_url

    if selected_name == CUSTOM_MODEL_LABEL:
        model = st.text_input("自定义模型名称", value=current_config.model)
        base_url = st.text_input("API 接口 Base URL", value=current_config.base_url)
    else:
        model = st.text_input("模型名称", value=default_model)
        base_url = st.text_input("API 接口 Base URL", value=default_base_url)

    api_key = st.text_input(
        "API Key",
        value=current_config.api_key,
        type="password",
        placeholder="请输入模型服务 API Key",
    )
    temperature = st.slider(
        "温度",
        min_value=0.0,
        max_value=1.0,
        value=float(current_config.temperature),
        step=0.1,
    )
    timeout = st.number_input(
        "超时时间",
        min_value=5,
        max_value=120,
        value=int(current_config.timeout),
        step=5,
    )
    if api_key and model and base_url:
        st.success("大模型已配置，分析时会优先调用模型。")
    else:
        st.warning("未填写完整模型配置时，将使用本地规则兜底。")

    config = {
        "api_key": api_key.strip(),
        "base_url": base_url.strip(),
        "model": model.strip(),
        "temperature": str(temperature),
        "timeout": str(timeout),
    }
    if st.button("测试模型连接", use_container_width=True):
        configure_llm_environment(config)
        test_llm_connection()
    return config


def test_llm_connection() -> None:
    """测试当前侧边栏模型配置是否可以成功调用。"""

    content = chat_completion("你是连通性测试助手。", "请只回复 OK。")
    if content:
        st.success(f"模型连接成功：{content[:80]}")
    else:
        st.error(f"模型连接失败：{get_last_llm_error() or '未知错误'}")


def render_input_sidebar(identity_config: Dict[str, str]):
    """根据身份渲染新建分析输入侧边栏。"""

    st.header("输入")
    if identity_config.get("actor_type") == "hr":
        return render_hr_input_sidebar(identity_config)
    return render_candidate_input_sidebar(identity_config)


def render_candidate_input_sidebar(identity_config: Dict[str, str]):
    """渲染 Candidate 新建分析输入区域。"""

    roles = get_history_service().list_candidate_target_roles(identity_config.get("candidate_id", ""))
    if not roles:
        st.warning("请先创建目标岗位。")
        clear_candidate_selection()
        st.button("开始分析", type="primary", use_container_width=True, disabled=True)
        return None, "", False
    selected_index = resolve_selection_index(
        records=roles,
        id_field="target_role_id",
        session_key="selected_target_role_id",
    )
    selected_role = st.selectbox(
        "目标岗位",
        roles,
        index=selected_index,
        format_func=lambda item: item.get("role_name", "未命名方向"),
    )
    st.session_state["selected_target_role_id"] = selected_role.get("target_role_id", "")
    st.session_state["selected_role_name"] = selected_role.get("role_name", "")
    persist_ui_state()
    resume_file = st.file_uploader(
        "上传简历文件",
        type=[extension.lstrip(".") for extension in sorted(ALLOWED_EXTENSIONS)],
    )
    jd_text = st.text_area(
        "本次岗位 JD",
        height=260,
        placeholder="粘贴岗位职责、任职要求、技能栈和加分项...",
    )
    submitted = st.button("开始分析", type="primary", use_container_width=True)
    return resume_file, jd_text, submitted


def render_hr_input_sidebar(identity_config: Dict[str, str]):
    """渲染 HR 新建候选人筛选输入区域。"""

    jobs = get_history_service().list_job_profiles(identity_config.get("company_id", ""))
    if not jobs:
        st.warning("请先创建岗位。")
        clear_hr_selection()
        st.button("开始筛选", type="primary", use_container_width=True, disabled=True)
        return None, "", False
    selected_index = resolve_selection_index(
        records=jobs,
        id_field="job_id",
        session_key="selected_job_id",
    )
    selected_job = st.selectbox(
        "当前岗位",
        jobs,
        index=selected_index,
        format_func=lambda item: item.get("job_name", "未命名岗位"),
    )
    st.session_state["selected_job_id"] = selected_job.get("job_id", "")
    st.session_state["selected_job_name"] = selected_job.get("job_name", "")
    persist_ui_state()
    st.caption(f"当前企业：{st.session_state.get('company_name') or identity_config.get('company_id')}")
    st.text_area("JD 预览", value=selected_job.get("jd_text", ""), height=220, disabled=True)
    resume_file = st.file_uploader(
        "上传候选人简历",
        type=[extension.lstrip(".") for extension in sorted(ALLOWED_EXTENSIONS)],
    )
    submitted = st.button("开始筛选", type="primary", use_container_width=True)
    return resume_file, selected_job.get("jd_text", ""), submitted


def configure_llm_environment(config: Dict[str, str]) -> None:
    """将用户在侧边栏输入的模型配置写入当前进程环境变量。"""

    mapping = {
        "LLM_API_KEY": config.get("api_key", ""),
        "LLM_BASE_URL": config.get("base_url", ""),
        "LLM_MODEL": config.get("model", ""),
        "LLM_TEMPERATURE": config.get("temperature", ""),
        "LLM_TIMEOUT": config.get("timeout", ""),
    }
    for key, value in mapping.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


@st.cache_resource
def get_manager_agent() -> ManagerAgent:
    """为 Streamlit 进程创建一个缓存的管理智能体。"""

    return ManagerAgent()


@st.cache_resource
def get_hr_manager_agent() -> HRManagerAgent:
    """为 Streamlit 进程创建一个缓存的 HR 管理智能体。"""

    return HRManagerAgent()


@st.cache_resource
def get_history_service() -> TenantMemoryService:
    """为 Streamlit 进程创建一个缓存的多租户历史服务。"""

    return TenantMemoryService()


@st.cache_resource
def get_ui_state_service() -> UIStateService:
    """为 Streamlit 进程创建一个缓存的 UI 状态服务。"""

    return UIStateService()


def get_query_param(name: str) -> str:
    """从浏览器 query params 中读取单个参数值。"""

    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def set_session_query_param(session_id: str) -> None:
    """把 session_id 写入 URL query params，刷新后可恢复同一会话。"""

    if not session_id:
        return
    try:
        st.query_params["session_id"] = session_id
    except Exception:
        return


def collect_persistent_ui_state(extra: Dict[str, str] = None) -> Dict[str, str]:
    """收集允许持久化的前端业务关键状态。"""

    state = {
        key: st.session_state.get(key, "")
        for key in UI_STATE_KEYS
        if st.session_state.get(key)
    }
    if extra:
        state.update({key: value for key, value in extra.items() if key in UI_STATE_KEYS and value})
    return state


def persist_ui_state(current_page: str = "") -> None:
    """将当前前端业务关键状态保存到 Redis 或本地 JSON。"""

    session_id = st.session_state.get("session_id", "")
    if current_page:
        st.session_state["current_page"] = current_page
    saved_to = get_ui_state_service().save_ui_state(session_id, collect_persistent_ui_state())
    if saved_to != "new":
        st.session_state["ui_state_saved_to"] = saved_to
    set_session_query_param(session_id)


def validate_restored_selection() -> None:
    """校验刷新恢复的岗位或目标岗位选择是否仍然有效。"""

    actor_type = st.session_state.get("actor_type", "candidate")
    if actor_type == "hr":
        validate_restored_job_selection()
        return
    validate_restored_target_role_selection()


def validate_restored_job_selection() -> None:
    """校验恢复的 selected_job_id 是否属于当前企业且仍为 active。"""

    company_id = st.session_state.get("company_id", "")
    selected_job_id = st.session_state.get("selected_job_id", "")
    if not company_id or not selected_job_id:
        return
    active_jobs = get_history_service().list_job_profiles(company_id, status="active")
    if any(job.get("job_id") == selected_job_id for job in active_jobs):
        return
    clear_hr_selection()
    st.session_state["ui_state_selection_warning"] = "已保存的岗位不存在或已停用，请重新选择岗位。"


def validate_restored_target_role_selection() -> None:
    """校验恢复的 selected_target_role_id 是否属于当前候选人且仍为 active。"""

    candidate_id = st.session_state.get("candidate_id", "")
    selected_role_id = st.session_state.get("selected_target_role_id", "")
    if not candidate_id or not selected_role_id:
        return
    active_roles = get_history_service().list_candidate_target_roles(candidate_id, status="active")
    if any(role.get("target_role_id") == selected_role_id for role in active_roles):
        return
    clear_candidate_selection()
    st.session_state["ui_state_selection_warning"] = "已保存的目标岗位不存在或已停用，请重新选择目标岗位。"


def resolve_selection_index(records: List[Dict[str, object]], id_field: str, session_key: str) -> int:
    """根据 session_state 中的已选 ID 恢复 selectbox 选中项。"""

    selected_id = st.session_state.get(session_key, "")
    for index, record in enumerate(records):
        if record.get(id_field) == selected_id:
            return index
    if selected_id:
        st.session_state.pop(session_key, None)
        st.warning("当前选中项已不存在或已停用，请重新选择。")
        persist_ui_state()
    return 0


def clear_candidate_selection() -> None:
    """清空 Candidate 当前目标岗位选择。"""

    for key in ["selected_target_role_id", "selected_role_name"]:
        st.session_state.pop(key, None)
    if st.session_state.get("session_id"):
        persist_ui_state()


def clear_hr_selection() -> None:
    """清空 HR 当前岗位选择。"""

    for key in ["selected_job_id", "selected_job_name", "selected_job_jd_text"]:
        st.session_state.pop(key, None)
    if st.session_state.get("session_id"):
        persist_ui_state()


def render_ui_state_warning() -> None:
    """显示刷新恢复过程中发现的无效选择提示。"""

    warning = st.session_state.pop("ui_state_selection_warning", "")
    if warning:
        st.warning(warning)


def save_uploaded_resume(uploaded_file) -> Path:
    """把 Streamlit 上传的简历先保存到 data/uploads/tmp，并返回文件系统路径。"""

    suffix = Path(uploaded_file.name or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))} 文件")

    return FileStorageService().save_temp_upload(uploaded_file.getvalue(), uploaded_file.name or f"resume{suffix}")


def analyze_by_identity(
    resume_file_path: str,
    jd_text: str,
    identity_config: Dict[str, str],
    resume_file_name: str,
    content_type: str = "",
) -> Dict[str, object]:
    """根据用户选择的身份运行对应的 LangGraph 工作流。"""

    if identity_config.get("actor_type") == "hr":
        return analyze_resume_for_hr(resume_file_path, jd_text, identity_config, resume_file_name, content_type)
    return analyze_resume_for_candidate(resume_file_path, jd_text, identity_config, resume_file_name, content_type)


def analyze_resume_for_candidate(
    resume_file_path: str,
    jd_text: str,
    identity_config: Dict[str, str],
    resume_file_name: str,
    content_type: str = "",
) -> Dict[str, object]:
    """以求职者身份运行 Candidate 侧工作流。"""

    return dict(
        get_manager_agent().run(
            resume_file_path=resume_file_path,
            jd_text=jd_text,
            user_id=identity_config["candidate_id"],
            candidate_id=identity_config["candidate_id"],
            session_id=identity_config["session_id"],
            thread_id="streamlit",
            user_query=jd_text,
            resume_file_name=resume_file_name,
            original_filename=resume_file_name,
            content_type=content_type,
            target_role_id=identity_config["target_role_id"],
            role_name=identity_config["role_name"],
        )
    )


def analyze_resume_for_hr(
    resume_file_path: str,
    jd_text: str,
    identity_config: Dict[str, str],
    resume_file_name: str,
    content_type: str = "",
) -> Dict[str, object]:
    """以企业招聘者身份运行 HR 侧工作流。"""

    return dict(
        get_hr_manager_agent().run(
            resume_file_path=resume_file_path,
            jd_text=jd_text,
            company_id=identity_config["company_id"],
            job_id=identity_config["job_id"],
            session_id=identity_config["session_id"],
            resume_file_name=resume_file_name,
            original_filename=resume_file_name,
            content_type=content_type,
        )
    )


def render_history_center(identity_config: Dict[str, str]) -> None:
    """根据当前身份渲染历史分析中心。"""

    st.header("Analysis Center")
    if identity_config.get("actor_type") == "hr":
        render_hr_history_center(identity_config)
        return
    render_candidate_history_center(identity_config)


def render_role_or_job_management(identity_config: Dict[str, str]) -> None:
    """根据当前身份渲染目标岗位或企业岗位管理页面。"""

    if identity_config.get("actor_type") == "hr":
        render_hr_job_management(identity_config)
        return
    render_candidate_target_role_management(identity_config)


def render_candidate_target_role_management(identity_config: Dict[str, str]) -> None:
    """渲染 Candidate 目标岗位管理页面。"""

    candidate_id = identity_config.get("candidate_id", "")
    form_version = st.session_state.setdefault("candidate_role_form_version", 0)
    st.header("目标岗位管理")
    with st.form(f"create_target_role_form_{form_version}"):
        role_name = st.text_input(
            "目标岗位名称",
            placeholder="例如：AI Agent 工程师",
            key=f"candidate_role_name_{form_version}",
        )
        description = st.text_area(
            "描述",
            placeholder="可填写求职方向说明，不绑定固定 JD。",
            key=f"candidate_role_desc_{form_version}",
        )
        submitted = st.form_submit_button(
            "新增目标岗位",
            use_container_width=True,
        )
    if submitted:
        try:
            role = get_history_service().create_candidate_target_role(
                candidate_id,
                role_name,
                description,
            )
            st.success(f"已创建目标岗位：{role.get('role_name')}")
            st.session_state["selected_target_role_id"] = role.get("target_role_id", "")
            st.session_state["selected_role_name"] = role.get("role_name", "")
            st.session_state["candidate_role_form_version"] = (
                    st.session_state.get("candidate_role_form_version", 0) + 1
            )
            persist_ui_state()
            st.rerun()

        except ValueError as exc:
            st.error(str(exc))

    active_roles = get_history_service().list_candidate_target_roles(candidate_id, status="active")
    inactive_roles = get_history_service().list_candidate_target_roles(candidate_id, status="inactive")
    if not active_roles:
        clear_candidate_selection()
        st.info("暂无目标岗位。")
        render_inactive_target_roles(candidate_id, inactive_roles)
        return
    selected_role = st.selectbox(
        "编辑目标岗位",
        active_roles,
        index=resolve_selection_index(active_roles, "target_role_id", "selected_target_role_id"),
        format_func=lambda item: item.get("role_name", "未命名方向"),
    )
    st.session_state["selected_target_role_id"] = selected_role.get("target_role_id", "")
    st.session_state["selected_role_name"] = selected_role.get("role_name", "")
    persist_ui_state()
    with st.form("edit_target_role_form"):
        new_name = st.text_input("名称", value=selected_role.get("role_name", ""))
        new_description = st.text_area("描述", value=selected_role.get("description", ""))
        col_update, col_deactivate = st.columns(2)
        update_clicked = col_update.form_submit_button("保存修改", use_container_width=True)
        deactivate_clicked = col_deactivate.form_submit_button("停用目标岗位", use_container_width=True)
    if update_clicked:
        try:
            updated = get_history_service().update_candidate_target_role(
                candidate_id,
                selected_role.get("target_role_id", ""),
                new_name,
                new_description,
            )
            st.success(f"已更新：{updated.get('role_name')}")
        except ValueError as exc:
            st.error(str(exc))
    if deactivate_clicked:
        if get_history_service().deactivate_candidate_target_role(
            candidate_id,
            selected_role.get("target_role_id", ""),
        ):
            st.success("目标岗位已停用。")
            clear_candidate_selection()
            st.rerun()
        else:
            st.error("停用失败：目标岗位不存在或无权访问。")
    st.subheader("Active 目标岗位")
    st.dataframe(
        [
            {
                "目标岗位": item.get("role_name"),
                "描述": item.get("description"),
                "状态": item.get("status"),
                "更新时间": format_time(item.get("updated_at")),
            }
            for item in active_roles
        ],
        use_container_width=True,
        hide_index=True,
    )
    render_inactive_target_roles(candidate_id, inactive_roles)


def render_hr_job_management(identity_config: Dict[str, str]) -> None:
    """渲染 HR 企业岗位管理页面。"""

    company_id = identity_config.get("company_id", "")
    st.header("岗位管理")
    if st.session_state.get("job_create_success_message"):
        st.success(st.session_state.pop("job_create_success_message"))
    form_version = int(st.session_state.get("create_job_form_version", 0))
    job_name_key = f"create_job_name_{form_version}"
    jd_text_key = f"create_job_jd_text_{form_version}"
    with st.form("create_job_form"):
        job_name = st.text_input("岗位名称", placeholder="例如：AI Agent 工程师", key=job_name_key)
        jd_text = st.text_area("岗位 JD", height=220, placeholder="请输入该岗位固定 JD。", key=jd_text_key)
        submitted = st.form_submit_button("新增岗位", use_container_width=True)
    if submitted:
        try:
            job = get_history_service().create_job_profile(company_id, job_name, jd_text, created_by=company_id)
            apply_created_job_state(job, form_version)
            persist_ui_state()
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

    active_jobs = get_history_service().list_job_profiles(company_id, status="active")
    inactive_jobs = get_history_service().list_job_profiles(company_id, status="inactive")
    if not active_jobs:
        clear_hr_selection()
        st.info("暂无岗位。")
        render_inactive_jobs(company_id, inactive_jobs)
        return
    selected_job = st.selectbox(
        "当前岗位选择器",
        active_jobs,
        index=resolve_selection_index(active_jobs, "job_id", "selected_job_id"),
        format_func=lambda item: item.get("job_name", "未命名岗位"),
    )
    st.session_state["selected_job_id"] = selected_job.get("job_id", "")
    st.session_state["selected_job_name"] = selected_job.get("job_name", "")
    st.session_state["selected_job_jd_text"] = selected_job.get("jd_text", "")
    persist_ui_state()
    st.text_area("JD 预览", value=selected_job.get("jd_text", ""), height=180, disabled=True)
    with st.form("edit_job_form"):
        new_job_name = st.text_input("岗位名称", value=selected_job.get("job_name", ""))
        new_jd_text = st.text_area("岗位 JD", value=selected_job.get("jd_text", ""), height=220)
        col_update, col_deactivate = st.columns(2)
        update_clicked = col_update.form_submit_button("保存岗位修改", use_container_width=True)
        deactivate_clicked = col_deactivate.form_submit_button("停用岗位", use_container_width=True)
    if update_clicked:
        try:
            updated = get_history_service().update_job_profile(
                company_id,
                selected_job.get("job_id", ""),
                new_job_name,
                new_jd_text,
                created_by=company_id,
            )
            st.success(f"已更新岗位：{updated.get('job_name')}，JD 版本：{updated.get('jd_version')}")
        except ValueError as exc:
            st.error(str(exc))
    if deactivate_clicked:
        if get_history_service().deactivate_job_profile(company_id, selected_job.get("job_id", "")):
            st.success("岗位已停用。")
            clear_hr_selection()
            st.rerun()
        else:
            st.error("停用失败：岗位不存在或无权访问。")
    with st.expander("JD 版本历史"):
        versions = get_history_service().list_job_versions(company_id, selected_job.get("job_id", ""))
        st.dataframe(versions, use_container_width=True, hide_index=True)
    st.subheader("Active 岗位")
    st.dataframe(
        [
            {
                "岗位名称": item.get("job_name"),
                "JD 版本": item.get("jd_version"),
                "技能": "、".join(item.get("required_skills") or []),
                "状态": item.get("status"),
                "更新时间": format_time(item.get("updated_at")),
            }
            for item in active_jobs
        ],
        use_container_width=True,
        hide_index=True,
    )
    render_inactive_jobs(company_id, inactive_jobs)


def render_inactive_target_roles(candidate_id: str, inactive_roles: List[Dict[str, object]]) -> None:
    """渲染已停用目标岗位列表并提供恢复按钮。"""

    st.subheader("Inactive 目标岗位")
    if not inactive_roles:
        st.write("暂无已停用目标岗位。")
        return
    for role in inactive_roles:
        col_name, col_restore = st.columns([3, 1])
        col_name.write(f"{role.get('role_name')} | {format_time(role.get('updated_at'))}")
        if col_restore.button("恢复", key=f"restore_role_{role.get('target_role_id')}", use_container_width=True):
            if get_history_service().restore_candidate_target_role(candidate_id, role.get("target_role_id", "")):
                st.success("目标岗位已恢复。")
                st.rerun()
            else:
                st.error("恢复失败。")


def render_inactive_jobs(company_id: str, inactive_jobs: List[Dict[str, object]]) -> None:
    """渲染已停用岗位列表并提供恢复按钮。"""

    st.subheader("Inactive 岗位")
    if not inactive_jobs:
        st.write("暂无已停用岗位。")
        return
    for job in inactive_jobs:
        col_name, col_restore = st.columns([3, 1])
        col_name.write(f"{job.get('job_name')} | JD v{job.get('jd_version')} | {format_time(job.get('updated_at'))}")
        if col_restore.button("恢复", key=f"restore_job_{job.get('job_id')}", use_container_width=True):
            if get_history_service().restore_job_profile(company_id, job.get("job_id", "")):
                st.success("岗位已恢复。")
                st.rerun()
            else:
                st.error("恢复失败。")


def render_candidate_history_center(identity_config: Dict[str, str]) -> None:
    """渲染 Candidate 历史分析页面。"""

    st.subheader("历史分析记录")
    candidate_id = identity_config.get("candidate_id", "")
    roles = get_history_service().list_candidate_target_roles(candidate_id)
    role_options = [{"target_role_id": "", "role_name": "全部求职方向"}] + roles
    selected_filter_role = st.selectbox(
        "按目标岗位筛选",
        role_options,
        format_func=lambda item: item.get("role_name", "未命名方向"),
    )
    records = load_history_records(
        actor_type="candidate",
        candidate_id=candidate_id,
        company_id="",
        target_role_id=selected_filter_role.get("target_role_id", ""),
    )
    if not records:
        st.info("暂无历史分析记录。完成一次新建分析后，这里会出现历史报告。")
        return

    left_col, right_col = st.columns([1, 2])
    with left_col:
        selected_id = render_record_selector(records, "选择历史记录")
        render_candidate_history_table(records)
    with right_col:
        selected = get_visible_record(selected_id, "candidate", candidate_id, "")
        if selected:
            render_candidate_record_detail(selected, candidate_id)

    render_candidate_compare(records, candidate_id)


def render_hr_history_center(identity_config: Dict[str, str]) -> None:
    """渲染 HR 候选人评估历史中心。"""

    st.subheader("Candidate Evaluation Center")
    company_id = identity_config.get("company_id", "")
    jobs = get_history_service().list_job_profiles(company_id)
    job_options = [{"job_id": "", "job_name": "全部岗位"}] + jobs
    selected_filter_job = st.selectbox(
        "按岗位筛选",
        job_options,
        format_func=lambda item: item.get("job_name", "未命名岗位"),
    )
    records = load_history_records(
        actor_type="hr",
        candidate_id="",
        company_id=company_id,
        job_id=selected_filter_job.get("job_id", ""),
    )
    if not records:
        st.info("暂无候选人评估记录。完成一次 HR 筛选后，这里会出现历史结果。")
        return

    sort_mode = st.selectbox("排序方式", ["创建时间倒序", "基础分倒序", "HR 调整分倒序"], index=0)
    records = sort_history_records(records, sort_mode)
    left_col, right_col = st.columns([1, 2])
    with left_col:
        selected_id = render_record_selector(records, "选择候选人评估")
        render_hr_history_table(records)
    with right_col:
        selected = get_visible_record(selected_id, "hr", "", company_id)
        if selected:
            render_hr_record_detail(selected, company_id)


def load_history_records(
    actor_type: str,
    candidate_id: str,
    company_id: str,
    job_id: str = "",
    target_role_id: str = "",
) -> List[Dict[str, object]]:
    """按当前租户身份加载历史分析记录。"""

    search = st.text_input("搜索", placeholder="岗位、技能、analysis_id、resume_hash")
    page_size = st.selectbox("每页数量", [5, 10, 20, 50], index=1)
    page = st.number_input("页码", min_value=1, value=1, step=1)
    try:
        result = get_history_service().list_analysis_records(
            actor_type=actor_type,
            candidate_id=candidate_id,
            company_id=company_id,
            job_id=job_id,
            target_role_id=target_role_id,
            search=search.strip(),
            page=int(page),
            page_size=int(page_size),
        )
    except ValueError as exc:
        st.error(str(exc))
        return []
    st.caption(
        f"共 {result.get('total', 0)} 条，第 {result.get('page', 1)} / {result.get('total_pages', 1)} 页"
    )
    return list(result.get("records") or [])


def render_record_selector(records: List[Dict[str, object]], label: str) -> str:
    """渲染历史记录选择器并返回 analysis_id。"""

    options = [str(record.get("analysis_id")) for record in records]
    labels = {str(record.get("analysis_id")): build_record_label(record) for record in records}
    current_analysis_id = str(st.session_state.get("current_analysis_id") or "")
    selector_key = build_history_selector_key(label)
    if current_analysis_id in options and st.session_state.get(selector_key) != current_analysis_id:
        st.session_state[selector_key] = current_analysis_id
    elif st.session_state.get(selector_key) not in options:
        st.session_state[selector_key] = current_analysis_id if current_analysis_id in options else options[0]
    selected_id = st.selectbox(
        label,
        options,
        format_func=lambda value: labels.get(value, value),
        key=selector_key,
        on_change=sync_history_selector_state,
        args=(selector_key,),
    )
    if selected_id and selected_id != current_analysis_id:
        st.session_state["current_analysis_id"] = selected_id
        persist_ui_state()
    return selected_id


def render_candidate_history_table(records: List[Dict[str, object]]) -> None:
    """渲染 Candidate 历史记录摘要列表。"""

    rows = []
    for record in records:
        rows.append(
            {
                "分析时间": format_time(record.get("created_at")),
                "目标岗位": record.get("target_role") or "未命名岗位",
                "原始文件名": record.get("original_filename") or record.get("resume_file_name") or "未记录",
                "文件状态": get_record_file_status(record),
                "文件大小": get_record_file_size(record),
                "基础匹配分": record.get("base_match_score"),
                "缺失技能数": len(record.get("missing_skills") or []),
                "resume_hash": short_text(record.get("resume_hash"), 12),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_hr_history_table(records: List[Dict[str, object]]) -> None:
    """渲染 HR 候选人评估记录摘要列表。"""

    rows = []
    for record in records:
        rows.append(
            {
                "岗位": record.get("target_role") or record.get("job_id") or "未命名岗位",
                "候选人": build_candidate_summary(record),
                "原始文件名": record.get("original_filename") or record.get("resume_file_name") or "未记录",
                "文件状态": get_record_file_status(record),
                "文件大小": get_record_file_size(record),
                "基础分": record.get("base_match_score"),
                "HR 调整分": record.get("hr_adjusted_score"),
                "招聘建议": record.get("hr_decision") or "暂无",
                "风险等级": build_risk_level(record),
                "创建时间": format_time(record.get("created_at")),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_candidate_record_detail(record: Dict[str, object], candidate_id: str) -> None:
    """渲染 Candidate 历史报告详情。"""

    st.subheader("报告详情")
    render_common_record_metrics(record)
    st.write(f"analysis_id：`{record.get('analysis_id')}`")
    st.write(f"resume_hash：`{record.get('resume_hash')}`")
    render_uploaded_file_panel(record, "candidate", candidate_id, "")
    with st.expander("JD", expanded=False):
        st.write(record.get("jd_text") or "暂无 JD。")
    render_list("缺失技能", to_string_list(record.get("missing_skills")), "暂无缺失技能。")
    render_list("优化建议", to_string_list(record.get("optimization_suggestions")), "暂无优化建议。")
    render_list("学习建议", to_string_list(record.get("learning_suggestions")), "暂无学习建议。")
    render_numbered_list("面试题", to_string_list(record.get("interview_questions")), "暂无面试题。")
    render_record_report_downloads(record, "candidate", candidate_id, "")
    render_record_management(record, "candidate", candidate_id, "")


def render_hr_record_detail(record: Dict[str, object], company_id: str) -> None:
    """渲染 HR 历史评估详情。"""

    st.subheader("候选人评估详情")
    render_common_record_metrics(record)
    st.write(f"analysis_id：`{record.get('analysis_id')}`")
    st.write(f"岗位名称：{record.get('job_name') or record.get('target_role') or '未记录'}")
    st.write(f"候选人：{build_candidate_summary(record)}")
    render_uploaded_file_panel(record, "hr", "", company_id)
    render_list("HR 风险因素", to_string_list(record.get("hr_risk_factors")), "暂无风险因素。")
    render_numbered_list("面试追问", to_string_list(record.get("interview_questions")), "暂无面试追问。")
    st.info(f"录用建议：{record.get('hr_decision') or '暂无'}")
    if record.get("ranking_result"):
        st.write(record.get("ranking_result"))
    render_record_report_downloads(record, "hr", "", company_id)
    render_record_management(record, "hr", "", company_id)


def render_common_record_metrics(record: Dict[str, object]) -> None:
    """渲染历史详情的通用指标。"""

    base_score = float(record.get("base_match_score") or 0)
    candidate_score = float(record.get("candidate_display_score") or base_score)
    hr_score = float(record.get("hr_adjusted_score") or base_score)
    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("基础匹配分", f"{base_score:.2f}")
    col_b.metric("Candidate 展示分", f"{candidate_score:.2f}")
    col_c.metric("HR 调整分", f"{hr_score:.2f}")
    col_d.metric("评分可信度", str(record.get("score_reliability") or "normal"))
    st.info(str(record.get("match_reason") or "暂无匹配理由。"))


def render_uploaded_file_panel(
    record: Dict[str, object],
    actor_type: str,
    candidate_id: str,
    company_id: str,
) -> None:
    """渲染历史分析关联的上传文件信息和操作。"""

    file_id = str(record.get("file_id") or "")
    if not file_id:
        st.info("该历史记录未关联原始上传文件。")
        return
    metadata = FileStorageService().get_file_metadata(
        file_id=file_id,
        actor_type=actor_type,
        candidate_id=candidate_id,
        company_id=company_id,
    )
    if not metadata:
        st.warning("原始文件不可访问或无权查看，仅保留分析结果。")
        return
    display = build_analysis_file_display(record, metadata)
    st.subheader("上传文件")
    col_name, col_status, col_size, col_hash = st.columns(4)
    col_name.metric("本次文件", display["analysis_original_filename"])
    col_status.metric("文件类型", display["analysis_file_type"])
    col_size.metric("文件大小", format_file_size(metadata.get("file_size")))
    col_hash.metric("fingerprint", short_text(metadata.get("resume_fingerprint_hash") or metadata.get("resume_hash"), 12))
    st.caption(f"本次上传/分析时间：{display['analysis_created_at']}")
    if display["is_duplicate_resume"]:
        st.info(
            "已识别为同一简历，归属主简历："
            f"{display['canonical_original_filename']}，"
            f"fingerprint：{display['fingerprint']}"
        )
    if metadata.get("status") == "expired":
        st.warning("原始文件已过期，仅保留分析结果。")
        return
    analysis_id = str(record.get("analysis_id") or file_id)
    show_debug = render_toggle_panel_button(
        label_show="显示文件调试信息",
        label_hide="隐藏文件调试信息",
        state_key=build_toggle_state_key(actor_type, analysis_id, "file_debug"),
        button_key=build_toggle_button_key(actor_type, analysis_id, "file_debug"),
    )
    if show_debug:
        st.text_input("analysis_original_filename", value=display["analysis_original_filename"], disabled=True)
        st.text_input("canonical_original_filename", value=display["canonical_original_filename"], disabled=True)
        st.text_input("stored_filename", value=str(metadata.get("stored_filename") or ""), disabled=True)
        st.text_input("file_path", value=str(metadata.get("file_path") or ""), disabled=True)
        st.text_input("raw_text_hash", value=str(metadata.get("raw_text_hash") or record.get("raw_text_hash") or ""), disabled=True)
        st.text_input("dedup_hit", value=str(metadata.get("dedup_hit", False)), disabled=True)
        st.text_input("dedup_source_file_id", value=str(metadata.get("dedup_source_file_id") or ""), disabled=True)
    col_download, col_delete = st.columns(2)
    file_path = Path(str(metadata.get("file_path") or ""))
    with col_download:
        if metadata.get("status") == "active" and file_path.exists():
            st.download_button(
                "下载原始文件",
                data=file_path.read_bytes(),
                file_name=str(metadata.get("original_filename") or metadata.get("stored_filename") or "resume"),
                mime=str(metadata.get("content_type") or "application/octet-stream"),
                use_container_width=True,
                key=f"download_file_{file_id}",
            )
        else:
            st.info("原始文件不可下载。")
    with col_delete:
        if st.button("删除原始文件", key=f"delete_file_{file_id}", use_container_width=True):
            deleted = FileStorageService().mark_file_deleted(
                file_id=file_id,
                actor_type=actor_type,
                candidate_id=candidate_id,
                company_id=company_id,
            )
            if deleted:
                st.success("原始文件已软删除。")
                st.rerun()
            else:
                st.error("删除失败：文件不存在或无权删除。")


def render_toggle_panel_button(
    label_show: str,
    label_hide: str,
    state_key: str,
    button_key: str,
) -> bool:
    """渲染单击立即生效的开关按钮，并返回当前显示状态。"""

    current = get_bool_state(st.session_state, state_key)
    label = label_hide if current else label_show
    if st.button(label, key=button_key, use_container_width=True):
        toggle_bool_state(st.session_state, state_key)
        st.rerun()
    return get_bool_state(st.session_state, state_key)


def render_record_report_downloads(
    record: Dict[str, object],
    actor_type: str,
    candidate_id: str,
    company_id: str,
) -> None:
    """渲染 Markdown 和 PDF 导出按钮，并记录导出审计。"""

    report = str(record.get("report_content") or "暂无报告内容。")
    analysis_id = str(record.get("analysis_id") or "analysis")
    col_md, col_pdf = st.columns(2)
    with col_md:
        if st.download_button(
            "导出 Markdown",
            data=report,
            file_name=f"{analysis_id}.md",
            mime="text/markdown",
            use_container_width=True,
        ):
            write_history_audit(actor_type, "export_markdown", analysis_id, candidate_id, company_id)
    with col_pdf:
        if st.download_button(
            "导出 PDF",
            data=build_simple_pdf_bytes(report),
            file_name=f"{analysis_id}.pdf",
            mime="application/pdf",
            use_container_width=True,
        ):
            write_history_audit(actor_type, "export_pdf", analysis_id, candidate_id, company_id)


def render_record_management(
    record: Dict[str, object],
    actor_type: str,
    candidate_id: str,
    company_id: str,
) -> None:
    """渲染历史记录管理按钮。"""

    analysis_id = str(record.get("analysis_id") or "")
    col_reanalyze, col_delete = st.columns(2)
    with col_reanalyze:
        if st.button("重新分析", key=f"reanalyze_{analysis_id}", use_container_width=True):
            write_history_audit(actor_type, "reanalyze", analysis_id, candidate_id, company_id)
            st.session_state["history_prefill_jd"] = record.get("jd_text") or ""
            st.info("请切换到“新建分析”并重新上传简历，历史 JD 已记录在调试信息中。")
    with col_delete:
        if st.button("删除记录", key=f"delete_{analysis_id}", use_container_width=True):
            deleted = get_history_service().delete_analysis_record(
                analysis_id=analysis_id,
                actor_type=actor_type,
                candidate_id=candidate_id,
                company_id=company_id,
                action_user_id=candidate_id or company_id,
            )
            if deleted:
                st.success("记录已删除，刷新页面后生效。")
            else:
                st.error("删除失败：记录不存在或无权删除。")


def render_candidate_compare(records: List[Dict[str, object]], candidate_id: str) -> None:
    """渲染 Candidate 历史分析对比功能。"""

    if len(records) < 2:
        return
    st.divider()
    st.subheader("历史报告对比")
    options = [str(record.get("analysis_id")) for record in records]
    labels = {str(record.get("analysis_id")): build_record_label(record) for record in records}
    col_a, col_b = st.columns(2)
    with col_a:
        left_id = st.selectbox("历史记录 A", options, format_func=lambda value: labels.get(value, value))
    with col_b:
        right_id = st.selectbox("历史记录 B", options, index=1, format_func=lambda value: labels.get(value, value))
    if left_id == right_id:
        st.warning("请选择两条不同记录进行对比。")
        return
    left = get_visible_record(left_id, "candidate", candidate_id, "")
    right = get_visible_record(right_id, "candidate", candidate_id, "")
    if left and right:
        render_compare_result(left, right)


def render_compare_result(left: Dict[str, object], right: Dict[str, object]) -> None:
    """展示两条历史分析的分数和缺失技能变化。"""

    left_score = float(left.get("base_match_score") or 0)
    right_score = float(right.get("base_match_score") or 0)
    left_missing = set(to_string_list(left.get("missing_skills")))
    right_missing = set(to_string_list(right.get("missing_skills")))
    added_skills = sorted(left_missing - right_missing)
    still_missing = sorted(left_missing.intersection(right_missing))
    new_missing = sorted(right_missing - left_missing)
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("记录 A", f"{left_score:.2f}")
    col_b.metric("记录 B", f"{right_score:.2f}")
    col_c.metric("变化", f"{right_score - left_score:+.2f}")
    render_list("已改善技能", added_skills, "暂无明显改善项。")
    render_list("仍缺技能", still_missing, "暂无共同缺失项。")
    render_list("新增缺失", new_missing, "暂无新增缺失项。")


def get_visible_record(
    analysis_id: str,
    actor_type: str,
    candidate_id: str,
    company_id: str,
) -> Dict[str, object]:
    """按当前租户身份读取可见的历史详情。"""

    return get_history_service().get_analysis_record(
        analysis_id=analysis_id,
        actor_type=actor_type,
        candidate_id=candidate_id,
        company_id=company_id,
        action_user_id=candidate_id or company_id,
    )


def build_history_selector_key(label: str) -> str:
    """根据下拉菜单标题生成稳定的 session_state key。"""

    slug = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", label or "history").strip("_")
    return f"history_record_selector_{slug or 'history'}"


def sync_history_selector_state(selector_key: str) -> None:
    """在历史记录下拉变化时立即同步当前 analysis_id 并持久化。"""

    selected_id = str(st.session_state.get(selector_key) or "")
    if selected_id:
        st.session_state["current_analysis_id"] = selected_id
        persist_ui_state()


def apply_created_job_state(job: Dict[str, object], form_version: int) -> None:
    """岗位创建成功后更新当前岗位选择并推进表单版本以清空输入框。"""

    st.session_state["job_create_success_message"] = f"岗位创建成功：{job.get('job_name')}"
    st.session_state["selected_job_id"] = job.get("job_id", "")
    st.session_state["selected_job_name"] = job.get("job_name", "")
    st.session_state["selected_job_jd_text"] = job.get("jd_text", "")
    st.session_state["create_job_form_version"] = form_version + 1


def write_history_audit(
    actor_type: str,
    action: str,
    analysis_id: str,
    candidate_id: str,
    company_id: str,
) -> None:
    """写入历史中心操作审计。"""

    get_history_service().write_audit_log(
        user_id=candidate_id or company_id,
        actor_type=actor_type,
        action=action,
        analysis_id=analysis_id,
        candidate_id=candidate_id,
        company_id=company_id,
    )


def sort_history_records(records: List[Dict[str, object]], sort_mode: str) -> List[Dict[str, object]]:
    """根据 HR 页面选择的排序方式排序记录。"""

    if sort_mode == "基础分倒序":
        return sorted(records, key=lambda item: float(item.get("base_match_score") or 0), reverse=True)
    if sort_mode == "HR 调整分倒序":
        return sorted(records, key=lambda item: float(item.get("hr_adjusted_score") or 0), reverse=True)
    return sorted(records, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def build_record_label(record: Dict[str, object]) -> str:
    """构造历史记录下拉选项标签。"""

    title = str(record.get("target_role") or record.get("job_id") or "未命名岗位")
    score = record.get("base_match_score")
    created_at = format_time(record.get("created_at"))
    return f"{created_at} | {title[:24]} | {score} 分"


def build_analysis_file_display(record: Dict[str, object], metadata: Dict[str, object]) -> Dict[str, object]:
    """构造历史详情中的本次文件与主简历文件展示信息。"""

    analysis_filename = str(
        record.get("original_filename")
        or record.get("resume_file_name")
        or metadata.get("original_filename")
        or "未知"
    )
    canonical_filename = str(metadata.get("original_filename") or metadata.get("stored_filename") or "未知")
    parse_result = record.get("document_parse_result") or {}
    file_type = ""
    if isinstance(parse_result, dict):
        file_type = str(parse_result.get("file_type") or "")
    file_type = file_type or Path(analysis_filename).suffix.lstrip(".").lower() or "unknown"
    fingerprint = str(
        record.get("resume_fingerprint_hash")
        or metadata.get("resume_fingerprint_hash")
        or record.get("resume_hash")
        or metadata.get("resume_hash")
        or ""
    )
    is_duplicate_resume = bool(
        record.get("dedup_hit")
        or record.get("duplicate_reused")
        or record.get("duplicate_of_file_id")
        or (
            analysis_filename
            and canonical_filename
            and analysis_filename != "未知"
            and canonical_filename != "未知"
            and analysis_filename != canonical_filename
        )
    )
    return {
        "analysis_original_filename": analysis_filename,
        "analysis_file_type": file_type,
        "analysis_created_at": format_time(record.get("created_at") or metadata.get("created_at")),
        "canonical_original_filename": canonical_filename,
        "fingerprint": fingerprint,
        "is_duplicate_resume": is_duplicate_resume,
    }


def build_candidate_summary(record: Dict[str, object]) -> str:
    """从历史记录中生成候选人摘要。"""

    resume_info = record.get("resume_info") or {}
    if isinstance(resume_info, dict):
        return str(resume_info.get("name") or resume_info.get("summary") or record.get("candidate_id") or "候选人")
    return str(record.get("candidate_id") or "候选人")


def get_record_file_status(record: Dict[str, object]) -> str:
    """读取历史记录关联文件状态。"""

    metadata = get_record_file_metadata(record)
    return str(metadata.get("status") or "未关联")


def get_record_file_size(record: Dict[str, object]) -> str:
    """读取历史记录关联文件大小。"""

    metadata = get_record_file_metadata(record)
    return format_file_size(metadata.get("file_size")) if metadata else "-"


def get_record_file_metadata(record: Dict[str, object]) -> Dict[str, object]:
    """按 analysis_record 的租户字段安全读取文件 metadata。"""

    file_id = str(record.get("file_id") or "")
    if not file_id:
        return {}
    return FileStorageService().get_file_metadata(
        file_id=file_id,
        actor_type=str(record.get("actor_type") or ""),
        candidate_id=str(record.get("candidate_id") or ""),
        company_id=str(record.get("company_id") or ""),
    )


def build_risk_level(record: Dict[str, object]) -> str:
    """根据 HR 调整分和风险因素生成风险等级。"""

    score = float(record.get("hr_adjusted_score") or record.get("base_match_score") or 0)
    risk_count = len(record.get("hr_risk_factors") or [])
    if score < 55 or risk_count >= 3:
        return "高"
    if score < 70 or risk_count:
        return "中"
    return "低"


def format_time(value: object) -> str:
    """格式化历史记录时间。"""

    return format_display_time(value, DISPLAY_TIMEZONE)


def localize_time_fields(value: object) -> object:
    """将展示数据中的常见 UTC 时间字段转换为配置时区。"""

    time_fields = {
        "created_at",
        "updated_at",
        "deleted_at",
        "expired_at",
        "timestamp",
        "start_time",
        "end_time",
        "expires_at",
    }
    if isinstance(value, list):
        return [localize_time_fields(item) for item in value]
    if isinstance(value, dict):
        localized = dict(value)
        for key in time_fields:
            if localized.get(key):
                localized[key] = format_time(localized.get(key))
        return localized
    return value


def short_text(value: object, length: int) -> str:
    """截断长文本以便在表格中展示。"""

    text = str(value or "")
    return text[:length] + ("..." if len(text) > length else "")


def format_file_size(value: object) -> str:
    """把字节数格式化为适合页面展示的文件大小。"""

    size = float(value or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def build_simple_pdf_bytes(markdown_text: str) -> bytes:
    """生成极简 PDF 字节流，用于无额外依赖的报告导出。"""

    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, StreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = StreamObject()
    stream._data = build_pdf_stream(markdown_text)
    page[NameObject("/Contents")] = writer._add_object(stream)
    import io

    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_pdf_stream(markdown_text: str) -> bytes:
    """把报告文本转换为 PDF 内容流，非 ASCII 字符会被安全替换。"""

    lines = sanitize_pdf_text(markdown_text).splitlines()[:42]
    commands = ["BT", "/F1 10 Tf", "56 750 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -16 Td")
        commands.append(f"({escape_pdf_text(line[:90])}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def sanitize_pdf_text(text: str) -> str:
    """将报告文本转换为内置 PDF 字体可写入的安全字符。"""

    return (text or "No report").encode("latin-1", errors="replace").decode("latin-1")


def escape_pdf_text(text: str) -> str:
    """转义 PDF 字符串中的括号和反斜杠。"""

    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def render_knowledge_page() -> None:
    """渲染知识库页面、导入操作和 RAG 诊断。"""

    st.header("知识库")
    diagnostics = get_knowledge_base_diagnostics()
    render_rag_diagnostics(diagnostics)
    if diagnostics["knowledge_base_file_count"] == 0:
        st.warning("知识库尚未导入，请先上传知识文件或点击创建默认知识库。")
    col_default, col_ingest = st.columns(2)
    with col_default:
        if st.button("创建默认知识库", use_container_width=True):
            path = create_default_knowledge_base()
            st.success(f"默认知识库已创建：{path.name}")
            st.rerun()
    with col_ingest:
        if st.button("导入知识库", use_container_width=True):
            result = ingest_knowledge_base()
            st.session_state["last_knowledge_ingest_result"] = result
            st.rerun()

        last_result = st.session_state.get("last_knowledge_ingest_result")
        if last_result:
            files = int(last_result.get("files") or 0)
            chunks = int(last_result.get("chunks") or 0)
            inserted = int(last_result.get("inserted") or 0)
            skipped = int(last_result.get("skipped") or 0)
            total_documents = int(last_result.get("total_documents") or last_result.get("total") or 0)

            if inserted > 0:
                st.success(f"知识库导入完成：新增 {inserted} 个知识块。")
            elif skipped > 0:
                st.info("未写入新内容：知识块已存在，已自动跳过重复数据。")
            else:
                st.warning("未发现可导入的知识库内容。")

            col_files, col_chunks, col_inserted, col_skipped, col_total = st.columns(5)
            col_files.metric("扫描文件", files)
            col_chunks.metric("扫描片段", chunks)
            col_inserted.metric("新增", inserted)
            col_skipped.metric("跳过重复", skipped)
            col_total.metric("当前总数", total_documents)

    query = st.text_input("RAG 检索测试", value="LangGraph RAG 面试题")
    top_k = st.slider("Top K", min_value=1, max_value=10, value=5)
    if st.button("测试检索", use_container_width=True):
        filters = {"scope": "shared"}
        docs = VectorStoreClient("shared_knowledge").similarity_search(
            query=query,
            top_k=top_k,
            filters=filters,
        )
        diagnostics = get_knowledge_base_diagnostics(
            retrieval_query=query,
            retrieval_top_k=top_k,
            retrieval_filters=filters,
        )
        diagnostics["retrieved_count"] = len(docs)
        render_rag_diagnostics(diagnostics)
        render_context([doc.get("text", "") for doc in docs])


def render_debug_page(identity_config: Dict[str, str]) -> None:
    """渲染调试信息页面。"""

    st.header("调试信息")
    st.json(identity_config)
    st.subheader("前端持久化状态")
    st.json(
        {
            "session_id": st.session_state.get("session_id", ""),
            "actor_type": st.session_state.get("actor_type", ""),
            "current_page": st.session_state.get("current_page", ""),
            "candidate_id": st.session_state.get("candidate_id", ""),
            "company_id": st.session_state.get("company_id", ""),
            "selected_job_id": st.session_state.get("selected_job_id", ""),
            "selected_target_role_id": st.session_state.get("selected_target_role_id", ""),
            "current_analysis_id": st.session_state.get("current_analysis_id", ""),
            "ui_state_loaded_from": st.session_state.get("ui_state_loaded_from", "new"),
            "ui_state_saved_to": st.session_state.get("ui_state_saved_to", ""),
        }
    )
    if st.session_state.get("history_prefill_jd"):
        st.text_area("最近重新分析记录的历史 JD", value=st.session_state["history_prefill_jd"], height=160)
    actor_type = identity_config.get("actor_type", "candidate")
    logs = get_history_service().get_audit_logs(
        actor_type=actor_type,
        candidate_id=identity_config.get("candidate_id", "") if actor_type == "candidate" else "",
        company_id=identity_config.get("company_id", "") if actor_type == "hr" else "",
    )
    st.subheader("审计日志")
    if logs:
        st.dataframe(localize_time_fields(logs), use_container_width=True, hide_index=True)
    else:
        st.write("暂无审计日志。")

def render_monitoring_dashboard() -> None:
    """渲染 Observability V1 监控中心。"""

    st.header("监控中心")

    monitor = get_monitor_service()
    summary = monitor.get_run_summary()

    col_total, col_success, col_duration, col_failed = st.columns(4)
    col_total.metric("运行总数", int(summary.get("total_runs") or 0))
    col_success.metric("成功率", f"{float(summary.get('success_rate') or 0):.2f}%")
    col_duration.metric("平均耗时", f"{float(summary.get('average_duration') or 0):.2f} ms")
    col_failed.metric("失败运行", int(summary.get("failed_runs") or 0))

    with st.expander("Agent Metrics", expanded=True):
        st.caption(
            "Agent Metrics 说明：node_name 表示节点或工具名称；"
            "average_duration 表示平均耗时；total 表示该节点累计执行次数。"
        )
        agent_metrics = summary.get("agent_metrics") or []
        if agent_metrics:
            st.dataframe(
                agent_metrics,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无节点指标。")

    col_rag, col_llm = st.columns(2)

    with col_rag:
        st.subheader("RAG Metrics")
        rag_metrics = summary.get("rag_metrics") or {}
        st.json(rag_metrics)
        st.caption(
            "字段说明：retrieval_count 表示 RAG 检索调用次数；"
            "retrieval_hit_count 表示返回过有效上下文的次数；"
            "retrieval_miss_count 表示未返回有效上下文的次数；"
            "average_retrieval_time 表示平均检索耗时。"
        )

    with col_llm:
        st.subheader("LLM Metrics")
        llm_metrics = summary.get("llm_metrics") or {}
        st.json(llm_metrics)
        st.caption(
            "字段说明：llm_calls 表示大模型调用次数；"
            "llm_failures 表示失败调用次数；"
            "average_response_time 表示平均响应耗时；"
            "fallback_calls 表示降级调用次数。"
        )

    if st.button("导出 Excel", use_container_width=True):
        paths = monitor.export_excel()
        st.success("导出完成。")
        st.json(paths)

    recent_runs = monitor.get_recent_runs(limit=20)
    recent_errors = monitor.get_recent_errors(limit=20)

    run_tab, error_tab, detail_tab, audit_tab = st.tabs(
        ["最近 Run Log", "最近 Error Trace", "Analysis Detail", "审计日志"]
    )

    with run_tab:
        st.caption(
            "Run Log 说明：run_id 表示一次工作流运行；analysis_id 对应分析记录；"
            "actor_type 表示运行身份；workflow_name 表示工作流名称；"
            "duration_ms 表示运行耗时；status 表示运行结果。"
        )
        if recent_runs:
            st.dataframe(
                localize_time_fields(recent_runs),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无 Run Log。")

    with error_tab:
        st.caption(
            "Error Trace 说明：展示最近失败或异常的运行记录，用于定位节点、工具或模型调用错误。"
        )
        if recent_errors:
            st.dataframe(
                localize_time_fields(recent_errors),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无 Error Trace。")

    with detail_tab:
        render_monitoring_analysis_detail(recent_runs)

    with audit_tab:
        st.caption(
            "审计日志说明：analysis_id 仅在查看、删除、导出报告等分析相关操作中存在；"
            "candidate_id 主要用于求职者侧操作；company_id / job_id 主要用于 HR 侧操作。"
            "空值不一定代表异常，可能表示该操作本身不涉及对应对象。"
        )

        try:
            audit_logs = get_history_service().list_audit_logs(limit=50)
        except AttributeError:
            audit_logs = []

        if audit_logs:
            display_logs = []
            for item in localize_time_fields(audit_logs):
                display_logs.append(
                    {
                        "时间": item.get("created_at") or item.get("timestamp") or "-",
                        "身份": item.get("actor_type") or "-",
                        "操作": item.get("action") or "-",
                        "analysis_id": item.get("analysis_id") or "-",
                        "candidate_id": item.get("candidate_id") or "-",
                        "company_id": item.get("company_id") or "-",
                        "job_id": item.get("job_id") or "-",
                        "user_id": item.get("user_id") or "-",
                    }
                )

            st.dataframe(
                display_logs,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("暂无审计日志。")
# def render_monitoring_dashboard() -> None:
#     """渲染 Observability V1 监控中心。"""
#
#     st.header("监控中心")
#     monitor = get_monitor_service()
#     summary = monitor.get_run_summary()
#     col_total, col_success, col_duration, col_failed = st.columns(4)
#     col_total.metric("运行总数", int(summary.get("total_runs") or 0))
#     col_success.metric("成功率", f"{float(summary.get('success_rate') or 0):.2f}%")
#     col_duration.metric("平均耗时", f"{float(summary.get('average_duration') or 0):.2f} ms")
#     col_failed.metric("失败运行", int(summary.get("failed_runs") or 0))
#
#     with st.expander("Agent Metrics", expanded=True):
#         agent_metrics = summary.get("agent_metrics") or []
#         if agent_metrics:
#             st.dataframe(agent_metrics, use_container_width=True, hide_index=True)
#         else:
#             st.write("暂无节点指标。")
#
#     col_rag, col_llm = st.columns(2)
#     with col_rag:
#         st.subheader("RAG Metrics")
#         st.json(summary.get("rag_metrics") or {})
#     with col_llm:
#         st.subheader("LLM Metrics")
#         st.json(summary.get("llm_metrics") or {})
#
#     if st.button("导出 Excel", use_container_width=True):
#         paths = monitor.export_excel()
#         st.success("导出完成。")
#         st.json(paths)
#
#     recent_runs = monitor.get_recent_runs(limit=20)
#     recent_errors = monitor.get_recent_errors(limit=20)
#     run_tab, error_tab, detail_tab = st.tabs(["最近 Run Log", "最近 Error Trace", "Analysis Detail"])
#     with run_tab:
#         if recent_runs:
#             st.dataframe(localize_time_fields(recent_runs), use_container_width=True, hide_index=True)
#         else:
#             st.write("暂无 Run Log。")
#     with error_tab:
#         if recent_errors:
#             st.dataframe(localize_time_fields(recent_errors), use_container_width=True, hide_index=True)
#         else:
#             st.write("暂无 Error Trace。")
#     with detail_tab:
#         render_monitoring_analysis_detail(recent_runs)


def render_monitoring_analysis_detail(recent_runs: List[Dict[str, object]]) -> None:
    """渲染指定 analysis_id 的运行详情和节点时间线。"""

    analysis_options = [
        str(row.get("analysis_id"))
        for row in recent_runs
        if row.get("analysis_id")
    ]
    if not analysis_options:
        st.write("暂无可查看的 analysis_id。")
        return
    selected_analysis_id = st.selectbox("analysis_id", analysis_options)
    detail = get_monitor_service().get_analysis_detail(selected_analysis_id)
    run = detail.get("run") or {}
    nodes = detail.get("nodes") or []
    errors = detail.get("errors") or []
    st.subheader("Run Detail")
    st.json(localize_time_fields(run))
    st.subheader("Node Timeline")
    if nodes:
        st.dataframe(localize_time_fields(nodes), use_container_width=True, hide_index=True)
    else:
        st.write("暂无节点时间线。")
    st.subheader("Error Trace")
    if errors:
        st.dataframe(localize_time_fields(errors), use_container_width=True, hide_index=True)
    else:
        st.write("暂无错误。")


def render_empty_state() -> None:
    """渲染用户提交输入前看到的页面，并优先恢复当前分析结果。"""

    restored = restore_current_analysis_result()
    if restored:
        render_result(restored)
        return
    if st.session_state.get("task_status") in {TASK_STATUS_GENERATING}:
        st.metric("匹配分数", "--")
        st.info("当前分析仍在生成中，请稍后刷新或进入历史分析查看结果。")
        return
    st.metric("匹配分数", "--")
    st.info("等待分析")


def restore_current_analysis_result() -> Dict[str, object]:
    """根据 current_analysis_id 和当前身份从历史记录中恢复分析结果。"""

    analysis_id = str(st.session_state.get("current_analysis_id") or "")
    if not analysis_id:
        return {}
    identity = build_identity_config_from_session()
    actor_type = identity.get("actor_type") or "candidate"
    try:
        return get_history_service().get_analysis_record(
            analysis_id=analysis_id,
            actor_type=actor_type,
            candidate_id=identity.get("candidate_id", ""),
            company_id=identity.get("company_id", ""),
        )
    except ValueError:
        return {}


def render_result(state: Dict[str, object]) -> None:
    """用指标、标签页和可下载报告渲染分析结果。"""

    actor_type = str(state.get("actor_type") or "candidate")
    role_label = "企业招聘者" if actor_type == "hr" else "求职者"
    base_score = float(state.get("base_match_score") or state.get("match_score") or 0)
    candidate_display_score = float(state.get("candidate_display_score") or base_score)
    hr_adjusted_score = float(state.get("hr_adjusted_score") or base_score)
    final_display_score = float(state.get("final_display_score") or base_score)
    retry_count = int(state.get("retry_count") or 0)
    questions = to_string_list(state.get("interview_questions"))
    missing_skills = to_string_list(state.get("missing_skills"))
    suggestions = to_string_list(state.get("optimization_suggestions"))
    rag_context = to_string_list(state.get("rag_context"))
    final_report = str(state.get("final_report") or "")
    hiring_decision = str(state.get("hiring_decision") or "")
    hr_risk_factors = to_string_list(state.get("hr_risk_factors"))
    parse_result = state.get("document_parse_result") or {}

    role_col, base_col, display_col, llm_col = st.columns(4)
    role_col.metric("当前身份", role_label)
    base_col.metric("基础匹配分", f"{base_score:.2f}")
    if actor_type == "hr":
        display_col.metric("HR 风险调整分", f"{hr_adjusted_score:.2f}")
    else:
        display_col.metric("求职者展示分", f"{candidate_display_score:.2f}")
    llm_col.metric("大模型调用", "已启用" if state.get("llm_used") else "未启用")
    if actor_type == "hr" and hiring_decision:
        st.success(f"招聘决策：{hiring_decision}")
    elif actor_type != "hr":
        st.caption(f"优化重试次数：{retry_count}")
    if not state.get("llm_used") and state.get("llm_error"):
        st.warning(f"大模型未成功调用：{state.get('llm_error')}")
    render_parse_diagnostics(parse_result, state)

    st.progress(min(max(final_display_score / 100, 0), 1), text="JD 匹配度")
    st.info(str(state.get("match_reason") or "暂无匹配理由。"))

    advice_tab_label = "评估建议" if actor_type == "hr" else "优化建议"
    tab_summary, tab_optimize, tab_interview, tab_report, tab_rag = st.tabs(
        ["匹配概览", advice_tab_label, "面试题", "综合报告", "RAG 上下文"]
    )

    with tab_summary:
        render_list("缺失技能", missing_skills, "暂无明显缺失技能。")

    with tab_optimize:
        advice_items = build_advice_items(actor_type, final_display_score, suggestions, missing_skills)
        advice_title = "招聘评估建议" if actor_type == "hr" else "简历优化建议"
        render_list(advice_title, advice_items, "暂无建议。")
        if actor_type == "hr":
            render_list("HR 风险因素", hr_risk_factors, "暂无额外风险因素。")

    with tab_interview:
        render_numbered_list("定制面试题", questions, "暂未生成面试题。")

    with tab_report:
        st.markdown(final_report or "暂无综合报告。")
        st.download_button(
            "下载报告",
            data=final_report,
            file_name="ai_recruitment_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab_rag:
        render_context(rag_context)


def render_parse_diagnostics(parse_result: Dict[str, object], state: Dict[str, object]) -> None:
    """展示简历文档解析诊断信息。"""

    if not parse_result:
        return
    resume_text = str(state.get("resume_text") or "")
    quality_score = float(parse_result.get("quality_score") or 0)
    warnings = to_string_list(parse_result.get("warnings"))
    with st.expander("简历解析诊断", expanded=quality_score < 0.3):
        col_type, col_len, col_quality, col_reliability = st.columns(4)
        col_type.metric("文件类型", str(parse_result.get("file_type") or "未知"))
        col_len.metric("解析文本长度", int(parse_result.get("text_length") or 0))
        col_quality.metric("解析质量分", f"{quality_score:.2f}")
        col_reliability.metric("评分可信度", str(state.get("score_reliability") or "normal"))
        st.write(f"解析器：{parse_result.get('parser_name') or '未知'}")
        st.write(f"Resume Hash：{state.get('resume_hash') or '未生成'}")
        if warnings:
            for warning in warnings:
                st.warning(warning)
        if quality_score < 0.3:
            st.warning("该文件解析质量较低，建议上传 TXT/PDF 或检查 DOCX 是否使用复杂表格、图片扫描件。")
        st.text_area("文本预览前 500 字", value=resume_text[:500], height=180, disabled=True)
        if state.get("debug_trace"):
            st.json(state.get("debug_trace"))


def render_list(title: str, values: List[str], empty_text: str) -> None:
    """渲染项目符号列表，并提供友好的空状态。"""

    st.subheader(title)
    if not values:
        st.write(empty_text)
        return
    for value in values:
        st.write(f"- {value}")


def build_advice_items(
    actor_type: str,
    match_score: float,
    suggestions: List[str],
    missing_skills: List[str],
) -> List[str]:
    """根据身份和匹配分生成与分数一致的建议文案。"""

    if suggestions:
        return suggestions
    if actor_type == "hr":
        return build_hr_advice_items(match_score, missing_skills)
    return build_candidate_advice_items(match_score, missing_skills)


def build_candidate_advice_items(match_score: float, missing_skills: List[str]) -> List[str]:
    """根据匹配分生成求职者侧简历优化建议。"""

    if match_score >= 70:
        return ["当前匹配度较高，可补充项目量化成果、技术深度和业务影响来提升竞争力。"]
    skill_text = "、".join(missing_skills) if missing_skills else "JD 核心技能"
    return [
        f"当前匹配度偏低，建议优先补齐或强化：{skill_text}。",
        "补充与目标岗位相关的项目背景、技术方案、个人职责和可量化结果。",
        "如果缺少真实经验，不要虚构经历，可用学习项目、开源贡献或实验项目补足证明材料。",
    ]


def build_hr_advice_items(match_score: float, missing_skills: List[str]) -> List[str]:
    """根据匹配分生成 HR 侧评估建议。"""

    if match_score >= 70:
        return ["当前候选人与 JD 匹配度较高，建议进入面试，并重点验证项目真实性和技术深度。"]
    skill_text = "、".join(missing_skills) if missing_skills else "岗位关键能力"
    return [
        f"当前匹配度偏低，不建议直接推进到正式面试，可先进行补充筛选或电话初筛。",
        f"重点核验候选人是否具备：{skill_text}。",
        "如果岗位紧急，可将候选人放入备选池；如果岗位要求严格，建议优先筛选更高匹配候选人。",
    ]


def render_numbered_list(title: str, values: List[str], empty_text: str) -> None:
    """渲染编号列表，并提供友好的空状态。"""

    st.subheader(title)
    if not values:
        st.write(empty_text)
        return
    for index, value in enumerate(values, start=1):
        st.write(f"{index}. {value}")


def render_context(contexts: List[str]) -> None:
    """在可展开面板中渲染检索到的 RAG 上下文。"""

    if not contexts:
        st.warning("知识库暂无命中内容。")
        diagnostics = get_knowledge_base_diagnostics()
        diagnostics["retrieved_count"] = 0
        render_rag_diagnostics(diagnostics)
        st.write(
            "可能原因：data/knowledge_base 为空、尚未执行导入、向量库为空、metadata scope/filter 不匹配、"
            "query 太短或缺少关键词、embedding/vector backend 不可用。"
        )
        return
    for index, context in enumerate(contexts, start=1):
        with st.expander(f"上下文 {index}", expanded=index == 1):
            st.write(context)


def render_rag_diagnostics(diagnostics: Dict[str, object]) -> None:
    """渲染 RAG 诊断信息。"""

    with st.expander("RAG Diagnostics", expanded=not diagnostics.get("vector_store_doc_count")):
        col_files, col_docs, col_sources = st.columns(3)
        col_files.metric("知识库文件数量", diagnostics.get("knowledge_base_file_count", 0))
        col_docs.metric("向量库文档数量", diagnostics.get("vector_store_doc_count", 0))
        col_sources.metric("向量来源数量", diagnostics.get("vector_store_source_count", 0))
        st.write(f"最近导入时间：{diagnostics.get('last_ingest_time') or '未导入'}")
        st.write(f"retrieval_query：{diagnostics.get('retrieval_query') or '未执行'}")
        st.write(f"retrieval_top_k：{diagnostics.get('retrieval_top_k')}")
        st.write(f"retrieval_filters：{diagnostics.get('retrieval_filters')}")
        if diagnostics.get("retrieved_count") is not None:
            st.write(f"retrieved_count：{diagnostics.get('retrieved_count')}")
        warnings = to_string_list(diagnostics.get("retrieval_warnings"))
        if warnings:
            for warning in warnings:
                st.warning(warning)


def to_string_list(value: object) -> List[str]:
    """将可能缺失的工作流值转换为字符串列表。"""

    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


if __name__ == "__main__":
    main()
