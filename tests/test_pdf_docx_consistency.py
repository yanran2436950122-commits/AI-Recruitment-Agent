"""PDF 与 DOCX 同内容简历解析和评分一致性测试。"""

from pathlib import Path

from tests.document_fixtures import write_demo_docx, write_demo_pdf
from tools.document_parser import parse_document
from tools.score_tool import calculate_match_score


RESUME_TEXT = """
Candidate: Consistency User
Role: AI Agent Engineer
Skills: Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, Docker, Chroma, Milvus.
Project: Built recruitment agent workflows with resume parsing, JD matching, memory isolation,
vector database retrieval, interview question generation, scoring trace, and Streamlit UI.
Impact: Improved hiring analysis quality and reduced manual screening workload.
Education: Computer Science.
""".strip()

JD_TEXT = (
    "Need AI Agent Engineer with Python, FastAPI, LangGraph, RAG, Redis, PostgreSQL, "
    "Docker, Chroma, Milvus, resume parsing, scoring trace, and recruitment workflow experience."
)


def test_pdf_docx_same_content_score_gap_within_five(tmp_path: Path) -> None:
    """同内容 PDF 和 DOCX 经过统一解析后基础评分差异不应超过 5 分。"""

    pdf_path = tmp_path / "resume.pdf"
    docx_path = tmp_path / "resume.docx"
    write_demo_pdf(pdf_path, RESUME_TEXT)
    write_demo_docx(docx_path, RESUME_TEXT)

    pdf_doc = parse_document(str(pdf_path))
    docx_doc = parse_document(str(docx_path))
    pdf_score, _, _ = calculate_match_score(pdf_doc.text, JD_TEXT)
    docx_score, _, _ = calculate_match_score(docx_doc.text, JD_TEXT)

    assert pdf_doc.text_length > 200
    assert docx_doc.text_length > 200
    assert "python" in pdf_doc.text.lower()
    assert "python" in docx_doc.text.lower()
    assert abs(pdf_score - docx_score) <= 5
