"""LangGraph 共享状态定义。"""

from typing import Any, Dict, List, Optional, TypedDict


TASK_STATUS_CREATED = "CREATED"
"""任务已创建但尚未上传文件。"""

TASK_STATUS_UPLOADED = "UPLOADED"
"""文件已上传，等待解析。"""

TASK_STATUS_PARSING = "PARSING"
"""正在解析简历或 JD。"""

TASK_STATUS_MATCHING = "MATCHING"
"""正在进行基础匹配评分。"""

TASK_STATUS_GENERATING = "GENERATING"
"""正在生成建议、面试题或报告。"""

TASK_STATUS_COMPLETED = "COMPLETED"
"""分析任务已完成。"""

TASK_STATUS_FAILED = "FAILED"
"""分析任务执行失败。"""


class AgentState(TypedDict, total=False):
    """在所有 LangGraph 节点之间传递的状态对象。"""

    actor_type: str
    user_id: str
    company_id: Optional[str]
    candidate_id: Optional[str]
    job_id: Optional[str]
    session_id: str
    current_analysis_id: Optional[str]
    analysis_id: Optional[str]
    task_status: Optional[str]
    thread_id: str

    resume_file_path: Optional[str]
    resume_file_name: Optional[str]
    original_filename: Optional[str]
    content_type: Optional[str]
    file_id: Optional[str]
    stored_filename: Optional[str]
    file_path: Optional[str]
    dedup_hit: Optional[bool]
    dedup_source_file_id: Optional[str]
    duplicate_of_file_id: Optional[str]
    raw_text_hash: Optional[str]
    canonical_text_hash: Optional[str]
    canonical_resume_hash: Optional[str]
    canonical_text_len: Optional[int]
    resume_fingerprint_hash: Optional[str]
    fingerprint_payload: Optional[Dict[str, Any]]
    fingerprint_debug_payload: Optional[Dict[str, Any]]
    fingerprint_payload_used_for_hash: Optional[Dict[str, Any]]
    fingerprint_debug_payload_not_used_for_hash: Optional[Dict[str, Any]]
    fingerprint_payload_json_used_for_hash: Optional[str]
    fingerprint_confidence: Optional[str]
    resume_hash_source: Optional[str]
    resume_hash: Optional[str]
    jd_text: str
    jd_snapshot: Optional[str]
    jd_version: Optional[int]
    user_query: Optional[str]
    target_role_id: Optional[str]
    selected_target_role_id: Optional[str]
    role_name: Optional[str]
    job_name: Optional[str]
    selected_job_id: Optional[str]

    resume_text: Optional[str]
    resume_info: Optional[Dict[str, Any]]
    field_extraction_audit: Optional[Dict[str, Any]]
    document_parse_result: Optional[Dict[str, Any]]
    jd_info: Optional[Dict[str, Any]]

    match_score: Optional[float]
    base_match_score: Optional[float]
    candidate_display_score: Optional[float]
    hr_adjusted_score: Optional[float]
    final_display_score: Optional[float]
    score_detail: Optional[Dict[str, Any]]
    match_reason: Optional[str]
    missing_skills: Optional[List[str]]
    hr_risk_factors: Optional[List[str]]
    hr_decision: Optional[str]

    optimized_resume: Optional[str]
    optimization_suggestions: Optional[List[str]]
    learning_suggestions: Optional[List[str]]
    interview_questions: Optional[List[str]]
    final_report: Optional[str]

    retrieved_docs: Optional[List[Dict[str, Any]]]
    rag_context: Optional[str]
    retrieval_query: Optional[str]

    session_memory: Optional[Dict[str, Any]]
    candidate_memory: Optional[Dict[str, Any]]
    company_memory: Optional[Dict[str, Any]]
    job_memory: Optional[Dict[str, Any]]
    user_profile: Optional[Dict[str, Any]]
    historical_matches: Optional[List[Dict[str, Any]]]
    analysis_records: Optional[List[Dict[str, Any]]]
    semantic_memories: Optional[List[Dict[str, Any]]]

    retry_count: int
    llm_used: Optional[bool]
    llm_error: Optional[str]
    scoring_trace: Optional[Dict[str, Any]]
    score_reliability: Optional[str]
    debug_trace: Optional[Dict[str, Any]]
    analysis_record: Optional[Dict[str, Any]]
    warning: Optional[str]
    memory_error: Optional[str]
    error: Optional[str]
