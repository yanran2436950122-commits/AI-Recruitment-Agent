"""本地 RAG 流程的检索器组装。"""

from typing import Any, Dict, List

from app.config import KNOWLEDGE_BASE_DIR
from rag.loader import load_documents
from rag.reranker import rerank
from rag.splitter import split_text
from rag.vector_store import InMemoryVectorStore, VectorStoreClient


class KnowledgeRetriever:
    """加载、索引、检索并重排本地知识库文本块。"""

    def __init__(self, knowledge_base_dir: str) -> None:
        """根据知识库目录构建内存向量索引。"""

        self.store = InMemoryVectorStore()
        for source, text in load_documents(knowledge_base_dir):
            self.store.add_texts(source, split_text(text))

    def retrieve(self, query: str, top_k: int = 3) -> List[str]:
        """检索用于生成面试题的最相关文本块。"""

        candidates = self.store.similarity_search(query, top_k=max(top_k * 3, 5))
        reranked = rerank(query, candidates, top_k=top_k)
        return [document.text for document in reranked]


def retrieve_interview_context(
    resume_info: Dict[str, Any],
    jd_info: Dict[str, Any],
    missing_skills: List[str],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """检索面试题库和技术题库上下文。"""

    query = _build_query(resume_info, jd_info, missing_skills)
    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    ) or _fallback_file_search(query, top_k)


def retrieve_hiring_standard(
    jd_info: Dict[str, Any],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """检索岗位能力模型和企业招聘标准。"""

    query = " ".join(jd_info.get("required_skills", []) or []) + " 招聘标准 岗位能力模型"
    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    )


def retrieve_resume_examples(
    jd_info: Dict[str, Any],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """检索历史优秀简历案例。"""

    query = " ".join(jd_info.get("required_skills", []) or []) + " 优秀简历 项目经历"
    return VectorStoreClient(collection_name="shared_knowledge").similarity_search(
        query=query,
        top_k=top_k,
        filters={"scope": "shared"},
    )


def _build_query(
    resume_info: Dict[str, Any],
    jd_info: Dict[str, Any],
    missing_skills: List[str],
) -> str:
    """根据简历、JD 和缺失技能构造 RAG 查询。"""

    return " ".join(
        [
            " ".join(resume_info.get("skills", []) or []),
            " ".join(jd_info.get("required_skills", []) or []),
            " ".join(missing_skills or []),
            jd_info.get("summary", ""),
        ]
    )


def _fallback_file_search(query: str, top_k: int) -> List[Dict[str, Any]]:
    """当向量库为空时从知识库文件即时构建轻量检索结果。"""

    store = InMemoryVectorStore()
    for source, text in load_documents(str(KNOWLEDGE_BASE_DIR)):
        store.add_texts(source, split_text(text))
    return [
        {
            "text": document.text,
            "source": document.source,
            "metadata": {"source": document.source},
            "score": 0,
        }
        for document in store.similarity_search(query, top_k=top_k)
    ]
