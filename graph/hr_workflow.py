"""HR 侧 LangGraph 工作流组装。"""

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False

from agents.candidate_screening_agent import CandidateScreeningAgent
from agents.evaluation_agent import EvaluationAgent
from agents.interview_design_agent import InterviewDesignAgent
from agents.jd_agent import JDAgent
from agents.job_profile_agent import JobProfileAgent
from agents.match_scoring_agent import MatchScoringAgent
from agents.memory_agent import MemoryAgent
from agents.ranking_agent import RankingAgent
from agents.resume_agent import ResumeAgent
from graph.state import AgentState, TASK_STATUS_FAILED
from memory.tenant_memory_service import TenantMemoryService
from monitoring.monitor_service import monitor_node


def build_hr_workflow():
    """构建并编译 HR 侧招聘工作流。"""

    memory_agent = MemoryAgent()
    nodes = {
        "load_memory": monitor_node("MemoryAgent.Load")(memory_agent.load_memory_node),
        "validate_selected_job": monitor_node("ValidateSelectedJob")(validate_selected_job_node),
        "load_job_profile": monitor_node("LoadJobProfile")(load_job_profile_node),
        "resume_agent": monitor_node("ResumeAgent")(ResumeAgent().run),
        "jd_agent": monitor_node("JDAgent")(JDAgent().run),
        "match_scoring_agent": monitor_node("MatchScoringAgent")(MatchScoringAgent().run),
        "job_profile_agent": monitor_node("JobProfileAgent")(JobProfileAgent().run),
        "candidate_screening_agent": monitor_node("CandidateScreeningAgent")(CandidateScreeningAgent().run),
        "ranking_agent": monitor_node("RankingAgent")(RankingAgent().run),
        "interview_design_agent": monitor_node("InterviewDesignAgent")(InterviewDesignAgent().run),
        "evaluation_agent": monitor_node("EvaluationAgent")(EvaluationAgent().run),
        "save_memory": monitor_node("MemoryAgent.Save")(memory_agent.save_memory_node),
    }
    if not LANGGRAPH_AVAILABLE:
        return _FallbackHRWorkflow(nodes)

    workflow = StateGraph(AgentState)
    for name, node in nodes.items():
        workflow.add_node(name, node)
    workflow.set_entry_point("load_memory")
    workflow.add_edge("load_memory", "validate_selected_job")
    workflow.add_conditional_edges(
        "validate_selected_job",
        route_after_validation,
        {
            "load_job_profile": "load_job_profile",
            "end": END,
        },
    )
    workflow.add_conditional_edges(
        "load_job_profile",
        route_after_validation,
        {
            "resume_agent": "resume_agent",
            "end": END,
        },
    )
    workflow.add_edge("resume_agent", "jd_agent")
    workflow.add_edge("jd_agent", "match_scoring_agent")
    workflow.add_edge("match_scoring_agent", "job_profile_agent")
    workflow.add_edge("job_profile_agent", "candidate_screening_agent")
    workflow.add_edge("candidate_screening_agent", "ranking_agent")
    workflow.add_edge("ranking_agent", "interview_design_agent")
    workflow.add_edge("interview_design_agent", "evaluation_agent")
    workflow.add_edge("evaluation_agent", "save_memory")
    workflow.add_edge("save_memory", END)
    return workflow.compile()


def validate_selected_job_node(state: AgentState) -> AgentState:
    """校验 HR 筛选必须选择企业和岗位。"""

    if not state.get("company_id"):
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "请先选择企业。"}
    if not state.get("job_id"):
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "请先创建或选择岗位。"}
    return {**state, "selected_job_id": state.get("job_id"), "error": None}


def load_job_profile_node(state: AgentState) -> AgentState:
    """根据 company_id 和 job_id 读取企业岗位 JD，禁止使用临时 JD。"""

    job = TenantMemoryService().get_job_profile(
        company_id=state.get("company_id") or "",
        job_id=state.get("job_id") or "",
    )
    if not job:
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "请先创建或选择岗位。"}
    if job.get("status", "active") != "active":
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "当前岗位已停用，请重新选择岗位。"}
    if not (job.get("jd_text") or "").strip():
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "当前岗位 JD 为空，请先在岗位管理中维护 JD。"}
    return {
        **state,
        "job_id": job.get("job_id"),
        "selected_job_id": job.get("job_id"),
        "job_name": job.get("job_name"),
        "jd_text": job.get("jd_text"),
        "jd_snapshot": job.get("jd_text"),
        "jd_version": job.get("jd_version"),
        "error": None,
    }


def route_after_validation(state: AgentState) -> str:
    """根据 HR 校验结果决定继续执行或直接结束。"""

    return "end" if state.get("error") else "load_job_profile" if not state.get("jd_snapshot") else "resume_agent"


class _FallbackHRWorkflow:
    """未安装 LangGraph 时使用的 HR 侧本地顺序执行器。"""

    def __init__(self, nodes: dict) -> None:
        """保存 HR 工作流节点。"""

        self.nodes = nodes

    def invoke(self, state: AgentState) -> AgentState:
        """按 HR 工作流顺序执行所有节点。"""

        for name in [
            "load_memory",
            "validate_selected_job",
            "load_job_profile",
            "resume_agent",
            "jd_agent",
            "match_scoring_agent",
            "job_profile_agent",
            "candidate_screening_agent",
            "ranking_agent",
            "interview_design_agent",
            "evaluation_agent",
            "save_memory",
        ]:
            state = self.nodes[name](state)
            if state.get("error"):
                return state
        return state
