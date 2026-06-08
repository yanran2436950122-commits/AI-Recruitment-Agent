"""多租户记忆服务，隔离 Candidate、Company、Job 与 Shared Knowledge。"""

from typing import Any, Dict, List

from graph.state import AgentState
from memory.memory_service import MemoryService
from rag.vector_store import VectorStoreClient


class TenantMemoryService(MemoryService):
    """支持 Candidate 与 HR 双端的多租户记忆服务。"""

    def load_memory_for_actor(self, state: AgentState) -> Dict[str, Any]:
        """根据 actor_type 加载不同租户范围的记忆。"""

        actor_type = (state.get("actor_type") or "candidate").lower()
        if actor_type == "hr":
            return self._load_hr_memory(state)
        return self._load_candidate_memory(state)

    def save_memory_for_actor(self, state: AgentState) -> Dict[str, Any]:
        """根据 actor_type 保存不同租户范围的记忆。"""

        actor_type = (state.get("actor_type") or "candidate").lower()
        if actor_type == "hr":
            return self._save_hr_memory(state)
        return self._save_candidate_memory(state)

    def search_candidate_semantic_memory(
        self,
        candidate_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """只检索指定 Candidate 的私有语义记忆。"""

        return VectorStoreClient("candidate_memory").similarity_search(
            query=query,
            top_k=top_k,
            filters={"scope": "candidate", "candidate_id": candidate_id},
        )

    def search_company_semantic_memory(
        self,
        company_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """只检索指定 Company 的私有语义记忆。"""

        return VectorStoreClient("company_memory").similarity_search(
            query=query,
            top_k=top_k,
            filters={"scope": "company", "company_id": company_id},
        )

    def search_job_semantic_memory(
        self,
        job_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """只检索指定 Job 的私有语义记忆。"""

        return VectorStoreClient("job_memory").similarity_search(
            query=query,
            top_k=top_k,
            filters={"scope": "job", "job_id": job_id},
        )

    def clear_candidate_memory(self, candidate_id: str) -> None:
        """清除指定 Candidate 的私有语义记忆。"""

        VectorStoreClient("candidate_memory").delete_by_metadata(
            {"scope": "candidate", "candidate_id": candidate_id}
        )

    def clear_company_memory(self, company_id: str) -> None:
        """清除指定 Company 的私有语义记忆。"""

        VectorStoreClient("company_memory").delete_by_metadata(
            {"scope": "company", "company_id": company_id}
        )

    def clear_job_memory(self, job_id: str) -> None:
        """清除指定 Job 的私有语义记忆。"""

        VectorStoreClient("job_memory").delete_by_metadata(
            {"scope": "job", "job_id": job_id}
        )

    def _load_candidate_memory(self, state: AgentState) -> Dict[str, Any]:
        """加载求职者侧可访问的记忆，禁止读取企业私有记忆。"""

        candidate_id = state.get("candidate_id") or state.get("user_id") or "anonymous"
        session_id = state.get("session_id") or "default"
        query = state.get("user_query") or state.get("jd_text") or ""
        base = self.load_memory(candidate_id, session_id, query)
        candidate_memory = {
            "profile": base.get("user_profile") or {},
            "match_history": base.get("historical_matches") or [],
            "session": base.get("session_memory") or {},
        }
        semantic_memories = self.search_candidate_semantic_memory(candidate_id, query)
        return {
            "session_memory": base.get("session_memory") or {},
            "candidate_memory": candidate_memory,
            "user_profile": candidate_memory["profile"],
            "historical_matches": candidate_memory["match_history"],
            "semantic_memories": semantic_memories,
        }

    def _load_hr_memory(self, state: AgentState) -> Dict[str, Any]:
        """加载 HR 侧可访问的企业和岗位记忆，禁止读取 Candidate 私有语义记忆。"""

        company_id = state.get("company_id") or "default_company"
        job_id = state.get("job_id") or "default_job"
        query = state.get("user_query") or state.get("jd_text") or ""
        company_memory = {
            "profile": self.postgres_memory.get_user_profile(f"company:{company_id}") or {},
            "semantic": self.search_company_semantic_memory(company_id, query),
        }
        job_memory = {
            "profile": self.postgres_memory.get_user_profile(f"job:{job_id}") or {},
            "semantic": self.search_job_semantic_memory(job_id, query),
        }
        return {
            "company_memory": company_memory,
            "job_memory": job_memory,
            "semantic_memories": company_memory["semantic"] + job_memory["semantic"],
        }

    def _save_candidate_memory(self, state: AgentState) -> Dict[str, Any]:
        """保存求职者侧安全会话和独立分析记录，不写入业务结果到 Session。"""

        candidate_id = state.get("candidate_id") or state.get("user_id") or "anonymous"
        return self.save_memory_after_run(
            {**state, "user_id": candidate_id, "candidate_id": candidate_id}
        )

    def _save_hr_memory(self, state: AgentState) -> Dict[str, Any]:
        """保存 HR 侧安全会话和独立分析记录，不写入会话业务缓存。"""

        company_id = state.get("company_id") or "default_company"
        job_id = state.get("job_id") or "default_job"
        return self.save_memory_after_run({**state, "company_id": company_id, "job_id": job_id})
