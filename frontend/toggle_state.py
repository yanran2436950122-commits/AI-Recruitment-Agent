"""Streamlit 面板开关状态工具，避免按钮点击后需要二次触发。"""

from typing import Any, MutableMapping


def build_toggle_state_key(actor_type: str, analysis_id: str, panel_name: str) -> str:
    """构造包含身份、分析编号和面板名的稳定状态 key。"""

    return f"show_{_safe_key_part(panel_name)}_{_safe_key_part(actor_type)}_{_safe_key_part(analysis_id)}"


def build_toggle_button_key(actor_type: str, analysis_id: str, panel_name: str) -> str:
    """构造包含身份、分析编号和面板名的稳定按钮 key。"""

    return f"toggle_{_safe_key_part(panel_name)}_{_safe_key_part(actor_type)}_{_safe_key_part(analysis_id)}"


def get_bool_state(session_state: MutableMapping[str, Any], key: str) -> bool:
    """读取布尔开关状态，缺省时初始化为 False。"""

    if key not in session_state:
        session_state[key] = False
    return bool(session_state[key])


def toggle_bool_state(session_state: MutableMapping[str, Any], key: str) -> bool:
    """切换布尔开关状态并返回新值。"""

    session_state[key] = not get_bool_state(session_state, key)
    return bool(session_state[key])


def _safe_key_part(value: str) -> str:
    """把任意字符串转换为可用于 Streamlit key 的安全片段。"""

    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or "unknown"))
    return cleaned.strip("_") or "unknown"
