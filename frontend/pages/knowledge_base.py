"""知识库与 RAG 诊断页面。"""

from frontend import legacy


def render_page() -> None:
    """渲染知识库管理页面。"""

    legacy.render_knowledge_page()
