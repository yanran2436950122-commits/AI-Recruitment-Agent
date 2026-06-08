"""关键词提取与简历/JD 评分工具。"""

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Sequence, Tuple


DEFAULT_SKILLS = [
    "python",
    "fastapi",
    "langgraph",
    "langchain",
    "rag",
    "llm",
    "openai",
    "sql",
    "mysql",
    "postgresql",
    "redis",
    "docker",
    "kubernetes",
    "linux",
    "git",
    "machine learning",
    "deep learning",
    "nlp",
    "pandas",
    "numpy",
    "scikit-learn",
    "pytorch",
    "tensorflow",
    "react",
    "vue",
    "typescript",
    "javascript",
    "java",
    "spring",
    "go",
    "microservice",
    "aws",
    "azure",
    "gcp",
    "vector database",
    "chroma",
    "milvus",
    "elasticsearch",
    "prompt engineering",
]
"""本地匹配器使用的常见技术技能。"""


def normalize_text(text: str) -> str:
    """标准化文本，便于进行大小写不敏感的匹配。"""

    return re.sub(r"\s+", " ", text or "").strip().lower()


def tokenize(text: str) -> List[str]:
    """切分英文单词、数字和常见中文词组。"""

    return re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]*|[\u4e00-\u9fff]{2,}", text or "")


def extract_skills(text: str, candidates: Sequence[str] = DEFAULT_SKILLS) -> List[str]:
    """从自由文本中提取已知技能，并保留候选技能的原始顺序。"""

    normalized = normalize_text(text)
    found = []
    for skill in candidates:
        pattern = r"(?<![a-zA-Z0-9])" + re.escape(skill.lower()) + r"(?![a-zA-Z0-9])"
        if re.search(pattern, normalized):
            found.append(skill)
    return found


def extract_keywords(text: str, limit: int = 20) -> List[str]:
    """在技能名称稀疏时提取高频关键词作为补充。"""

    stop_words = {
        "and",
        "or",
        "the",
        "with",
        "for",
        "to",
        "of",
        "in",
        "a",
        "an",
        "is",
        "are",
        "岗位",
        "负责",
        "要求",
        "经验",
        "熟悉",
        "能力",
    }
    words = [word.lower() for word in tokenize(text) if len(word) > 1]
    counter = Counter(word for word in words if word not in stop_words)
    return [word for word, _ in counter.most_common(limit)]


def parse_profile(text: str) -> Dict[str, object]:
    """将简历文本解析为轻量级结构化画像。"""

    profile, _ = parse_profile_with_audit(text)
    return profile


def parse_profile_with_audit(text: str) -> Tuple[Dict[str, object], Dict[str, dict]]:
    """将简历文本解析为结构化画像，并返回关键字段抽取审计信息。"""

    email_audit = _extract_email_with_audit(text)
    phone_audit = _extract_phone_with_audit(text)
    name_audit = _extract_name_with_audit(text)
    skills = extract_skills(text)
    keywords = extract_keywords(text)
    profile = {
        "name": name_audit["extracted_value"],
        "email": email_audit["extracted_value"],
        "phone": phone_audit["extracted_value"],
        "skills": skills,
        "project_names": _extract_project_names(text),
        "work_companies": _extract_work_companies(text),
        "keywords": keywords,
        "summary": _summarize_text(text),
    }
    return profile, {"name": name_audit, "email": email_audit, "phone": phone_audit}


def parse_jd(text: str) -> Dict[str, object]:
    """将 JD 文本解析为必备技能和代表性关键词。"""

    skills = extract_skills(text)
    keywords = extract_keywords(text)
    required_skills = skills or keywords[:8]
    return {
        "required_skills": required_skills,
        "keywords": keywords,
        "summary": _summarize_text(text),
    }


def calculate_match_score(resume_text: str, jd_text: str) -> Tuple[float, str, List[str]]:
    """计算 0-100 的匹配分，并说明缺失技能。"""

    detailed = calculate_detailed_match_score(resume_text, jd_text)
    score = float(detailed["base_score"])
    reason = (
        f"技能匹配 {detailed['skill_score']}/50，"
        f"项目经验 {detailed['project_score']}/30，"
        f"关键词覆盖 {detailed['keyword_score']}/20。"
    )
    return score, reason, list(detailed["missing_skills"])


