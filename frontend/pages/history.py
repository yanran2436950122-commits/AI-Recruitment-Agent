"""历史分析中心页面。"""

from frontend import legacy


def render_page(identity_config: dict) -> None:
    """渲染 Candidate/HR 历史分析中心。"""

    legacy.render_history_center(identity_config)
