"""旧文档解析入口的兼容包装。"""

from tools.document_parser import parse_document as parse_rich_document


def parse_document(file_path: str) -> str:
    """兼容旧调用方式，返回统一文档解析层的纯文本。"""

    return parse_rich_document(file_path).text
