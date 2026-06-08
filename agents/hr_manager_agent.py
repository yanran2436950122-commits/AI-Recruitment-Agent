"""HR 管理智能体：封装 HR 侧 LangGraph 工作流。"""

from graph.hr_workflow import build_hr_workflow
from graph.state import AgentState, TASK_STATUS_FAILED, TASK_STATUS_UPLOADED
from monitoring.monitor_service import get_monitor_service
from tools.context_validator import ContextValidator


class HRManagerAgent:
    """供 API 调用 HR 侧完整工作流的智能体门面。"""

    def __init__(self) -> None:
        """编译并缓存 HR 侧工作流。"""

        self.workflow = build_hr_workflow()
        self.context_validator = ContextValidator()

    def run(
        self,
        resume_file_path: str,
        jd_text: str,
        company_id: str,
        job_id: str,
        session_id: str,
        resume_file_name: str = "",
        original_filename: str = "",
        content_type: str = "",
    ) -> AgentState:
        """执行一次 HR 侧候选人筛选与评估。"""

        monitor = get_monitor_service()
        run_id = monitor.start_run(actor_type="hr", workflow_name="HRWorkflow")
        initial_state: AgentState = {
            "run_id": run_id,
            "actor_type": "hr",
            "user_id": company_id,
            "company_id": company_id,
            "job_id": job_id,
            "session_id": session_id,
            "thread_id": session_id,
            "resume_file_path": resume_file_path,
            "resume_file_name": resume_file_name,
            "original_filename": original_filename or resume_file_name,
            "content_type": content_type,
            "jd_text": jd_text,
            "user_query": jd_text,
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
                node_name="HRWorkflow",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
            monitor.end_run(
                run_id=run_id,
                status="failed",
                actor_type="hr",
                workflow_name="HRWorkflow",
            )
            return {**initial_state, "task_status": TASK_STATUS_FAILED, "error": str(exc)}
        monitor.end_run(
            run_id=run_id,
            status="failed" if result.get("error") else "success",
            analysis_id=result.get("analysis_id") or "",
            actor_type="hr",
            workflow_name="HRWorkflow",
        )
        return result
