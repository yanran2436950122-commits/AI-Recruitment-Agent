"""统一基础评分智能体：Candidate 与 HR 共用的唯一基础评分入口。"""

from graph.state import AgentState, TASK_STATUS_MATCHING
from tools.score_tool import calculate_detailed_match_score, calculate_match_score


class MatchScoringAgent:
    """只负责规则基础评分、可信度判断和评分追踪。"""

    def run(self, state: AgentState) -> AgentState:
        """根据统一 resume_text 和 JD 文本计算基础匹配分。"""

        resume_text = state.get("resume_text") or ""
        jd_text = state.get("jd_text") or ""
        parse_result = state.get("document_parse_result") or {}
        quality_score = float(parse_result.get("quality_score") or 0)
        score_reliability = self._build_score_reliability(len(resume_text), quality_score)
        warnings = self._build_warnings(state, resume_text, jd_text, parse_result, score_reliability)

        score, reason, missing_skills = calculate_match_score(resume_text, jd_text)
        detail = calculate_detailed_match_score(resume_text, jd_text)
        scoring_trace = self._build_scoring_trace(
            state=state,
            resume_text=resume_text,
            jd_text=jd_text,
            parse_result=parse_result,
            detail=detail,
            score=score,
            score_reliability=score_reliability,
        )
        debug_trace = self._build_debug_trace(state, scoring_trace)
        return {
            **state,
            "base_match_score": score,
            "candidate_display_score": score,
            "hr_adjusted_score": score,
            "final_display_score": score,
            "match_score": score,
            "match_reason": reason,
            "missing_skills": missing_skills,
            "score_detail": detail,
            "score_reliability": score_reliability,
            "scoring_trace": scoring_trace,
            "debug_trace": debug_trace,
            "warning": "；".join(dict.fromkeys(warnings)) if warnings else state.get("warning"),
            "task_status": TASK_STATUS_MATCHING,
            "error": None,
        }

    def _build_score_reliability(self, resume_text_len: int, quality_score: float) -> str:
        """根据解析长度和质量分判断评分可信度。"""

        if resume_text_len < 200 or quality_score < 0.3:
            return "low"
        return "normal"

    def _build_warnings(
        self,
        state: AgentState,
        resume_text: str,
        jd_text: str,
        parse_result: dict,
        score_reliability: str,
    ) -> list:
        """汇总评分前检查和解析诊断中的警告。"""

        warnings = []
        if state.get("warning"):
            warnings.append(state["warning"])
        if not resume_text:
            warnings.append("resume_text 为空，基础评分可信度较低。")
        if not jd_text:
            warnings.append("jd_text 为空，基础评分可信度较低。")
        if len(resume_text) < 200:
            warnings.append("简历文本解析过短，可能导致评分偏低。")
        if score_reliability == "low":
            warnings.append("当前评分可能因文档解析不完整而失真。")
        warnings.extend(parse_result.get("warnings") or [])
        return warnings

    def _build_scoring_trace(
        self,
        state: AgentState,
        resume_text: str,
        jd_text: str,
        parse_result: dict,
        detail: dict,
        score: float,
        score_reliability: str,
    ) -> dict:
        """构造可解释的评分追踪信息。"""

        return {
            "analysis_id": state.get("analysis_id"),
            "actor_type": state.get("actor_type") or "candidate",
            "raw_text_hash": state.get("raw_text_hash"),
            "canonical_text_hash": state.get("canonical_text_hash"),
            "canonical_resume_hash": state.get("canonical_resume_hash"),
            "resume_fingerprint_hash": state.get("resume_fingerprint_hash"),
            "fingerprint_payload": state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload": state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_used_for_hash": state.get("fingerprint_payload_used_for_hash") or state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload_not_used_for_hash": state.get("fingerprint_debug_payload_not_used_for_hash") or state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_json_used_for_hash": state.get("fingerprint_payload_json_used_for_hash") or "",
            "fingerprint_confidence": state.get("fingerprint_confidence") or "",
            "resume_hash_source": state.get("resume_hash_source") or "sha256(fingerprint_payload_json_used_for_hash)",
            "field_extraction_audit": state.get("field_extraction_audit") or {},
            "resume_hash": state.get("resume_hash"),
            "canonical_text_len": state.get("canonical_text_len"),
            "resume_text_len": len(resume_text),
            "jd_text_len": len(jd_text),
            "resume_preview": resume_text[:300],
            "jd_preview": jd_text[:300],
            "score_detail": detail,
            "base_match_score": score,
            "file_type": parse_result.get("file_type"),
            "parser_name": parse_result.get("parser_name"),
            "quality_score": parse_result.get("quality_score"),
            "parse_warnings": parse_result.get("warnings") or [],
            "score_reliability": score_reliability,
            "source_agent": "MatchScoringAgent",
            "source_tool": "tools.score_tool.calculate_match_score",
        }

    def _build_debug_trace(self, state: AgentState, scoring_trace: dict) -> dict:
        """生成前端可展示的本次分析调试追踪。"""

        return {
            "analysis_id": state.get("analysis_id"),
            "actor_type": state.get("actor_type") or "candidate",
            "raw_text_hash": state.get("raw_text_hash"),
            "canonical_text_hash": state.get("canonical_text_hash"),
            "canonical_resume_hash": state.get("canonical_resume_hash"),
            "resume_fingerprint_hash": state.get("resume_fingerprint_hash"),
            "fingerprint_payload": state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload": state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_used_for_hash": state.get("fingerprint_payload_used_for_hash") or state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload_not_used_for_hash": state.get("fingerprint_debug_payload_not_used_for_hash") or state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_json_used_for_hash": state.get("fingerprint_payload_json_used_for_hash") or "",
            "fingerprint_confidence": state.get("fingerprint_confidence") or "",
            "resume_hash_source": state.get("resume_hash_source") or "sha256(fingerprint_payload_json_used_for_hash)",
            "field_extraction_audit": state.get("field_extraction_audit") or {},
            "resume_hash": state.get("resume_hash"),
            "canonical_text_len": scoring_trace.get("canonical_text_len"),
            "resume_text_len": scoring_trace.get("resume_text_len"),
            "quality_score": scoring_trace.get("quality_score"),
            "parser_name": scoring_trace.get("parser_name"),
            "base_match_score": scoring_trace.get("base_match_score"),
            "score_reliability": scoring_trace.get("score_reliability"),
        }
