"""简历智能体：每次分析都重新解析上传文件，避免会话缓存污染。"""

from uuid import uuid4

from graph.state import AgentState, TASK_STATUS_FAILED, TASK_STATUS_PARSING
from llm.client import chat_completion, normalize_string_list, parse_json_object
from services.file_storage_service import FileStorageService
from tools.document_parser import DocumentParserService, ParsedDocument
from tools.score_tool import parse_profile_with_audit
from tools.text_quality import validate_resume_text
from utils.hash_utils import (
    build_canonical_text_hash,
    build_raw_text_hash,
    build_resume_fingerprint,
    normalize_resume_fingerprint,
    normalize_resume_text_for_hash,
)


class ResumeAgent:
    """负责把上传简历转换为统一文本、结构化画像和解析诊断。"""

    def __init__(self) -> None:
        """初始化统一文档解析服务。"""

        self.parser_service = DocumentParserService()
        self.file_storage_service = FileStorageService()

    def run(self, state: AgentState) -> AgentState:
        """重新解析当前简历文件，并生成 resume_hash、analysis_id 和 resume_info。"""

        try:
            parsed = self.parser_service.parse(state["resume_file_path"])
            resume_text = parsed.text
            quality = validate_resume_text(resume_text)
            parsed = self._merge_quality_result(parsed, quality)
            raw_text_hash = build_raw_text_hash(resume_text)
            canonical_text_hash = build_canonical_text_hash(resume_text)
            canonical_text_len = len(normalize_resume_text_for_hash(resume_text))
            analysis_id = str(uuid4())
            base_resume_info, field_extraction_audit = parse_profile_with_audit(resume_text)
            fingerprint_payloads = normalize_resume_fingerprint(base_resume_info)
            fingerprint_payload = fingerprint_payloads["fingerprint_payload_used_for_hash"]
            fingerprint_debug_payload = fingerprint_payloads["fingerprint_debug_payload_not_used_for_hash"]
            fingerprint_payload_json = fingerprint_payloads["fingerprint_payload_json_used_for_hash"]
            fingerprint_confidence = fingerprint_payloads["fingerprint_confidence"]
            resume_fingerprint_hash = build_resume_fingerprint(base_resume_info)
            resume_hash = resume_fingerprint_hash
            resume_info = dict(base_resume_info)
            llm_resume_info = self._parse_resume_with_llm(resume_text)
            if llm_resume_info:
                resume_info.update(self._filter_llm_resume_info(llm_resume_info))
            file_metadata = self._persist_uploaded_file(
                state=state,
                analysis_id=analysis_id,
                resume_hash=resume_hash,
                raw_text_hash=raw_text_hash,
                canonical_text_hash=canonical_text_hash,
                resume_fingerprint_hash=resume_fingerprint_hash,
                fingerprint_confidence=fingerprint_confidence,
            )

            parse_result = self._build_parse_result(parsed)
            warning = self._build_warning(state.get("warning"), parsed.warnings)
            return {
                **state,
                "analysis_id": analysis_id,
                "current_analysis_id": analysis_id,
                "file_id": file_metadata.get("file_id") or state.get("file_id"),
                "original_filename": file_metadata.get("original_filename") or state.get("resume_file_name"),
                "stored_filename": file_metadata.get("stored_filename") or "",
                "file_path": file_metadata.get("file_path") or state.get("resume_file_path"),
                "resume_file_path": file_metadata.get("file_path") or state.get("resume_file_path"),
                "dedup_hit": bool(file_metadata.get("dedup_hit")),
                "dedup_source_file_id": file_metadata.get("dedup_source_file_id") or "",
                "duplicate_of_file_id": file_metadata.get("duplicate_of_file_id") or "",
                "resume_text": resume_text,
                "raw_text_hash": raw_text_hash,
                "canonical_text_hash": canonical_text_hash,
                "canonical_resume_hash": canonical_text_hash,
                "canonical_text_len": canonical_text_len,
                "resume_fingerprint_hash": resume_fingerprint_hash,
                "fingerprint_payload": fingerprint_payload,
                "fingerprint_debug_payload": fingerprint_debug_payload,
                "fingerprint_payload_used_for_hash": fingerprint_payload,
                "fingerprint_debug_payload_not_used_for_hash": fingerprint_debug_payload,
                "fingerprint_payload_json_used_for_hash": fingerprint_payload_json,
                "fingerprint_confidence": fingerprint_confidence,
                "resume_hash_source": "sha256(fingerprint_payload_json_used_for_hash)",
                "field_extraction_audit": field_extraction_audit,
                "resume_hash": resume_hash,
                "resume_info": resume_info,
                "document_parse_result": parse_result,
                "warning": warning,
                "llm_used": bool(state.get("llm_used")) or bool(llm_resume_info),
                "task_status": TASK_STATUS_PARSING,
                "error": None,
            }
        except Exception as exc:
            return {**state, "task_status": TASK_STATUS_FAILED, "error": f"简历智能体解析失败: {exc}"}

    def _persist_uploaded_file(
        self,
        state: AgentState,
        analysis_id: str,
        resume_hash: str,
        raw_text_hash: str,
        canonical_text_hash: str,
        resume_fingerprint_hash: str,
        fingerprint_confidence: str,
    ) -> dict:
        """把已解析的简历文件归档到生命周期目录并返回 metadata。"""

        if state.get("file_id"):
            return {}
        try:
            return self.file_storage_service.save_uploaded_file(
                source_path=state.get("resume_file_path") or "",
                analysis_id=analysis_id,
                actor_type=state.get("actor_type") or "candidate",
                original_filename=state.get("original_filename") or state.get("resume_file_name") or "",
                resume_hash=resume_hash,
                raw_text_hash=raw_text_hash,
                canonical_text_hash=canonical_text_hash,
                canonical_resume_hash=canonical_text_hash,
                resume_fingerprint_hash=resume_fingerprint_hash,
                fingerprint_confidence=fingerprint_confidence,
                candidate_id=state.get("candidate_id") or state.get("user_id") or "",
                company_id=state.get("company_id") or "",
                job_id=state.get("job_id") or state.get("selected_job_id") or "",
                content_type=state.get("content_type") or "",
            )
        except Exception as exc:
            warning = state.get("warning") or ""
            state["warning"] = "；".join(filter(None, [warning, f"上传文件归档失败：{exc}"]))
            return {}

    def _merge_quality_result(self, parsed: ParsedDocument, quality: dict) -> ParsedDocument:
        """把显式质量检测结果合并回 ParsedDocument，确保 ResumeAgent 执行 validate_text。"""

        return ParsedDocument(
            text=parsed.text,
            file_type=parsed.file_type,
            parser_name=parsed.parser_name,
            text_length=int(quality.get("text_length") or parsed.text_length),
            quality_score=float(quality.get("quality_score") or parsed.quality_score),
            warnings=list(quality.get("warnings") or parsed.warnings),
            metadata=parsed.metadata,
        )

    def _build_parse_result(self, parsed: ParsedDocument) -> dict:
        """构造写入 AgentState 的文档解析诊断信息。"""

        return {
            "file_type": parsed.file_type,
            "parser_name": parsed.parser_name,
            "text_length": parsed.text_length,
            "quality_score": parsed.quality_score,
            "warnings": parsed.warnings,
            "metadata": parsed.metadata,
        }

    def _build_warning(self, existing_warning: str, parse_warnings: list) -> str:
        """合并已有警告和文档解析警告，并保持内容去重。"""

        warnings = []
        if existing_warning:
            warnings.append(existing_warning)
        warnings.extend(parse_warnings or [])
        return "；".join(dict.fromkeys(warnings))

    def _parse_resume_with_llm(self, resume_text: str) -> dict:
        """调用大模型提取简历结构化字段，失败时由调用方降级到规则画像。"""

        system_prompt = "你是招聘系统中的简历解析专家，只输出 JSON。"
        user_prompt = f"""
请从以下简历中提取结构化信息，输出 JSON：
{{
  "name": "候选人姓名，无法识别则为空字符串",
  "skills": ["技能1", "技能2"],
  "projects": ["项目摘要1", "项目摘要2"],
  "advantages": ["优势1", "优势2"],
  "summary": "不超过120字的候选人摘要"
}}

简历内容：
{resume_text[:6000]}
"""
        parsed = parse_json_object(chat_completion(system_prompt, user_prompt))
        if not parsed:
            return {}
        parsed["skills"] = normalize_string_list(parsed.get("skills"))
        parsed["projects"] = normalize_string_list(parsed.get("projects"))
        parsed["advantages"] = normalize_string_list(parsed.get("advantages"))
        return parsed

    def _filter_llm_resume_info(self, llm_resume_info: dict) -> dict:
        """过滤 LLM 结果，禁止其覆盖强指纹字段。"""

        hash_fields = {"name", "email", "phone", "work_companies", "project_names"}
        return {key: value for key, value in (llm_resume_info or {}).items() if key not in hash_fields}
