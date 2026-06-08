"""HR 岗位管理页面。"""

from frontend import legacy


def render_page(identity_config: dict) -> None:
    """渲染 HR 岗位管理。"""

    legacy.render_hr_job_management(identity_config)
