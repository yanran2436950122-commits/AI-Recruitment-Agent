"""管理智能体：已编译 LangGraph 工作流的轻量门面。"""

from graph.state import AgentState, TASK_STATUS_FAILED, TASK_STATUS_UPLOADED
from graph.workflow import build_workflow
from monitoring.monitor_service import get_monitor_service
from tools.context_validator import ContextValidator


class ManagerAgent:
    """供 API 和前端调用 Candidate 侧完整工作流的智能体门面。"""

    def __init__(self) -> None:
        """编译并缓存 Candidate 侧 LangGraph 工作流。"""

        self.workflow = build_workflow()
        self.context_validator = ContextValidator()

    def run(
        self,
        resume_file_path: str,
        jd_text: str,
        user_id: str = "anonymous",
        session_id: str = "default",
        thread_id: str = "default",
        user_query: str = "",
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        resume_file_name: str = "",
        original_filename: str = "",
        content_type: str = "",
        target_role_id: str = "",
        role_name: str = "",
    ) -> AgentState:
        """分析一份上传简历与一段岗位 JD 的匹配情况。"""

        resolved_candidate_id = candidate_id or user_id
        monitor = get_monitor_service()
        run_id = monitor.start_run(actor_type="candidate", workflow_name="CandidateWorkflow")
        initial_state: AgentState = {
            "run_id": run_id,
            "actor_type": "candidate",
            "user_id": user_id,
            "candidate_id": resolved_candidate_id,
            "target_role_id": target_role_id,
            "selected_target_role_id": target_role_id,
            "role_name": role_name,
            "session_id": session_id,
            "thread_id": thread_id,
            "resume_file_path": resume_file_path,
            "resume_file_name": resume_file_name,
            "original_filename": original_filename or resume_file_name,
            "content_type": content_type,
            "jd_text": jd_text,
            "user_query": user_query or jd_text,
            "retry_count": 0,
            "llm_used": False,
            "task_status": TASK_STATUS_UPLOADED,
            "error": None,
        }
        try:
            self.context_validator.validate(initial_state)
            result = self.workflow.invoke(initial_state)
        except Exception as exc:
            monitor.log_error(
                run_id=run_id,
                node_name="CandidateWorkflow",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            monitor.end_run(
                run_id=run_id,
                status="failed",
                actor_type="candidate",
                workflow_name="CandidateWorkflow",
            )
            return {**initial_state, "task_status": TASK_STATUS_FAILED, "error": str(exc)}
        monitor.end_run(
            run_id=run_id,
            status="failed" if result.get("error") else "success",
            analysis_id=result.get("analysis_id") or "",
            actor_type="candidate",
            workflow_name="CandidateWorkflow",
        )
        return result
