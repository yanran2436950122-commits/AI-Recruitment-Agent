"""侧边栏组件。"""

from typing import Dict, Tuple

from frontend import legacy


def render_sidebar() -> Tuple[Dict[str, str], Dict[str, str]]:
    """渲染身份、模型配置和调试入口。"""

    identity_config = legacy.render_identity_sidebar()
    legacy.render_ui_state_warning()
    legacy.st.divider()
    llm_config = legacy.render_llm_sidebar()
    return identity_config, llm_config
