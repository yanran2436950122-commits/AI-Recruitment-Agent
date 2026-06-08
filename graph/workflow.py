"""LangGraph 工作流组装。"""

from typing import Callable, Dict

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False

from agents.interview_agent import InterviewAgent
from agents.jd_agent import JDAgent
from agents.match_agent import MatchAgent
from agents.match_scoring_agent import MatchScoringAgent
from agents.memory_agent import MemoryAgent
from agents.optimize_agent import OptimizeAgent
from agents.report_agent import ReportAgent
from agents.resume_agent import ResumeAgent
from graph.router import route_after_match
from graph.state import AgentState, TASK_STATUS_FAILED
from monitoring.monitor_service import monitor_node
from tools.rag_search_tool import (
    retrieve_hiring_standard_for_state,
    retrieve_interview_context_for_state,
    retrieve_resume_examples_for_state,
)


def build_workflow():
    """构建并编译招聘分析工作流。"""

    if not LANGGRAPH_AVAILABLE:
        return _build_fallback_workflow()

    workflow = StateGraph(AgentState)
    memory_agent = MemoryAgent()
    resume_agent = ResumeAgent()
    jd_agent = JDAgent()
    match_scoring_agent = MatchScoringAgent()
    match_agent = MatchAgent()
    optimize_agent = OptimizeAgent()
    interview_agent = InterviewAgent()
    report_agent = ReportAgent()

    workflow.add_node("load_memory", monitor_node("MemoryAgent.Load")(memory_agent.load_memory_node))
    workflow.add_node("validate_target_role", monitor_node("ValidateTargetRole")(validate_target_role_node))
    workflow.add_node("resume_agent", monitor_node("ResumeAgent")(resume_agent.run))
    workflow.add_node("jd_agent", monitor_node("JDAgent")(jd_agent.run))
    workflow.add_node("match_scoring_agent", monitor_node("MatchScoringAgent")(match_scoring_agent.run))
    workflow.add_node("retrieve_hiring_standard", monitor_node("RetrieveHiringStandard")(retrieve_hiring_standard_node))
    workflow.add_node("match_agent", monitor_node("MatchAgent")(match_agent.run))
    workflow.add_node("retrieve_interview_context", monitor_node("RetrieveInterviewContext")(retrieve_interview_context_node))
    workflow.add_node("retrieve_resume_examples", monitor_node("RetrieveResumeExamples")(retrieve_resume_examples_node))
    workflow.add_node("optimize_agent", monitor_node("OptimizeAgent")(optimize_agent.run))
    workflow.add_node("interview_agent", monitor_node("InterviewAgent")(interview_agent.run))
    workflow.add_node("report_agent", monitor_node("ReportAgent")(report_agent.run))
    workflow.add_node("save_memory", monitor_node("MemoryAgent.Save")(memory_agent.save_memory_node))

    workflow.set_entry_point("load_memory")
    workflow.add_edge("load_memory", "validate_target_role")
    workflow.add_conditional_edges(
        "validate_target_role",
        route_after_validation,
        {
            "resume_agent": "resume_agent",
            "end": END,
        },
    )
    workflow.add_edge("resume_agent", "jd_agent")
    workflow.add_edge("jd_agent", "match_scoring_agent")
    workflow.add_edge("match_scoring_agent", "retrieve_hiring_standard")
    workflow.add_edge("retrieve_hiring_standard", "match_agent")
    workflow.add_conditional_edges(
        "match_agent",
        route_after_match,
        {
            "retrieve_interview_context": "retrieve_interview_context",
            "retrieve_resume_examples": "retrieve_resume_examples",
            "report_agent": "report_agent",
        },
    )
    workflow.add_edge("retrieve_interview_context", "interview_agent")
    workflow.add_edge("interview_agent", "report_agent")
    workflow.add_edge("retrieve_resume_examples", "optimize_agent")
    workflow.add_edge("optimize_agent", "match_agent")
    workflow.add_edge("report_agent", "save_memory")
    workflow.add_edge("save_memory", END)
    return workflow.compile()


def retrieve_hiring_standard_node(state: AgentState) -> AgentState:
    """检索岗位能力模型和招聘标准，并写入共享状态。"""

    docs = retrieve_hiring_standard_for_state(state)
    return {
        **state,
        "retrieved_docs": docs,
        "rag_context": _format_docs(docs),
        "retrieval_query": "hiring_standard",
    }


