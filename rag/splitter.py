"""用于 RAG 索引的文本切分工具。"""

from typing import List


def split_text(text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
    """将长文本切分为适合检索的重叠文本块。"""

    cleaned = (text or "").strip()
    if not cleaned:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + chunk_size)
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks
