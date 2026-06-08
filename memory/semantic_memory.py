"""基于向量库的语义记忆实现。"""

from typing import Any, Dict, List

from rag.vector_store import VectorStoreClient


class SemanticMemory:
    """用于保存和检索用户长期语义摘要的记忆适配器。"""

    def __init__(self) -> None:
        """初始化语义记忆向量库。"""

        self._store = VectorStoreClient(collection_name="semantic_memory")

    def save_semantic_memory(
        self,
        user_id: str,
        text: str,
        metadata: Dict[str, Any],
    ) -> None:
        """保存一条用户语义记忆摘要。"""

        if not user_id or not text:
            return
        merged_metadata = {"user_id": user_id, **metadata}
        self._store.add_documents([{"text": text, "metadata": merged_metadata}])

    def search_semantic_memory(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """按用户和查询语义检索历史摘要。"""

        if not user_id or not query:
            return []
        return self._store.similarity_search(
            query=query,
            top_k=top_k,
            filters={"user_id": user_id},
        )

    def clear_user(self, user_id: str) -> None:
        """清除某个用户的语义记忆。"""

        self._store.delete_by_metadata({"user_id": user_id})
