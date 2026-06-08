"""监控中心页面。"""

from frontend import legacy


def render_page() -> None:
    """渲染 Observability V1 监控中心。"""

    legacy.render_monitoring_dashboard()
