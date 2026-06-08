"""导出服务适配器。"""

from frontend import legacy


def export_monitoring_excel() -> dict:
    """导出监控中心 Excel 文件。"""

    return legacy.get_monitor_service().export_excel()
