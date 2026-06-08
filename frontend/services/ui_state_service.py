"""前端 UI 状态服务适配器。"""

from frontend import legacy


def save_ui_state() -> None:
    """保存前端 UI 状态。"""

    legacy.persist_ui_state()


def restore_ui_state() -> None:
    """恢复前端 UI 状态。"""

    legacy.initialize_identity_state()
