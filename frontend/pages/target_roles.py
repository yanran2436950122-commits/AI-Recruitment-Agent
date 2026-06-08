"""Candidate 目标岗位管理页面。"""

from frontend import legacy


def render_page(identity_config: dict) -> None:
    """渲染 Candidate 目标岗位管理。"""

    legacy.render_candidate_target_role_management(identity_config)