def calculate_detailed_match_score(resume_text: str, jd_text: str) -> Dict[str, object]:
    """按技能、项目经验和关键词覆盖计算规则基础分。"""

    resume_skills = set(extract_skills(resume_text))
    jd_skills = set(extract_skills(jd_text))
    resume_keywords = set(extract_keywords(resume_text, limit=40))
    jd_keywords = set(extract_keywords(jd_text, limit=40))

    required = jd_skills or set(list(jd_keywords)[:10])
    covered = required.intersection(resume_skills.union(resume_keywords))
    missing = sorted(required.difference(covered))

    skill_score = round((len(covered) / len(required) * 50) if required else 25, 2)
    project_score = round(_project_experience_score(resume_text, jd_text), 2)
    keyword_score = round(_jaccard(resume_keywords, jd_keywords) * 20, 2)
    base_score = min(100.0, round(skill_score + project_score + keyword_score, 2))
    return {
        "base_score": base_score,
        "skill_score": skill_score,
        "project_score": project_score,
        "keyword_score": keyword_score,
        "missing_skills": missing,
    }


def build_optimization_suggestions(missing_skills: Iterable[str]) -> List[str]:
    """针对缺失技能生成具体的简历优化建议。"""

    skills = list(missing_skills)
    if not skills:
        return ["当前简历与 JD 匹配度较高，可补充项目量化结果提升说服力。"]
    return [
        f"补充与 {skill} 相关的项目经历、职责范围和可量化成果。"
        for skill in skills
    ]


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    """计算两个词集合的 Jaccard 相似度。"""

    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    return len(left_set.intersection(right_set)) / len(left_set.union(right_set))


def _project_experience_score(resume_text: str, jd_text: str) -> float:
    """根据项目相关词和 JD 关键词重合度估算项目经验分。"""

    project_markers = {"项目", "系统", "平台", "负责", "开发", "设计", "优化", "落地", "经验", "api"}
    resume_tokens = set(extract_keywords(resume_text, limit=60))
    jd_tokens = set(extract_keywords(jd_text, limit=60))
    lowered_resume = normalize_text(resume_text)
    marker_hits = sum(1 for marker in project_markers if marker in lowered_resume)
    marker_bonus = marker_hits / len(project_markers)
    overlap = _jaccard(resume_tokens, jd_tokens)
    return min(30.0, overlap * 18 + marker_bonus * 12 + (10 if marker_hits >= 3 else 0))


def _summarize_text(text: str, limit: int = 240) -> str:
    """从原始文本中生成紧凑的单行摘要。"""

    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:limit]


def _extract_email_with_audit(text: str) -> dict:
    """抽取邮箱并记录命中位置和候选值。"""

    source = text or ""
    pattern = r"[\w.\-+]+@[\w.\-]+\.\w+"
    candidates = []
    for match in re.finditer(pattern, source):
        candidates.append(_candidate_audit(match.group(0), "email_regex", source, match.start(), match.end(), ""))
    if candidates:
        accepted = candidates[0]
        return _field_audit(
            extracted_value=accepted["value"],
            extractor_name=accepted["extractor_name"],
            source=source,
            start=accepted["source_start_index"],
            end=accepted["source_end_index"],
            candidate_values=candidates,
            reject_reason="",
        )
    return _field_audit("", "email_regex", source, -1, -1, candidates, "未找到邮箱格式文本")


