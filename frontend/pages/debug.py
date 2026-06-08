"""调试信息页面。"""

from frontend import legacy


def render_page(identity_config: dict) -> None:
    """渲染只读调试信息。"""

    legacy.render_debug_page(identity_config)
