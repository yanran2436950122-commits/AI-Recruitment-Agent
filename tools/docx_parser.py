"""DOCX 文档解析工具。"""

from tools.pdf_parser import parse_document


def parse_docx(file_path: str) -> str:
    """解析 DOCX 文件并返回纯文本。"""

    return parse_document(file_path)
