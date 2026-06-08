"""向量数据库接口封装，默认使用本地持久化实现并预留 Chroma/Milvus 切换点。"""
import hashlib
import json
import re
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import VECTOR_STORE_DIR
from rag.embedding import Vector, cosine_similarity, embed_text


@dataclass
class VectorDocument:
    """可检索的文本块及其元数据。"""

    source: str
    text: str
    vector: Vector
    metadata: Dict[str, Any]

def _normalize_text_for_id(text: str) -> str:
    """归一化文本，用于生成稳定 chunk_id。"""
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _build_chunk_id(text: str, metadata: Dict[str, Any], source: str) -> str:
    """根据 source、position、text 生成稳定 chunk_id。"""

    payload = {
        "source": source,
        "position": metadata.get("position", ""),
        "text": _normalize_text_for_id(text),
    }
    # metadata = doc.get("metadata", {}) or {}
    # payload = {
    #     "source": metadata.get("source", ""),
    #     "position": metadata.get("position", ""),
    #     "text": _normalize_text_for_id(doc.get("text", "")),
    # }
    # raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    # return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

class InMemoryVectorStore:
    """作为 Chroma 或 Milvus 本地替代方案的简单向量库。"""

    def __init__(self) -> None:
        """初始化空的向量索引。"""

        self._documents: List[VectorDocument] = []

    def add_texts(self, source: str, texts: List[str]) -> None:
        """将同一来源文档的文本块加入索引。"""

        for text in texts:
            self._documents.append(
                VectorDocument(
                    source=source,
                    text=text,
                    vector=embed_text(text),
                    metadata={"source": source},
                )
            )

    def similarity_search(self, query: str, top_k: int = 5) -> List[VectorDocument]:
        """返回与查询最相似的文本块。"""

        query_vector = embed_text(query)
        scored = [
            (cosine_similarity(query_vector, document.vector), document)
            for document in self._documents
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [document for score, document in scored[:top_k] if score > 0]

class VectorStoreClient:
    """业务代码使用的向量库统一客户端。"""

    def __init__(self, collection_name: str = "knowledge_base") -> None:
        """初始化指定集合的本地向量库。"""

        self.collection_name = collection_name
        self._path = VECTOR_STORE_DIR / f"{collection_name}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)


    def add_doucements(self, docs: list) -> Dict[str, int]:
        """批量写入文档，文档必须包含 text 和 metadata 字段。
        使用 metadata.chunk_id 做幂等写入，
        避免重复导入同一知识块。"""
        records = self._load()
        existing_chunk_ids = {
            (record.get("metadata") or {}).get("chunk_id", "")
            for record in records
            if(record.get("metadata") or {}).get("chunk_id")
        }
        inserted = 0
        skipped = 0
        for doc in docs:
            text = str(doc.get("text") or "").strip()
            if not text:
                skipped += 1
                continue
            metadata = dict(doc.get("metadata", {}) or {})
            source = str(metadata.get("source") or doc.get("source") or "")
            chunk_id = metadata.get("chunk_id")
            if not chunk_id:
                chunk_id = _build_chunk_id(text = text, metadata = metadata, source = source)
                metadata["chunk_id"] = chunk_id
            if chunk_id in existing_chunk_ids:
                skipped += 1
                continue
            records.append(
                {
                    "text": text,
                    "metadata": metadata,
                    "source": source,
                    "vector": embed_text(text),
                }
            )
            existing_chunk_ids.add(chunk_id)
            inserted += 1
        self._save(records)
        return{
            "inserted": inserted,
            "skipped": skipped,
            "total": len(records),
        }

    # def add_documents(self, docs: list) -> None:
    #     """批量写入文档，文档必须包含 text 和 metadata 字段。"""
    #
    #     records = self._load()
    #     for doc in docs:
    #         text = str(doc.get("text") or "").strip()
    #         if not text:
    #             continue
    #         metadata = dict(doc.get("metadata") or {})
    #         source = str(metadata.get("source") or doc.get("source") or "")
    #         records.append(
    #             {
    #                 "text": text,
    #                 "metadata": metadata,
    #                 "source": source,
    #                 "vector": embed_text(text),
    #             }
    #         )
    #     self._save(records)

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """按语义相似度检索文档，并支持 metadata 精确过滤。"""

        query_vector = embed_text(query)
        scored = []
        for record in self._load():
            metadata = record.get("metadata") or {}
            if not self._match_filters(metadata, filters):
                continue
            score = cosine_similarity(query_vector, record.get("vector") or {})
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        results = []
        for score, record in scored[:top_k]:
            metadata = record.get("metadata") or {}
            results.append(
                {
                    "text": record.get("text", ""),
                    "source": metadata.get("source") or record.get("source", ""),
                    "metadata": metadata,
                    "score": round(float(score), 6),
                }
            )
        return results

    def delete_by_metadata(self, filters: dict) -> None:
        """根据 metadata 过滤条件删除文档。"""

        if not filters:
            return
        records = [
            record
            for record in self._load()
            if not self._match_filters(record.get("metadata") or {}, filters)
        ]
        self._save(records)

    def count_documents(self, filters: Optional[dict] = None) -> int:
        """统计当前集合中满足过滤条件的文档数量。"""

        return sum(
            1
            for record in self._load()
            if self._match_filters(record.get("metadata") or {}, filters)
        )

    def describe(self, filters: Optional[dict] = None) -> Dict[str, Any]:
        """返回向量集合的基础诊断信息。"""

        records = [
            record
            for record in self._load()
            if self._match_filters(record.get("metadata") or {}, filters)
        ]
        sources = sorted({(record.get("metadata") or {}).get("source") or record.get("source") or "" for record in records})
        return {
            "collection_name": self.collection_name,
            "doc_count": len(records),
            "source_count": len([source for source in sources if source]),
            "sources": [source for source in sources if source],
            "path": str(self._path),
        }

    def _load(self) -> List[Dict[str, Any]]:
        """读取本地向量库文件。"""

        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _save(self, records: List[Dict[str, Any]]) -> None:
        """写入本地向量库文件。"""

        self._path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    def _match_filters(self, metadata: Dict[str, Any], filters: Optional[dict]) -> bool:
        """判断文档 metadata 是否满足过滤条件。"""

        if not filters:
            return True
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True
