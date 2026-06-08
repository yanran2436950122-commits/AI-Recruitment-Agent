"""RAG 搜索工具封装。"""

from typing import Dict, List

from rag.retriever import (
    retrieve_hiring_standard,
    retrieve_interview_context,
    retrieve_resume_examples,
)
from rag.vector_store import VectorStoreClient


def search_interview_questions(query: str, top_k: int = 5) -> List[Dict[str, object]]:
    """检索面试题库和技术题库。"""

    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    )


def search_hiring_standards(query: str, top_k: int = 5) -> List[Dict[str, object]]:
    """检索企业招聘标准和岗位能力模型。"""

    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    )


def search_resume_examples(query: str, top_k: int = 5) -> List[Dict[str, object]]:
    """检索历史优秀简历案例。"""

    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    )


def retrieve_interview_context_for_state(state: dict) -> List[Dict[str, object]]:
    """根据工作流状态检索面试题上下文。"""

    return retrieve_interview_context(
        resume_info=state.get("resume_info") or {},
        jd_info=state.get("jd_info") or {},
        missing_skills=state.get("missing_skills") or [],
    )


def retrieve_hiring_standard_for_state(state: dict) -> List[Dict[str, object]]:
    """根据工作流状态检索招聘标准上下文。"""

    return retrieve_hiring_standard(jd_info=state.get("jd_info") or {})


def retrieve_resume_examples_for_state(state: dict) -> List[Dict[str, object]]:
    """根据工作流状态检索优秀简历案例上下文。"""

    return retrieve_resume_examples(jd_info=state.get("jd_info") or {})