def _extract_phone_with_audit(text: str) -> dict:
    """抽取高置信电话号码，避免把日期、年份和项目数字识别为手机号。"""

    source = text or ""
    candidates = []

    for match in re.finditer(r"(?<!\d)(?:\+?86[-\s]?)?(1[3-9]\d[\d\s\-]{8,12})(?!\d)", source):
        raw_value = match.group(0)
        normalized = _digits_only(raw_value)
        if normalized.startswith("86") and len(normalized) == 13:
            normalized = normalized[2:]
        reject_reason = _reject_phone_reason(raw_value, normalized, source, match.start(), label_required=False)
        candidates.append(_candidate_audit(raw_value, "china_mobile_regex", source, match.start(), match.end(), reject_reason))
        if not reject_reason:
            return _field_audit(normalized, "china_mobile_regex", source, match.start(), match.end(), candidates, "")

    label_pattern = r"(?:phone|mobile|tel|telephone|电话|手机|联系方式|联系电话)\s*[:：|]?\s*([^\n]{0,80})"
    for label_match in re.finditer(label_pattern, source, flags=re.IGNORECASE):
        segment = label_match.group(1) or ""
        segment_start = label_match.start(1)
        for number_match in re.finditer(r"\+?\d[\d\s\-()/]{5,24}\d", segment):
            raw_value = number_match.group(0)
            start = segment_start + number_match.start()
            end = segment_start + number_match.end()
            normalized = _digits_only(raw_value)
            if normalized.startswith("86") and len(normalized) == 13:
                normalized = normalized[2:]
            reject_reason = _reject_phone_reason(raw_value, normalized, source, start, label_required=True)
            candidates.append(_candidate_audit(raw_value, "labeled_phone_regex", source, start, end, reject_reason))
            if not reject_reason:
                return _field_audit(normalized, "labeled_phone_regex", source, start, end, candidates, "")

    for date_match in re.finditer(r"(?:19|20)\d{2}\s*[-/年.]\s*(?:0?[1-9]|1[0-2])|(?:0?[1-9]|1[0-2])\s*[-/月.]\s*(?:19|20)\d{2}", source):
        normalized = _digits_only(date_match.group(0))
        candidates.append(
            _candidate_audit(
                normalized,
                "rejected_date_like_number",
                source,
                date_match.start(),
                date_match.end(),
                "疑似年月日期",
            )
        )

    reject_reason = "未找到高置信手机号或明确电话标签附近的有效号码"
    if candidates:
        reasons = [item["reject_reason"] for item in candidates if item["reject_reason"]]
        reject_reason = "候选号码均被过滤：" + "；".join(dict.fromkeys(reasons))
    return _field_audit("", "phone_high_confidence", source, -1, -1, candidates, reject_reason)


def _extract_name(text: str) -> str:
    """兼容旧调用：只返回姓名文本。"""

    return _extract_name_with_audit(text)["extracted_value"]


def _extract_name_with_audit(text: str) -> dict:
    """从简历顶部和显式姓名标签中提取姓名，并记录审计信息。"""

    source = text or ""
    top_text = source[:1200]
    candidates = []
    for match in re.finditer(r"(?:姓名|Name|Candidate)\s*[:：|]?\s*([^\n,，|]{1,40})", top_text, flags=re.IGNORECASE):
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        start = match.start(1)
        end = match.end(1)
        reject_reason = _reject_name_reason(value)
        candidates.append(_candidate_audit(value, "name_label", source, start, end, reject_reason))
        if not reject_reason:
            return _field_audit(value, "name_label", source, start, end, candidates, "")

    for line_start, line in _top_lines_with_offsets(source, max_chars=600, max_lines=8):
        stripped = line.strip()
        if not stripped or any(token in stripped.lower() for token in ["email", "phone", "mobile", "tel", "skills", "project", "company"]):
            continue
        reject_reason = _reject_name_reason(stripped)
        candidates.append(_candidate_audit(stripped, "top_line_candidate", source, line_start, line_start + len(line), reject_reason))
        if not reject_reason:
            return _field_audit(stripped, "top_line_candidate", source, line_start, line_start + len(line), candidates, "")

    return _field_audit("", "name_top_region", source, -1, -1, candidates, "未找到可靠姓名；候选值为空或疑似岗位名/公司名/联系方式/过长文本")


def _extract_project_names(text: str, limit: int = 8) -> List[str]:
    """从 Project/项目 字段中提取稳定项目名称或项目摘要。"""

    values = []
    for match in re.finditer(r"(?:Project(?:\s+\w+)?|项目(?:名称|经历|经验)?)\s*[:：|]\s*([^\n]{2,120})", text or "", flags=re.IGNORECASE):
        values.append(match.group(1).strip())
    return values[:limit]


def _extract_work_companies(text: str, limit: int = 8) -> List[str]:
    """从公司字段中提取工作公司名称。"""

    values = []
    for match in re.finditer(r"(?:Company|公司|任职公司)\s*[:：|]\s*([^\n]{2,80})", text or "", flags=re.IGNORECASE):
        values.append(match.group(1).strip())
    return values[:limit]


