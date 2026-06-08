"""检索文本块的重排辅助工具。"""

from typing import List

from rag.vector_store import VectorDocument
from tools.score_tool import tokenize


def rerank(query: str, documents: List[VectorDocument], top_k: int = 3) -> List[VectorDocument]:
    """根据与最终查询的词重合度对检索文档重新排序。"""

    query_tokens = set(token.lower() for token in tokenize(query))

    def overlap_score(document: VectorDocument) -> int:
        """根据共享查询词数量为单个文本块打分。"""

        doc_tokens = set(token.lower() for token in tokenize(document.text))
        return len(query_tokens.intersection(doc_tokens))

    return sorted(documents, key=overlap_score, reverse=True)[:top_k]
