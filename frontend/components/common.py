"""通用前端组件和格式化函数。"""

from frontend import legacy


render_list = legacy.render_list
"""渲染普通列表。"""

render_numbered_list = legacy.render_numbered_list
"""渲染编号列表。"""

render_error_box = legacy.st.error
"""渲染错误提示。"""

render_warning_box = legacy.st.warning
"""渲染警告提示。"""

safe_text = legacy.short_text
"""安全截断文本。"""
