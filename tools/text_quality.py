"""简历文本解析质量检查工具。"""

import re
from typing import Dict, List

from tools.score_tool import extract_skills


class TextQualityValidator:
    """简历文本质量验证器，集中管理解析失败和乱码风险判断。"""

    def validate(self, text: str) -> Dict[str, object]:
        """检查简历文本质量并返回长度、质量分和警告。"""

        normalized = text or ""
        warnings: List[str] = []
        text_length = len(normalized.strip())
        quality_score = 1.0

        if text_length < 200:
            warnings.append("简历文本长度小于 200，疑似解析失败或内容过少。")
            quality_score -= 0.35

        skills = extract_skills(normalized)
        if len(skills) < 2:
            warnings.append("识别到的技能关键词过少，可能存在解析缺失。")
            quality_score -= 0.2

        project_hits = _project_marker_count(normalized)
        if project_hits < 2:
            warnings.append("项目经历关键词过少，可能存在项目内容解析缺失。")
            quality_score -= 0.15

        valid_ratio = _valid_character_ratio(normalized)
        if valid_ratio < 0.65:
            warnings.append("中文/英文/数字有效字符比例偏低，可能存在乱码或不可见字符。")
            quality_score -= 0.2

        garbled_ratio = _garbled_character_ratio(normalized)
        if garbled_ratio > 0.08:
            warnings.append("疑似乱码字符比例偏高。")
            quality_score -= 0.2

        whitespace_ratio = _whitespace_ratio(normalized)
        if whitespace_ratio > 0.45:
            warnings.append("空白字符比例偏高，可能存在换行或排版解析异常。")
            quality_score -= 0.1

        if re.search(r"\n{5,}", normalized):
            warnings.append("连续换行过多，可能存在版式解析异常。")
            quality_score -= 0.05

        if quality_score < 0.3:
            warnings.append("解析质量分低于 0.3，当前评分可信度较低。")

        return {
            "text_length": text_length,
            "quality_score": max(0.0, round(quality_score, 2)),
            "warnings": warnings,
        }


def validate_resume_text(text: str) -> Dict[str, object]:
    """兼容旧调用方式，使用统一验证器检查简历文本质量。"""

    return TextQualityValidator().validate(text)


def _valid_character_ratio(text: str) -> float:
    """计算中文、英文、数字和常见标点的有效字符比例。"""

    if not text:
        return 0.0
    valid = re.findall(r"[\u4e00-\u9fffA-Za-z0-9，。、“”‘’：:；;,.!?/+\-#()\[\]\s]", text)
    return len(valid) / len(text)


def _garbled_character_ratio(text: str) -> float:
    """估算乱码或替换字符比例。"""

    if not text:
        return 1.0
    garbled = re.findall(r"[�\ufffd]|[^\u4e00-\u9fffA-Za-z0-9，。、“”‘’：:；;,.!?/+\-#()\[\]\s]", text)
    return len(garbled) / len(text)


def _whitespace_ratio(text: str) -> float:
    """计算空白字符占比。"""

    if not text:
        return 1.0
    whitespace = re.findall(r"\s", text)
    return len(whitespace) / len(text)


def _project_marker_count(text: str) -> int:
    """统计项目经历相关关键词命中数量，用于发现项目段落解析缺失。"""

    normalized = (text or "").lower()
    markers = [
        "项目",
        "经历",
        "负责",
        "开发",
        "设计",
        "优化",
        "落地",
        "系统",
        "平台",
        "project",
        "experience",
        "built",
        "developed",
        "designed",
        "optimized",
    ]
    return sum(1 for marker in markers if marker in normalized)
