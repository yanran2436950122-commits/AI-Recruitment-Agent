"""知识库导入流程。"""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from app.config import KNOWLEDGE_BASE_DIR, KNOWLEDGE_EXTENSIONS, VECTOR_STORE_DIR
from rag.splitter import split_text
from rag.vector_store import VectorStoreClient
from tools.pdf_parser import parse_document


def ingest_knowledge_base() -> Dict[str, int]:
    """导入 data/knowledge_base 下的文档到向量库。"""

    docs: List[dict] = []
    root = KNOWLEDGE_BASE_DIR
    root.mkdir(parents=True, exist_ok=True)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in KNOWLEDGE_EXTENSIONS:
            continue
        docs.extend(_build_documents_from_file(path))
    store = VectorStoreClient(collection_name="shared_knowledge")
    # if docs:
    #     store.add_documents(docs)
    # result = {"files": len({doc["metadata"]["source"] for doc in docs}), "chunks": len(docs)}
    write_result = {"inserted": 0, "skipped": 0, "total": store.count_documents()}
    if docs:
        write_result = store.add_doucements(docs)
    result = {
        "files": len({doc["metadata"]["source"] for doc in docs}),
        "chunks": len(docs),
        "inserted": write_result["inserted"],
        "skipped": write_result["skipped"],
        "total_documents": write_result["total"],
    }
    _write_ingest_metadata(result)
    return result

# 验证docs[]
# def ingest_knowledge_base() -> Dict[str, int]:
#     docs: List[dict] = []
#     root = KNOWLEDGE_BASE_DIR
#     root.mkdir(parents=True, exist_ok=True)
#     for path in root.rglob("*"):
#         if not path.is_file() or path.suffix.lower() not in KNOWLEDGE_EXTENSIONS:
#             continue
#         docs.extend(_build_documents_from_file(path))
#     if docs:
#         import json
#         print("=" * 80)
#         for i, doc in enumerate(docs[:3]):
#             print(f"\n========== DOC {i} ==========")
#             print(json.dumps(doc, ensure_ascii=False, indent=2))
#         print("=" * 80)
#     store = VectorStoreClient(collection_name="shared_knowledge")
#     if docs:
#         store.add_documents(docs)
#     result = {
#         "files": len({doc["metadata"]["source"] for doc in docs}),
#         "chunks": len(docs)
#     }
#     _write_ingest_metadata(result)
#     return result

def get_knowledge_base_diagnostics(
    retrieval_query: str = "",
    retrieval_top_k: int = 5,
    retrieval_filters: dict = None,
) -> Dict[str, object]:
    """返回知识库和共享向量库诊断信息。"""

    root = KNOWLEDGE_BASE_DIR
    root.mkdir(parents=True, exist_ok=True)
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in KNOWLEDGE_EXTENSIONS
    ]
    store = VectorStoreClient(collection_name="shared_knowledge")
    filters = retrieval_filters or {"scope": "shared"}
    store_info = store.describe(filters=filters)
    warnings = []
    if not files:
        warnings.append("data/knowledge_base 为空。")
    if store_info["doc_count"] == 0:
        warnings.append("向量库为空，可能尚未执行 /knowledge/ingest。")
    if retrieval_query and len(retrieval_query.strip()) < 3:
        warnings.append("检索 query 过短，可能缺少关键词。")
    if filters != {"scope": "shared"}:
        warnings.append("Shared Knowledge 检索应只使用 scope=shared，避免附加租户 ID。")
    metadata = _read_ingest_metadata()
    return {
        "knowledge_base_file_count": len(files),
        "knowledge_base_files": [str(path) for path in files],
        "vector_store_doc_count": store_info["doc_count"],
        "vector_store_source_count": store_info["source_count"],
        "last_ingest_time": metadata.get("last_ingest_time", ""),
        "retrieval_query": retrieval_query,
        "retrieval_top_k": retrieval_top_k,
        "retrieval_filters": filters,
        "retrieval_warnings": warnings,
    }


