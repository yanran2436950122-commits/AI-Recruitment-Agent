"""知识库文档加载。"""

from pathlib import Path
from typing import List, Tuple

from app.config import KNOWLEDGE_EXTENSIONS
from tools.pdf_parser import parse_document


def load_documents(directory: str) -> List[Tuple[str, str]]:
    """将支持的知识库文件加载为 `(来源, 文本)` 元组。"""

    root = Path(directory)
    if not root.exists():
        return []

    documents: List[Tuple[str, str]] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in KNOWLEDGE_EXTENSIONS:
            try:
                if path.suffix.lower() == ".md":
                    text = path.read_text(encoding="utf-8")
                else:
                    text = parse_document(str(path))
                documents.append((str(path), text))
            except Exception:
                continue
    return documents
