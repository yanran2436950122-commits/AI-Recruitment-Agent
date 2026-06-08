"""Streamlit 历史页开关状态测试。"""

from frontend.toggle_state import build_toggle_state_key, get_bool_state, toggle_bool_state


def test_state_key_includes_actor_type_and_analysis_id() -> None:
    """开关状态 key 应包含 actor_type 和 analysis_id，避免 Candidate/HR 冲突。"""

    candidate_key = build_toggle_state_key("candidate", "analysis_001", "file_debug")
    hr_key = build_toggle_state_key("hr", "analysis_001", "file_debug")

    assert candidate_key != hr_key
    assert "candidate" in candidate_key
    assert "analysis_001" in candidate_key


def test_initial_toggle_state_is_false() -> None:
    """首次读取开关状态时应初始化为 False。"""

    session_state = {}
    key = build_toggle_state_key("candidate", "analysis_init", "file_debug")

    assert get_bool_state(session_state, key) is False
    assert session_state[key] is False


def test_first_toggle_true_second_toggle_false() -> None:
    """第一次点击后为 True，第二次点击后恢复 False。"""

    session_state = {}
    key = build_toggle_state_key("candidate", "analysis_toggle", "file_debug")

    assert toggle_bool_state(session_state, key) is True
    assert toggle_bool_state(session_state, key) is False


def test_different_analysis_ids_are_isolated() -> None:
    """不同 analysis_id 的开关状态互不影响。"""

    session_state = {}
    left_key = build_toggle_state_key("candidate", "analysis_left", "file_debug")
    right_key = build_toggle_state_key("candidate", "analysis_right", "file_debug")

    toggle_bool_state(session_state, left_key)

    assert get_bool_state(session_state, left_key) is True
    assert get_bool_state(session_state, right_key) is False