def _digits_only(value: str) -> str:
    """只保留号码中的数字。"""

    return re.sub(r"\D+", "", value or "")


def _reject_phone_reason(raw_value: str, normalized: str, source: str, start: int, label_required: bool) -> str:
    """返回电话号码候选值的拒绝原因，空字符串表示接受。"""

    raw = raw_value or ""
    context = source[max(0, start - 12) : min(len(source), start + len(raw) + 12)]
    if re.search(r"(?:19|20)\d{2}\s*[-/年.]\s*(?:0?[1-9]|1[0-2])", raw) or re.search(r"(?:19|20)\d{2}\s*[-/年.]\s*(?:0?[1-9]|1[0-2])", context):
        return "疑似年月日期"
    if re.search(r"(?:0?[1-9]|1[0-2])\s*[-/月.]\s*(?:19|20)\d{2}", raw) or re.search(r"(?:0?[1-9]|1[0-2])\s*[-/月.]\s*(?:19|20)\d{2}", context):
        return "疑似年月日期"
    if re.fullmatch(r"(?:19|20)\d{2}", normalized):
        return "疑似年份"
    if len(normalized) < 7:
        return "号码长度不足"
    if not label_required and not re.fullmatch(r"1[3-9]\d{9}", normalized):
        return "无电话标签且不是中国大陆手机号"
    if label_required and not (7 <= len(normalized) <= 16):
        return "电话标签附近号码长度不合理"
    if re.search(r"(?:薪资|工资|salary|预算|budget|金额|项目|project)", context, flags=re.IGNORECASE):
        return "疑似薪资、预算或项目数字"
    return ""


def _reject_name_reason(value: str) -> str:
    """判断姓名候选值是否可靠。"""

    candidate = re.sub(r"\s+", " ", value or "").strip()
    lowered = candidate.lower()
    if not candidate:
        return "姓名候选为空"
    if len(candidate) > 30:
        return "姓名候选过长"
    if re.search(r"[@\d]", candidate):
        return "姓名候选包含邮箱或数字"
    blocked_tokens = [
        "engineer",
        "developer",
        "manager",
        "architect",
        "公司",
        "岗位",
        "工程师",
        "开发",
        "项目",
        "简历",
        "resume",
        "skills",
        "education",
        "company",
    ]
    if any(token in lowered or token in candidate for token in blocked_tokens):
        return "疑似岗位名、公司名或栏目标题"
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", candidate):
        return ""
    if re.fullmatch(r"[A-Za-z][A-Za-z.'-]+(?:\s+[A-Za-z][A-Za-z.'-]+){0,3}", candidate):
        return ""
    return "姓名格式置信度不足"


def _candidate_audit(value: str, extractor_name: str, source: str, start: int, end: int, reject_reason: str) -> dict:
    """构造单个候选值审计记录。"""

    return {
        "value": value,
        "extractor_name": extractor_name,
        "source_text_snippet": _snippet(source, start, end),
        "source_start_index": start,
        "source_end_index": end,
        "reject_reason": reject_reason,
    }


def _field_audit(
    extracted_value: str,
    extractor_name: str,
    source: str,
    start: int,
    end: int,
    candidate_values: List[dict],
    reject_reason: str,
) -> dict:
    """构造字段级抽取审计记录。"""

    return {
        "extracted_value": extracted_value,
        "extractor_name": extractor_name,
        "source_text_snippet": _snippet(source, start, end),
        "source_start_index": start,
        "source_end_index": end,
        "candidate_values": candidate_values,
        "reject_reason": reject_reason,
    }


def _snippet(source: str, start: int, end: int, radius: int = 36) -> str:
    """截取字段命中位置附近的上下文片段。"""

    if start < 0 or end < 0:
        return ""
    left = max(0, start - radius)
    right = min(len(source), end + radius)
    return re.sub(r"\s+", " ", source[left:right]).strip()


def _top_lines_with_offsets(source: str, max_chars: int, max_lines: int) -> List[Tuple[int, str]]:
    """返回简历顶部若干行及其在原文中的起始位置。"""

    result = []
    offset = 0
    for line in source[:max_chars].splitlines(keepends=True):
        clean_line = line.rstrip("\r\n")
        result.append((offset, clean_line))
        offset += len(line)
        if len(result) >= max_lines:
            break
    return result
