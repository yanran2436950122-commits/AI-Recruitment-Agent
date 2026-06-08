"""Actor Context 校验工具，防止 Candidate 与 HR 上下文互相污染。"""

from typing import Dict, Mapping


CANDIDATE_FORBIDDEN_KEYS = {"company_id", "job_id", "job_name", "selected_job_id"}
"""Candidate Context 中禁止出现的 HR 字段。"""

HR_FORBIDDEN_KEYS = {"candidate_id", "target_role_id", "role_name", "selected_target_role_id"}
"""HR Context 中禁止出现的 Candidate 字段。"""


class ContextValidator:
    """校验 CandidateContext 与 HRContext 的字段边界。"""

    def validate(self, context: Mapping[str, object]) -> None:
        """根据 actor_type 分发到对应上下文校验逻辑。"""

        actor_type = str(context.get("actor_type") or "").lower()
        if actor_type == "candidate":
            self.validate_candidate_context(context)
            return
        if actor_type == "hr":
            self.validate_hr_context(context)
            return
        raise ValueError(f"不支持的 actor_type: {actor_type}")

    def validate_candidate_context(self, context: Mapping[str, object]) -> None:
        """校验 Candidate Context 不包含 HR 字段。"""

        polluted_keys = self._present_keys(context, CANDIDATE_FORBIDDEN_KEYS)
        if polluted_keys:
            raise ValueError(f"Candidate Context 污染: {', '.join(polluted_keys)}")

    def validate_hr_context(self, context: Mapping[str, object]) -> None:
        """校验 HR Context 不包含 Candidate 字段。"""

        polluted_keys = self._present_keys(context, HR_FORBIDDEN_KEYS)
        if polluted_keys:
            raise ValueError(f"HR Context 污染: {', '.join(polluted_keys)}")

    def clean_candidate_context(self, context: Mapping[str, object]) -> Dict[str, object]:
        """返回只包含 Candidate 允许字段的上下文副本。"""

        allowed_keys = {
            "actor_type",
            "candidate_id",
            "target_role_id",
            "role_name",
            "session_id",
            "current_analysis_id",
        }
        return {key: context.get(key) for key in allowed_keys if context.get(key)}

    def clean_hr_context(self, context: Mapping[str, object]) -> Dict[str, object]:
        """返回只包含 HR 允许字段的上下文副本。"""

        allowed_keys = {
            "actor_type",
            "company_id",
            "job_id",
            "job_name",
            "session_id",
            "current_analysis_id",
        }
        return {key: context.get(key) for key in allowed_keys if context.get(key)}

    def _present_keys(self, context: Mapping[str, object], keys: set) -> list:
        """返回上下文中值不为空的指定字段。"""

        return sorted(key for key in keys if context.get(key))
