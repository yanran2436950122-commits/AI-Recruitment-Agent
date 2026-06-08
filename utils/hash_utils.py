"""简历 Hash 工具，区分原始文本、规范文本和结构化简历指纹。"""

import hashlib
import json
import re
import unicodedata
from typing import Any, Dict, Iterable, List


FINGERPRINT_HASH_FIELDS = ("name", "email", "phone", "work_companies", "project_names")
"""第一版简历强指纹只使用的稳定字段。"""

FINGERPRINT_DEBUG_FIELDS = ("skills", "education")
"""仅进入调试载荷、不参与强指纹 Hash 的字段。"""


def normalize_resume_text_for_hash(text: str) -> str:
    """将解析后的简历文本归一化为跨 PDF/DOCX/TXT 稳定的 Hash 输入。"""

    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = _remove_invisible_chars(normalized)
    normalized = _normalize_line_start_bullets(normalized)
    normalized = _join_broken_hyphen_lines(normalized)
    normalized = _join_cjk_broken_lines(normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s+", "", normalized)
    return normalized.strip()


def build_raw_text_hash(text: str) -> str:
    """基于解析后的原始 resume_text 生成 Hash，用于调试解析差异。"""

    return sha256_text(text or "")


def build_canonical_resume_hash(text: str) -> str:
    """兼容旧调用，基于归一化文本生成 canonical 文本 Hash。"""

    return build_canonical_text_hash(text)


def build_canonical_text_hash(text: str) -> str:
    """基于归一化后的简历文本生成 canonical_text_hash。"""

    return sha256_text(normalize_resume_text_for_hash(text))


def build_resume_fingerprint(resume_info: Dict[str, Any]) -> str:
    """基于结构化简历信息生成跨格式稳定的 resume_fingerprint_hash。"""

    return build_resume_fingerprint_hash(resume_info)


def build_resume_fingerprint_hash(resume_info: Dict[str, Any]) -> str:
    """基于 fingerprint_payload 生成 resume_fingerprint_hash。"""

    return sha256_text(build_resume_fingerprint_payload_json(resume_info))


def build_resume_fingerprint_payload_json(resume_info: Dict[str, Any]) -> str:
    """生成参与强指纹 Hash 的稳定 JSON 字符串。"""

    return normalize_resume_fingerprint(resume_info)["fingerprint_payload_json_used_for_hash"]


def build_resume_fingerprint_payload(resume_info: Dict[str, Any]) -> Dict[str, Any]:
    """提取参与强指纹 Hash 的稳定结构化字段。"""

    return normalize_resume_fingerprint(resume_info)["fingerprint_payload_used_for_hash"]


def normalize_resume_fingerprint(resume_info: Dict[str, Any]) -> Dict[str, Any]:
    """规范化简历指纹载荷，并把不参与 Hash 的字段放入调试载荷。"""

    info = resume_info or {}
    fingerprint_payload = {
        "name": _normalize_text_value(info.get("name")),
        "email": _normalize_email(info.get("email")),
        "phone": _normalize_phone(info.get("phone")),
        "work_companies": _normalize_list(info.get("work_companies")),
        "project_names": _normalize_list(info.get("project_names")),
    }
    debug_payload = {
        "skills": _normalize_list(info.get("skills")),
        "education": _normalize_list(info.get("education") or info.get("educations")),
    }
    payload_json = json.dumps(
        fingerprint_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "fingerprint_payload_used_for_hash": fingerprint_payload,
        "fingerprint_debug_payload_not_used_for_hash": debug_payload,
        "fingerprint_payload_json_used_for_hash": payload_json,
        "fingerprint_confidence": _build_fingerprint_confidence(fingerprint_payload),
        "fingerprint_payload": fingerprint_payload,
        "fingerprint_debug_payload": debug_payload,
    }


def sha256_text(text: str) -> str:
    """对 UTF-8 文本计算 SHA256。"""

    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _remove_invisible_chars(text: str) -> str:
    """删除常见不可见字符，避免复制或解析来源影响 Hash。"""

    for char in ["\u200b", "\u200c", "\u200d", "\ufeff"]:
        text = text.replace(char, "")
    return text


def _normalize_line_start_bullets(text: str) -> str:
    """移除行首项目符号，并保留电话、日期、英文复合词中的普通连字符。"""

    text = re.sub(r"(?m)^\s*[•·●○]\s*", "", text)
    return re.sub(r"(?m)^\s*[-–—]\s+", "", text)


def _join_broken_hyphen_lines(text: str) -> str:
    """修复 PDF 断行连字符，例如 138-0000-\n1234。"""

    return re.sub(r"([A-Za-z0-9])-\s*\n\s*([A-Za-z0-9])", r"\1-\2", text)


def _join_cjk_broken_lines(text: str) -> str:
    """消除中文或中英数字之间由版式造成的换行。"""

    text = re.sub(r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s*\n\s*(?=[A-Za-z0-9])", "", text)
    return re.sub(r"(?<=[A-Za-z0-9])\s*\n\s*(?=[\u4e00-\u9fff])", "", text)


def _normalize_scalar(value: Any) -> str:
    """规范化结构化字段中的单值文本。"""

    return _normalize_text_value(value)


def _normalize_text_value(value: Any) -> str:
    """中文/英文文本统一全半角、去空白并转小写。"""

    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = _remove_invisible_chars(text)
    text = _normalize_common_punctuation(text)
    return re.sub(r"\s+", "", text)


def _normalize_email(value: Any) -> str:
    """邮箱统一全半角、去空白并转小写。"""

    return _normalize_text_value(value)


def _normalize_phone(value: Any) -> str:
    """电话号码只保留数字，消除连字符、空格和换行差异。"""

    return re.sub(r"\D+", "", unicodedata.normalize("NFKC", str(value or "")))


def _normalize_list(values: Any) -> List[str]:
    """规范化结构化字段中的列表并排序去重。"""

    if values in (None, ""):
        return []
    if isinstance(values, str):
        iterable: Iterable[Any] = re.split(r"[,，;；、\n]+", values)
    elif isinstance(values, dict):
        iterable = values.values()
    else:
        iterable = values
    normalized = [_normalize_scalar(item) for item in iterable if _normalize_scalar(item)]
    return sorted(dict.fromkeys(normalized))


def _normalize_common_punctuation(text: str) -> str:
    """统一常见中英文标点，避免全角或特殊符号影响结构化字段。"""

    replacements = {
        "：": ":",
        "，": ",",
        "；": ";",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "、": ",",
        "。": ".",
        "—": "-",
        "–": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _build_fingerprint_confidence(payload: Dict[str, Any]) -> str:
    """根据稳定身份字段数量判断当前指纹能否用于强去重。"""

    has_email = bool(payload.get("email"))
    has_phone = bool(payload.get("phone"))
    signal_count = sum(
        1
        for key in ("name", "email", "phone", "work_companies", "project_names")
        if payload.get(key)
    )
    if has_email or has_phone or signal_count >= 2:
        return "high"
    return "low"
