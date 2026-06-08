"""业务输入质量校验工具，防止无意义岗位、目标方向和 JD 进入分析流程。"""

from typing import Dict, List

from tools.score_tool import extract_skills


MEANINGLESS_VALUES = {"aaa", "bbb", "ccc", "test", "测试", "随便", "无", "none", "null", "n/a"}
"""明显无意义的输入值集合。"""

ROLE_HINT_WORDS = {
    "工程师",
    "开发",
    "产品",
    "运营",
    "设计",
    "rag",
    "agent",
    "后端",
    "前端",
    "算法",
    "测试",
    "engineer",
    "developer",
    "backend",
    "frontend",
}
"""岗位名称和求职方向中推荐出现的职位相关词。"""

RESPONSIBILITY_WORDS = {
    "负责",
    "参与",
    "设计",
    "开发",
    "维护",
    "优化",
    "建设",
    "build",
    "develop",
    "design",
    "maintain",
    "optimize",
}
"""JD 中常见的职责类关键词。"""

REQUIREMENT_WORDS = {
    "要求",
    "熟悉",
    "掌握",
    "经验",
    "能力",
    "优先",
    "need",
    "required",
    "require",
    "experience",
    "familiar",
    "preferred",
}
"""JD 中常见的任职要求类关键词。"""

SKILL_WORDS = {
    "python",
    "java",
    "fastapi",
    "langgraph",
    "rag",
    "sql",
    "redis",
    "docker",
    "大模型",
    "agent",
}
"""JD 中常见的技能关键词。"""


def validate_job_name(name: str) -> Dict[str, object]:
    """校验 HR 岗位名称，并返回统一 ValidationResult 字典。"""

    return _validate_role_like_name(name, "岗位名称")


def validate_target_role_name(name: str) -> Dict[str, object]:
    """校验 Candidate 目标岗位名称，并返回统一 ValidationResult 字典。"""

    return _validate_role_like_name(name, "目标岗位名称")


def validate_jd_text(text: str) -> Dict[str, object]:
    """校验 JD 文本是否具备基本岗位职责、要求或技能信息。"""

    cleaned = (text or "").strip()
    errors: List[str] = []
    warnings: List[str] = []
    quality_score = 1.0

    if not cleaned:
        errors.append("JD 不能为空。")
    if len(cleaned) < 50:
        errors.append("JD 长度不能小于 50 个字符。")
        quality_score -= 0.3
    if _is_meaningless(cleaned):
        errors.append("JD 内容明显无意义，请输入真实岗位职责和要求。")
        quality_score -= 0.5

    lowered = cleaned.lower()
    category_hits = 0
    if any(word in lowered for word in RESPONSIBILITY_WORDS):
        category_hits += 1
    if any(word in lowered for word in REQUIREMENT_WORDS):
        category_hits += 1
    skill_hits = bool(extract_skills(cleaned)) or any(word in lowered for word in SKILL_WORDS)
    if skill_hits:
        category_hits += 1
    if len(cleaned) >= 100:
        category_hits += 1
    if category_hits < 2:
        errors.append("JD 至少需要包含职责、要求、技能关键词或足够详细的描述中的两类。")
        quality_score -= 0.3

    if not errors and len(cleaned) < 100:
        warnings.append("JD 偏短，建议补充岗位职责、任职要求和加分项。")
        quality_score -= 0.1

    return _result(errors=errors, warnings=warnings, quality_score=quality_score)


def validate_role_description(text: str) -> Dict[str, object]:
    """校验岗位或目标方向描述，允许为空但不允许明显无意义。"""

    cleaned = (text or "").strip()
    errors: List[str] = []
    warnings: List[str] = []
    quality_score = 1.0
    if cleaned and _is_meaningless(cleaned):
        errors.append("描述内容明显无意义。")
        quality_score -= 0.4
    if cleaned and len(cleaned) < 4:
        warnings.append("描述较短，可以补充更多说明。")
        quality_score -= 0.1
    return _result(errors=errors, warnings=warnings, quality_score=quality_score)


def _validate_role_like_name(name: str, field_label: str) -> Dict[str, object]:
    """校验岗位名称或求职方向名称。"""

    cleaned = (name or "").strip()
    errors: List[str] = []
    warnings: List[str] = []
    quality_score = 1.0

    if not cleaned:
        errors.append(f"{field_label}不能为空。")
    if len(cleaned) < 2:
        errors.append(f"{field_label}长度不能小于 2。")
        quality_score -= 0.3
    if len(cleaned) > 50:
        errors.append(f"{field_label}长度不能超过 50。")
        quality_score -= 0.2
    if cleaned.isdigit():
        errors.append(f"{field_label}不能是纯数字。")
        quality_score -= 0.3
    if _is_meaningless(cleaned):
        errors.append(f"{field_label}明显无意义，请输入真实岗位名称。")
        quality_score -= 0.5
    lowered = cleaned.lower()
    if not any(word in lowered or word in cleaned for word in ROLE_HINT_WORDS):
        warnings.append(f"{field_label}建议包含职位相关词，例如工程师、开发、RAG、Agent、后端等。")
        quality_score -= 0.1
    return _result(errors=errors, warnings=warnings, quality_score=quality_score)


def _is_meaningless(text: str) -> bool:
    """判断文本是否明显无意义。"""

    cleaned = "".join((text or "").strip().lower().split())
    if cleaned in MEANINGLESS_VALUES:
        return True
    if len(set(cleaned)) == 1 and len(cleaned) >= 3:
        return True
    return False


def _result(errors: List[str], warnings: List[str], quality_score: float) -> Dict[str, object]:
    """构造统一 ValidationResult 字典。"""

    return {
        "valid": not errors,
        "warnings": warnings,
        "errors": errors,
        "quality_score": max(0.0, round(quality_score, 2)),
    }
