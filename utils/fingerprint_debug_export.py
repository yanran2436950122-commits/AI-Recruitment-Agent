"""简历指纹调试导出工具。"""

import json
from pathlib import Path
from typing import Any, Dict, List

from monitoring.monitor_service import write_xlsx
from tools.score_tool import parse_profile
from utils.hash_utils import (
    build_canonical_text_hash,
    build_raw_text_hash,
    build_resume_fingerprint_hash,
    normalize_resume_fingerprint,
)


HASH_FIELDS = ("name", "email", "phone", "work_companies", "project_names")
"""参与强 fingerprint hash 的字段。"""

DEBUG_FIELDS = ("skills", "education")
"""仅用于调试、不参与强 fingerprint hash 的字段。"""


def build_fingerprint_payload_compare_rows(
    docx_run_1: Dict[str, Any],
    docx_run_2: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """构造两次上传的 fingerprint payload 对比行。"""

    first = build_fingerprint_debug_snapshot(docx_run_1)
    second = build_fingerprint_debug_snapshot(docx_run_2)
    rows: List[Dict[str, Any]] = []
    for field in HASH_FIELDS:
        rows.append(_build_compare_row(first, second, field, True, "fingerprint_payload_used_for_hash"))
    for field in DEBUG_FIELDS:
        rows.append(_build_compare_row(first, second, field, False, "fingerprint_debug_payload_not_used_for_hash"))
    for field in (
        "raw_text_hash",
        "canonical_text_hash",
        "fingerprint_payload_json_used_for_hash",
        "resume_fingerprint_hash",
        "resume_hash",
    ):
        rows.append(_build_compare_row(first, second, field, field in {"resume_fingerprint_hash", "resume_hash"}, "hash_result"))
    return rows


def export_fingerprint_payload_compare_excel(
    docx_run_1: Dict[str, Any],
    docx_run_2: Dict[str, Any],
    output_path: str | Path,
) -> Path:
    """把两次上传的 fingerprint payload 对比结果导出为 Excel。"""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_xlsx(path, build_fingerprint_payload_compare_rows(docx_run_1, docx_run_2))
    return path


def build_fingerprint_debug_snapshot(run_payload: Dict[str, Any]) -> Dict[str, Any]:
    """把一次上传结果或原始文本整理为可比较的 fingerprint 调试快照。"""

    resume_text = run_payload.get("resume_text") or run_payload.get("text") or ""
    resume_info = run_payload.get("resume_info") or parse_profile(resume_text)
    normalized = normalize_resume_fingerprint(resume_info)
    fingerprint_hash = run_payload.get("resume_fingerprint_hash") or build_resume_fingerprint_hash(resume_info)
    resume_hash = run_payload.get("resume_hash") or fingerprint_hash
    return {
        **normalized["fingerprint_payload_used_for_hash"],
        **normalized["fingerprint_debug_payload_not_used_for_hash"],
        "raw_text_hash": run_payload.get("raw_text_hash") or build_raw_text_hash(resume_text),
        "canonical_text_hash": run_payload.get("canonical_text_hash") or build_canonical_text_hash(resume_text),
        "fingerprint_payload_json_used_for_hash": normalized["fingerprint_payload_json_used_for_hash"],
        "resume_fingerprint_hash": fingerprint_hash,
        "resume_hash": resume_hash,
    }


def _build_compare_row(
    first: Dict[str, Any],
    second: Dict[str, Any],
    field: str,
    used_for_hash: bool,
    section: str,
) -> Dict[str, Any]:
    """构造 Excel 中的单个字段对比行。"""

    first_value = first.get(field)
    second_value = second.get(field)
    return {
        "field": field,
        "docx_run_1_value": _stable_cell_value(first_value),
        "docx_run_2_value": _stable_cell_value(second_value),
        "equal": first_value == second_value,
        "used_for_hash": used_for_hash,
        "section": section,
    }


def _stable_cell_value(value: Any) -> str:
    """把列表和字典稳定序列化为 Excel 单元格文本。"""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "" if value is None else str(value)