def validate_target_role_node(state: AgentState) -> AgentState:
    """校验 Candidate 分析必须选择目标岗位并输入本次 JD。"""

    if not state.get("target_role_id") or not state.get("role_name"):
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "请先创建或选择目标岗位。"}
    if not (state.get("jd_text") or "").strip():
        return {**state, "task_status": TASK_STATUS_FAILED, "error": "请先输入本次岗位 JD。"}
    return {
        **state,
        "selected_target_role_id": state.get("target_role_id"),
        "jd_snapshot": state.get("jd_text"),
        "error": None,
    }


def route_after_validation(state: AgentState) -> str:
    """根据校验结果决定继续工作流或直接结束。"""

    return "end" if state.get("error") else "resume_agent"


def retrieve_interview_context_node(state: AgentState) -> AgentState:
    """检索面试题库和技术题库上下文。"""

    docs = retrieve_interview_context_for_state(state)
    return {
        **state,
        "retrieved_docs": docs,
        "rag_context": _format_docs(docs),
        "retrieval_query": "interview_context",
    }


def retrieve_resume_examples_node(state: AgentState) -> AgentState:
    """检索优秀简历案例上下文。"""

    docs = retrieve_resume_examples_for_state(state)
    return {
        **state,
        "retrieved_docs": docs,
        "rag_context": _format_docs(docs),
        "retrieval_query": "resume_examples",
    }


def _format_docs(docs: list) -> str:
    """将 RAG 检索结果格式化为带来源的上下文文本。"""

    lines = []
    for index, doc in enumerate(docs or [], start=1):
        source = doc.get("source") or (doc.get("metadata") or {}).get("source") or "unknown"
        lines.append(f"[{index}] 来源: {source}\n{doc.get('text', '')}")
    return "\n\n".join(lines)


class _FallbackWorkflow:
    """仅在未安装 LangGraph 时使用的本地轻量执行器。"""

    def __init__(self, nodes: Dict[str, Callable[[AgentState], AgentState]]) -> None:
        """保存节点可调用对象，便于本地按固定顺序执行。"""

        self.nodes = nodes

    def invoke(self, state: AgentState) -> AgentState:
        """按与 LangGraph 相同的节点顺序和路由规则执行。"""

        state = self.nodes["load_memory"](state)
        state = self.nodes["validate_target_role"](state)
        if state.get("error"):
            return state
        state = self.nodes["resume_agent"](state)
        state = self.nodes["jd_agent"](state)
        state = self.nodes["match_scoring_agent"](state)
        state = self.nodes["retrieve_hiring_standard"](state)
        state = self.nodes["match_agent"](state)
        while True:
            next_node = route_after_match(state)
            if next_node == "retrieve_interview_context":
                state = self.nodes["retrieve_interview_context"](state)
                state = self.nodes["interview_agent"](state)
                state = self.nodes["report_agent"](state)
                return self.nodes["save_memory"](state)
            if next_node == "retrieve_resume_examples":
                state = self.nodes["retrieve_resume_examples"](state)
                state = self.nodes["optimize_agent"](state)
                state = self.nodes["match_agent"](state)
                continue
            state = self.nodes["report_agent"](state)
            return self.nodes["save_memory"](state)


def _build_fallback_workflow() -> _FallbackWorkflow:
    """构建无需外部依赖的工作流，用于安装依赖前的本地测试。"""

    memory_agent = MemoryAgent()
    return _FallbackWorkflow(
        {
            "load_memory": monitor_node("MemoryAgent.Load")(memory_agent.load_memory_node),
            "validate_target_role": monitor_node("ValidateTargetRole")(validate_target_role_node),
            "resume_agent": monitor_node("ResumeAgent")(ResumeAgent().run),
            "jd_agent": monitor_node("JDAgent")(JDAgent().run),
            "match_scoring_agent": monitor_node("MatchScoringAgent")(MatchScoringAgent().run),
            "retrieve_hiring_standard": monitor_node("RetrieveHiringStandard")(retrieve_hiring_standard_node),
            "match_agent": monitor_node("MatchAgent")(MatchAgent().run),
            "retrieve_interview_context": monitor_node("RetrieveInterviewContext")(retrieve_interview_context_node),
            "retrieve_resume_examples": monitor_node("RetrieveResumeExamples")(retrieve_resume_examples_node),
            "optimize_agent": monitor_node("OptimizeAgent")(OptimizeAgent().run),
            "interview_agent": monitor_node("InterviewAgent")(InterviewAgent().run),
            "report_agent": monitor_node("ReportAgent")(ReportAgent().run),
            "save_memory": monitor_node("MemoryAgent.Save")(memory_agent.save_memory_node),
        }
    )
