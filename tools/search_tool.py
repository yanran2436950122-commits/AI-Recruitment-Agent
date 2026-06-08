"""面向智能体的 RAG 检索工具封装。"""

from functools import lru_cache
from typing import List

from app.config import KNOWLEDGE_BASE_DIR
from rag.retriever import KnowledgeRetriever


@lru_cache(maxsize=1)
def _get_retriever() -> KnowledgeRetriever:
    """创建并缓存知识检索器，供重复 API 调用复用。"""

    return KnowledgeRetriever(str(KNOWLEDGE_BASE_DIR))


def search_interview_knowledge(query: str, top_k: int = 3) -> List[str]:
    """从本地知识库中检索面试题生成所需的上下文。"""

    return _get_retriever().retrieve(query=query, top_k=top_k)
