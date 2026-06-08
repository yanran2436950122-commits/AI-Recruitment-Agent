"""统一记忆服务，封装会话记忆、长期记忆和语义记忆。"""

from typing import Any, Dict, List

from graph.state import AgentState
from memory.postgres_memory import PostgresMemory
from memory.redis_memory import RedisMemory
from memory.semantic_memory import SemanticMemory
from repositories.analysis_record_repository import AnalysisRecordRepository
from repositories.audit_log_repository import AuditLogRepository
from repositories.job_profile_repository import JobProfileRepository
from repositories.target_role_repository import TargetRoleRepository
from services.file_storage_service import FileStorageService
from tools.context_validator import ContextValidator


class MemoryService:
    """面向工作流和 API 的统一记忆服务。"""

    def __init__(self) -> None:
        """初始化三类记忆适配器。"""

        self.redis_memory = RedisMemory()
        self.postgres_memory = PostgresMemory()
        self.semantic_memory = SemanticMemory()
        self.context_validator = ContextValidator()
        self.file_storage_service = FileStorageService()
        self.analysis_record_repository = AnalysisRecordRepository(self.postgres_memory)
        self.audit_log_repository = AuditLogRepository(self.postgres_memory)
        self.job_profile_repository = JobProfileRepository(self.postgres_memory)
        self.target_role_repository = TargetRoleRepository(self.postgres_memory)

    def load_memory(self, user_id: str, session_id: str, query: str) -> Dict[str, Any]:
        """加载安全会话记忆和只读分析记录，禁止恢复业务分析结果。"""

        session_memory = self._sanitize_session_payload(self.redis_memory.get_session(session_id) or {})
        return {
            "session_memory": session_memory,
            "user_profile": self.postgres_memory.get_user_profile(user_id) or {},
            "historical_matches": [],
            "analysis_records": self.analysis_record_repository.list_by_owner(
                actor_type="candidate",
                candidate_id=user_id,
            ),
            "semantic_memories": self.semantic_memory.search_semantic_memory(user_id, query),
        }

    def save_memory_after_run(self, state: AgentState) -> Dict[str, Any]:
        """在工作流结束后保存安全会话记忆和独立分析记录。"""

        user_id = state.get("user_id") or "anonymous"
        session_id = state.get("session_id") or "default"
        self.redis_memory.save_session(session_id, self._build_session_payload(state))
        analysis_record = self._build_analysis_record(state)
        if analysis_record:
            saved_record = self.analysis_record_repository.save(analysis_record)
            state["analysis_record"] = saved_record
            return saved_record
        return {}

    def build_memory_context(self, state: AgentState) -> str:
        """将当前状态中的记忆信息组装为提示词上下文。"""

        return (
            f"用户画像：{state.get('user_profile') or {}}\n"
            f"历史匹配：{state.get('historical_matches') or []}\n"
            f"分析记录：{state.get('analysis_records') or []}\n"
            f"语义记忆：{state.get('semantic_memories') or []}"
        )

    def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """读取用户可查看的长期记忆信息。"""

        return {
            "user_profile": self.postgres_memory.get_user_profile(user_id) or {},
            "historical_matches": [],
            "analysis_records": self.analysis_record_repository.list_by_owner(
                actor_type="candidate",
                candidate_id=user_id,
                limit=20,
            ),
            "semantic_memories": self.semantic_memory.search_semantic_memory(
                user_id=user_id,
                query=user_id,
                top_k=20,
            ),
        }

    def clear_user_memory(self, user_id: str) -> None:
        """清除用户长期记忆和语义记忆。"""

        self.postgres_memory.clear_user(user_id)
        self.semantic_memory.clear_user(user_id)

    def list_analysis_records(
        self,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        target_role_id: str = "",
        search: str = "",
        sort_by: str = "created_at",
        descending: bool = True,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """按当前身份安全读取历史分析记录列表。"""

        self._validate_actor_scope(actor_type, candidate_id, company_id)
        offset = max(page - 1, 0) * page_size
        records = self.analysis_record_repository.list_by_owner(
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
            job_id=job_id,
            target_role_id=target_role_id if actor_type == "candidate" else "",
            search=search,
            sort_by=sort_by,
            descending=descending,
            limit=page_size,
            offset=offset,
        )
        total = self.analysis_record_repository.count_by_owner(
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
            job_id=job_id,
            target_role_id=target_role_id if actor_type == "candidate" else "",
            search=search,
        )
        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }

    def get_analysis_record(
        self,
        analysis_id: str,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        action_user_id: str = "",
    ) -> Dict[str, Any]:
        """按当前身份安全读取分析详情，并记录查看审计。"""

        self._validate_actor_scope(actor_type, candidate_id, company_id)
        record = self.analysis_record_repository.get_by_id(
            analysis_id=analysis_id,
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
        )
        if not record:
            return {}
        self.write_audit_log(
            user_id=action_user_id or candidate_id or company_id,
            actor_type=actor_type,
            action="view_report",
            analysis_id=analysis_id,
            candidate_id=candidate_id,
            company_id=company_id,
        )
        return record

    def delete_analysis_record(
        self,
        analysis_id: str,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        action_user_id: str = "",
    ) -> bool:
        """按当前身份安全软删除分析记录，并写入审计日志。"""

        self._validate_actor_scope(actor_type, candidate_id, company_id)
        record = self.analysis_record_repository.get_by_id(
            analysis_id=analysis_id,
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
        )
        deleted = self.analysis_record_repository.soft_delete(
            analysis_id=analysis_id,
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
        )
        if deleted:
            if record and record.get("file_id") and not self._file_has_active_references(record):
                self.file_storage_service.mark_file_deleted(
                    file_id=record.get("file_id") or "",
                    actor_type=actor_type,
                    candidate_id=candidate_id,
                    company_id=company_id,
                )
            self.write_audit_log(
                user_id=action_user_id or candidate_id or company_id,
                actor_type=actor_type,
                action="delete_record",
                analysis_id=analysis_id,
                candidate_id=candidate_id,
                company_id=company_id,
            )
        return deleted

    def write_audit_log(
        self,
        user_id: str,
        actor_type: str,
        action: str,
        analysis_id: str = "",
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
    ) -> Dict[str, Any]:
        """保存历史中心审计日志。"""

        return self.audit_log_repository.save(
            {
                "user_id": user_id,
                "actor_type": actor_type,
                "action": action,
                "analysis_id": analysis_id,
                "candidate_id": candidate_id,
                "company_id": company_id,
                "job_id": job_id,
            }
        )

    def get_audit_logs(
        self,
        actor_type: str,
        candidate_id: str = "",
        company_id: str = "",
        analysis_id: str = "",
    ) -> List[Dict[str, Any]]:
        """按当前身份读取审计日志。"""

        self._validate_actor_scope(actor_type, candidate_id, company_id)
        return self.audit_log_repository.list_by_owner(
            actor_type=actor_type,
            candidate_id=candidate_id if actor_type == "candidate" else "",
            company_id=company_id if actor_type == "hr" else "",
            analysis_id=analysis_id,
        )

    def create_candidate_target_role(
        self,
        candidate_id: str,
        role_name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """为 Candidate 创建求职方向。"""

        return self.target_role_repository.save(candidate_id, role_name, description)

    def list_candidate_target_roles(self, candidate_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """读取 Candidate 自己的求职方向列表。"""

        return self.target_role_repository.list_by_owner(candidate_id, status=status)

    def get_candidate_target_role(self, candidate_id: str, target_role_id: str) -> Dict[str, Any]:
        """在 Candidate 租户范围内读取求职方向。"""

        return self.target_role_repository.get_by_id(candidate_id, target_role_id)

    def update_candidate_target_role(
        self,
        candidate_id: str,
        target_role_id: str,
        role_name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """更新 Candidate 求职方向。"""

        return self.target_role_repository.update(
            candidate_id,
            target_role_id,
            role_name,
            description,
        ) or {}

    def deactivate_candidate_target_role(self, candidate_id: str, target_role_id: str) -> bool:
        """停用 Candidate 求职方向。"""

        return self.target_role_repository.mark_inactive(candidate_id, target_role_id)

    def restore_candidate_target_role(self, candidate_id: str, target_role_id: str) -> bool:
        """恢复 Candidate 已停用求职方向。"""

        return self.target_role_repository.restore(candidate_id, target_role_id)

    def create_job_profile(
        self,
        company_id: str,
        job_name: str,
        jd_text: str,
        created_by: str = "",
    ) -> Dict[str, Any]:
        """为企业创建岗位画像。"""

        return self.job_profile_repository.save(company_id, job_name, jd_text, created_by)

    def list_job_profiles(self, company_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """读取当前企业岗位列表。"""

        return self.job_profile_repository.list_by_owner(company_id, status=status)

    def get_job_profile(self, company_id: str, job_id: str) -> Dict[str, Any]:
        """在 Company 租户范围内读取岗位画像。"""

        return self.job_profile_repository.get_by_id(company_id, job_id)

    def update_job_profile(
        self,
        company_id: str,
        job_id: str,
        job_name: str,
        jd_text: str,
        created_by: str = "",
    ) -> Dict[str, Any]:
        """更新企业岗位画像并保存 JD 版本。"""

        return self.job_profile_repository.update(
            company_id,
            job_id,
            job_name,
            jd_text,
            created_by,
        ) or {}

    def deactivate_job_profile(self, company_id: str, job_id: str) -> bool:
        """停用企业岗位。"""

        return self.job_profile_repository.mark_inactive(company_id, job_id)

    def restore_job_profile(self, company_id: str, job_id: str) -> bool:
        """恢复企业已停用岗位。"""

        return self.job_profile_repository.restore(company_id, job_id)

    def list_job_versions(self, company_id: str, job_id: str) -> List[Dict[str, Any]]:
        """读取企业岗位 JD 版本历史。"""

        return self.postgres_memory.list_job_versions(company_id, job_id)

    def _build_session_payload(self, state: AgentState) -> Dict[str, Any]:
        """构造写入 Redis 的安全会话载荷，禁止保存业务分析结果。"""

        actor_type = state.get("actor_type") or "candidate"
        if actor_type == "hr":
            return self._sanitize_session_payload(
                {
                    "session_id": state.get("session_id"),
                    "actor_type": "hr",
                    "company_id": state.get("company_id"),
                    "selected_job_id": state.get("job_id") or state.get("selected_job_id"),
                    "current_analysis_id": state.get("analysis_id") or state.get("current_analysis_id"),
                }
            )
        return self._sanitize_session_payload(
            {
                "session_id": state.get("session_id"),
                "actor_type": "candidate",
                "candidate_id": state.get("candidate_id"),
                "selected_target_role_id": state.get("target_role_id") or state.get("selected_target_role_id"),
                "current_analysis_id": state.get("analysis_id") or state.get("current_analysis_id"),
            }
        )

    def _sanitize_session_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """过滤会话载荷，只保留身份和当前分析编号字段。"""

        actor_type = payload.get("actor_type")
        if actor_type == "hr":
            allowed_keys = {"session_id", "actor_type", "company_id", "selected_job_id", "current_analysis_id"}
        else:
            allowed_keys = {
                "session_id",
                "actor_type",
                "candidate_id",
                "selected_target_role_id",
                "current_analysis_id",
            }
        sanitized = {key: payload.get(key) for key in allowed_keys if payload.get(key)}
        if sanitized.get("actor_type") in {"candidate", "hr"}:
            self.context_validator.validate(self._session_payload_to_context(sanitized))
        return sanitized

    def _session_payload_to_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """把 Session Memory 载荷转换为 ContextValidator 可识别的上下文。"""

        actor_type = payload.get("actor_type")
        if actor_type == "hr":
            return {
                "actor_type": "hr",
                "company_id": payload.get("company_id"),
                "job_id": payload.get("selected_job_id"),
                "session_id": payload.get("session_id"),
                "current_analysis_id": payload.get("current_analysis_id"),
            }
        return {
            "actor_type": "candidate",
            "candidate_id": payload.get("candidate_id"),
            "target_role_id": payload.get("selected_target_role_id"),
            "session_id": payload.get("session_id"),
            "current_analysis_id": payload.get("current_analysis_id"),
        }

    def _build_analysis_record(self, state: AgentState) -> Dict[str, Any]:
        """构造独立分析记录，所有评分结果都通过 analysis_id 管理。"""

        if not state.get("analysis_id"):
            return {}
        jd_info = state.get("jd_info") or {}
        resume_info = state.get("resume_info") or {}
        common = {
            "analysis_id": state.get("analysis_id"),
            "actor_type": state.get("actor_type") or "candidate",
            "raw_text_hash": state.get("raw_text_hash") or "",
            "canonical_text_hash": state.get("canonical_text_hash") or state.get("canonical_resume_hash") or "",
            "canonical_resume_hash": state.get("canonical_resume_hash") or state.get("canonical_text_hash") or "",
            "canonical_text_len": state.get("canonical_text_len"),
            "resume_fingerprint_hash": state.get("resume_fingerprint_hash") or state.get("resume_hash"),
            "fingerprint_payload": state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload": state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_used_for_hash": state.get("fingerprint_payload_used_for_hash") or state.get("fingerprint_payload") or {},
            "fingerprint_debug_payload_not_used_for_hash": state.get("fingerprint_debug_payload_not_used_for_hash") or state.get("fingerprint_debug_payload") or {},
            "fingerprint_payload_json_used_for_hash": state.get("fingerprint_payload_json_used_for_hash") or "",
            "fingerprint_confidence": state.get("fingerprint_confidence") or "",
            "resume_hash_source": state.get("resume_hash_source") or "",
            "field_extraction_audit": state.get("field_extraction_audit") or {},
            "resume_hash": state.get("resume_hash"),
            "resume_file_name": state.get("resume_file_name") or "",
            "file_id": state.get("file_id") or "",
            "original_filename": state.get("original_filename") or state.get("resume_file_name") or "",
            "stored_filename": state.get("stored_filename") or "",
            "file_path": state.get("file_path") or state.get("resume_file_path") or "",
            "dedup_hit": bool(state.get("dedup_hit")),
            "dedup_source_file_id": state.get("dedup_source_file_id") or "",
            "duplicate_of_file_id": state.get("duplicate_of_file_id") or "",
            "target_role": state.get("role_name") or state.get("job_name") or jd_info.get("summary") or self._summarize_text(state.get("jd_text") or ""),
            "jd_snapshot": state.get("jd_snapshot") or state.get("jd_text") or "",
            "jd_text": state.get("jd_snapshot") or state.get("jd_text") or "",
            "jd_version": state.get("jd_version"),
            "jd_info": jd_info,
            "resume_info": resume_info,
            "base_match_score": state.get("base_match_score"),
            "candidate_display_score": state.get("candidate_display_score"),
            "hr_adjusted_score": state.get("hr_adjusted_score"),
            "final_display_score": state.get("final_display_score"),
            "score_detail": state.get("score_detail") or {},
            "match_reason": state.get("match_reason") or "",
            "missing_skills": state.get("missing_skills") or [],
            "risk_factors": state.get("hr_risk_factors") or [],
            "hiring_decision": state.get("hiring_decision") or state.get("hr_decision") or "",
            "optimization_suggestions": state.get("optimization_suggestions") or [],
            "learning_suggestions": state.get("learning_suggestions") or [],
            "interview_questions": state.get("interview_questions") or [],
            "hr_risk_factors": state.get("hr_risk_factors") or [],
            "hr_decision": state.get("hr_decision") or state.get("hiring_decision") or "",
            "ranking_result": state.get("ranking_result") or "",
            "report_content": state.get("final_report") or "",
            "warning": state.get("warning") or "",
            "score_reliability": state.get("score_reliability") or "normal",
            "scoring_trace": state.get("scoring_trace") or {},
            "document_parse_result": state.get("document_parse_result") or {},
            "debug_trace": state.get("debug_trace") or {},
            "task_status": state.get("task_status") or "",
            "status": "active",
        }
        if common["actor_type"] == "hr":
            return {
                **common,
                "company_id": state.get("company_id") or "",
                "job_id": state.get("job_id") or "",
                "job_name": state.get("job_name") or "",
            }
        return {
            **common,
            "candidate_id": state.get("candidate_id") or state.get("user_id") or "",
            "target_role_id": state.get("target_role_id") or "",
            "role_name": state.get("role_name") or "",
        }

    def _file_has_active_references(self, deleted_record: Dict[str, Any]) -> bool:
        """检查同一租户下是否还有其他 active 分析记录引用同一个 file_id。"""

        file_id = deleted_record.get("file_id")
        if not file_id:
            return False
        records = self.analysis_record_repository.list_by_owner(
            actor_type=deleted_record.get("actor_type") or "",
            candidate_id=deleted_record.get("candidate_id") or "",
            company_id=deleted_record.get("company_id") or "",
            status="active",
            limit=10**9,
        )
        return any(
            record.get("file_id") == file_id
            and record.get("analysis_id") != deleted_record.get("analysis_id")
            for record in records
        )

    def _validate_actor_scope(self, actor_type: str, candidate_id: str, company_id: str) -> None:
        """校验历史中心查询必须带有对应租户身份。"""

        if actor_type == "candidate" and not candidate_id:
            raise ValueError("Candidate 查询必须提供 candidate_id")
        if actor_type == "hr" and not company_id:
            raise ValueError("HR 查询必须提供 company_id")
        if actor_type not in {"candidate", "hr", "admin"}:
            raise ValueError(f"不支持的 actor_type: {actor_type}")

    def _summarize_text(self, text: str, limit: int = 80) -> str:
        """为历史列表生成简短标题。"""

        cleaned = " ".join((text or "").split())
        return cleaned[:limit] if cleaned else "未命名岗位"

    def _build_user_profile_patch(self, state: AgentState) -> Dict[str, Any]:
        """根据本次分析构造用户画像增量。"""

        jd_info = state.get("jd_info") or {}
        return {
            "latest_target_summary": jd_info.get("summary", ""),
            "latest_required_skills": jd_info.get("required_skills", []),
            "latest_analysis_id": state.get("analysis_id") or "",
        }

    def _build_semantic_summary(self, state: AgentState) -> str:
        """构造不包含完整隐私文本的语义记忆摘要。"""

        return (
            f"目标岗位摘要：{(state.get('jd_info') or {}).get('summary', '')}。"
            f"分析编号：{state.get('analysis_id')}。"
            f"简历哈希：{state.get('resume_hash')}。"
        )

    def _safe_resume_snapshot(self, resume_text: str, limit: int = 2000) -> str:
        """保存简历文本快照时限制长度，降低隐私和存储风险。"""

        return resume_text[:limit]