def create_default_knowledge_base() -> Path:
    """创建默认面试题知识库文件，已存在时不覆盖。"""

    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    path = KNOWLEDGE_BASE_DIR / "default_interview_questions.md"
    if path.exists():
        return path
    path.write_text(DEFAULT_KNOWLEDGE_TEXT, encoding="utf-8")
    return path


# def _normalize_chunk_text(text: str) -> str:
#     """用于生成稳定 chunk_id 的亲量归一化"""
#     text = text or ""
#     text = re.sub(r"\s+", "", text)
#     return text.strip().lower()
#
# def _build_chunk_id(path: Path, position: int, chunk: str) -> str:
#     """生成稳定 chunk_id，避免重复导入同一知识块。"""
#     payload = {
#         "source": str(path.resolve()),
#         "position": position,
#         "text": _normalize_chunk_text(chunk),
#     }
#     raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
#     return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _build_documents_from_file(path: Path) -> List[dict]:
    """将单个知识库文件转换为可入库的文档块。"""

    try:
        text = path.read_text(encoding="utf-8") if path.suffix.lower() == ".md" else parse_document(str(path))
    except Exception:
        return []
    doc_type = _infer_doc_type(path, text)
    created_at = datetime.now(timezone.utc).isoformat()
    documents = []
    for position, chunk in enumerate(split_text(text), start=1):
        # chunk_id = _build_chunk_id(path, position, chunk)
        documents.append(
            {
                "text": chunk,
                "metadata": {
                    # "chunk_id": chunk_id,
                    "source": str(path),
                    "doc_type": doc_type,
                    "position": position,
                    "created_at": created_at,
                    "scope": "shared",
                },
            }
        )
    return documents


def _infer_doc_type(path: Path, text: str) -> str:
    """根据文件名和内容推断知识库文档类型。"""

    lowered = f"{path.name} {text[:200]}".lower()
    if "resume" in lowered or "简历" in lowered:
        return "resume_example"
    if "standard" in lowered or "标准" in lowered or "能力模型" in lowered:
        return "hiring_standard"
    if "interview" in lowered or "面试" in lowered or "题" in lowered:
        return "interview_question"
    return "technical_doc"


def _write_ingest_metadata(result: Dict[str, int]) -> None:
    """记录最近一次知识库导入时间。"""

    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    metadata_path = VECTOR_STORE_DIR / "ingest_metadata.json"
    metadata_path.write_text(
        (
            "{\n"
            f'  "last_ingest_time": "{datetime.now(timezone.utc).isoformat()}",\n'
            f'  "files": {int(result.get("files") or 0)},\n'
            f'  "chunks": {int(result.get("chunks") or 0)}\n'
            "}\n"
        ),
        encoding="utf-8",
    )


def _read_ingest_metadata() -> Dict[str, object]:
    """读取最近一次知识库导入元数据。"""

    import json

    metadata_path = VECTOR_STORE_DIR / "ingest_metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


DEFAULT_KNOWLEDGE_TEXT = """# 默认招聘知识库

## AI Agent 面试题

1. 请说明 Agent 的规划、工具调用、记忆和反馈闭环如何设计。
2. 如何避免 Agent 在多轮执行中出现状态污染或无限循环？
3. 如果工具调用失败，你会如何设计降级和重试策略？

## LangGraph 面试题

1. 为什么选择 LangGraph 而不是普通链式调用？
2. AgentState 中哪些字段应该属于短期状态，哪些应该持久化？
3. 条件路由如何避免死循环？

## RAG 面试题

1. RAG 的召回、重排和生成分别解决什么问题？
2. 如何排查向量库无命中？
3. metadata filter 错误会造成什么后果？

## 向量数据库面试题

1. Chroma 和 Milvus 在本地开发和生产环境中的取舍是什么？
2. 为什么多租户检索必须依赖 scope、company_id、candidate_id、job_id？
3. 如何设计 Shared Knowledge 与 Private Memory 的隔离？

## 简历优化建议样例

- 项目经历应包含业务背景、技术方案、个人职责和可量化结果。
- 如果 JD 要求 RAG，应补充检索、Embedding、向量库、重排和评估指标。
- 如果 JD 要求 LangGraph，应说明节点设计、状态传递、条件路由和异常处理。
"""
