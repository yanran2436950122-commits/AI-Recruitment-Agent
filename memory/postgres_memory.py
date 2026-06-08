"""PostgreSQL 长期记忆实现，连接失败时自动使用本地 JSON 降级。"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.config import MEMORY_DIR
from tools.score_tool import extract_skills
from tools.validators import (
    validate_jd_text,
    validate_job_name,
    validate_role_description,
    validate_target_role_name,
)


class PostgresMemory:
    """用于保存用户画像、简历版本和历史匹配记录的适配器。"""

    def __init__(self) -> None:
        """初始化长期记忆本地降级文件。"""

        self._path = MEMORY_DIR / "postgres_fallback.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def create_user_profile(self, user_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """创建或覆盖用户画像。"""

        data = self._load()
        data.setdefault("profiles", {})[user_id] = profile
        self._save(data)
        return profile

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """读取用户画像。"""

        return self._load().get("profiles", {}).get(user_id)

    def update_user_profile(self, user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        """增量更新用户画像。"""

        data = self._load()
        profile = data.setdefault("profiles", {}).setdefault(user_id, {})
        profile.update(patch)
        self._save(data)
        return profile

    def save_resume_record(
        self,
        user_id: str,
        resume_text: str,
        resume_info: Dict[str, Any],
    ) -> None:
        """保存用户简历版本记录。"""

        data = self._load()
        data.setdefault("resume_records", []).append(
            {
                "user_id": user_id,
                "resume_text": resume_text,
                "resume_info": resume_info,
                "created_at": self._now(),
            }
        )
        self._save(data)

    def save_match_record(
        self,
        user_id: str,
        jd_text: str,
        match_score: float,
        match_reason: str,
        missing_skills: List[str],
    ) -> None:
        """保存一次岗位匹配记录。"""

        data = self._load()
        data.setdefault("match_records", []).append(
            {
                "user_id": user_id,
                "jd_text": jd_text,
                "match_score": match_score,
                "match_reason": match_reason,
                "missing_skills": missing_skills,
                "created_at": self._now(),
            }
        )
        self._save(data)

    def save_analysis_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """保存一次独立分析记录，并保留 analysis_id 作为唯一索引。"""

        data = self._load()
        records = data.setdefault("analysis_records", [])
        records.append({**record, "created_at": record.get("created_at") or self._now()})
        self._save(data)
        return records[-1]

    def create_candidate_target_role(
        self,
        candidate_id: str,
        role_name: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """为 Candidate 创建一个求职方向，并保证同一候选人下名称不重复。"""

        data = self._load()
        normalized_name = role_name.strip()
        self._raise_if_invalid(validate_target_role_name(normalized_name))
        self._raise_if_invalid(validate_role_description(description))
        if not candidate_id or not normalized_name:
            raise ValueError("candidate_id 和 role_name 不能为空")
        for item in data.setdefault("candidate_target_roles", []):
            if (
                item.get("candidate_id") == candidate_id
                and item.get("role_name") == normalized_name
                and item.get("status", "active") != "deleted"
            ):
                return item
        now = self._now()
        role = {
            "target_role_id": f"target_role_{uuid4().hex}",
            "candidate_id": candidate_id,
            "role_name": normalized_name,
            "description": description.strip(),
            "created_at": now,
            "updated_at": now,
            "status": "active",
        }
        data["candidate_target_roles"].append(role)
        self._save(data)
        return role

    def list_candidate_target_roles(
        self,
        candidate_id: str,
        status: str = "active",
    ) -> List[Dict[str, Any]]:
        """读取 Candidate 自己的求职方向列表。"""

        roles = [
            item
            for item in self._load().get("candidate_target_roles", [])
            if item.get("candidate_id") == candidate_id
        ]
        if status:
            roles = [item for item in roles if item.get("status", "active") == status]
        roles.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return roles

    def get_candidate_target_role(
        self,
        candidate_id: str,
        target_role_id: str,
    ) -> Optional[Dict[str, Any]]:
        """在 Candidate 租户范围内读取单个求职方向。"""

        for role in self._load().get("candidate_target_roles", []):
            if role.get("candidate_id") == candidate_id and role.get("target_role_id") == target_role_id:
                if role.get("status", "active") == "deleted":
                    return None
                return role
        return None

    def update_candidate_target_role(
        self,
        candidate_id: str,
        target_role_id: str,
        role_name: str,
        description: str = "",
    ) -> Optional[Dict[str, Any]]:
        """更新 Candidate 求职方向名称和描述。"""

        data = self._load()
        normalized_name = role_name.strip()
        self._raise_if_invalid(validate_target_role_name(normalized_name))
        self._raise_if_invalid(validate_role_description(description))
        if not normalized_name:
            raise ValueError("role_name 不能为空")
        for item in data.get("candidate_target_roles", []):
            if (
                item.get("candidate_id") == candidate_id
                and item.get("role_name") == normalized_name
                and item.get("target_role_id") != target_role_id
                and item.get("status", "active") != "deleted"
            ):
                raise ValueError("同一求职者下目标岗位名称不能重复")
        for role in data.get("candidate_target_roles", []):
            if role.get("candidate_id") == candidate_id and role.get("target_role_id") == target_role_id:
                role.update(
                    {
                        "role_name": normalized_name,
                        "description": description.strip(),
                        "updated_at": self._now(),
                    }
                )
                self._save(data)
                return role
        return None

    def deactivate_candidate_target_role(self, candidate_id: str, target_role_id: str) -> bool:
        """停用 Candidate 求职方向，历史分析记录仍保留。"""

        data = self._load()
        for role in data.get("candidate_target_roles", []):
            if role.get("candidate_id") == candidate_id and role.get("target_role_id") == target_role_id:
                role["status"] = "inactive"
                role["updated_at"] = self._now()
                self._save(data)
                return True
        return False

    def restore_candidate_target_role(self, candidate_id: str, target_role_id: str) -> bool:
        """恢复 Candidate 已停用的求职方向。"""

        data = self._load()
        for role in data.get("candidate_target_roles", []):
            if role.get("candidate_id") == candidate_id and role.get("target_role_id") == target_role_id:
                role["status"] = "active"
                role["updated_at"] = self._now()
                self._save(data)
                return True
        return False

    def create_job_profile(
        self,
        company_id: str,
        job_name: str,
        jd_text: str,
        created_by: str = "",
    ) -> Dict[str, Any]:
        """为 HR 企业创建招聘岗位，并保存第一个 JD 版本。"""

        data = self._load()
        normalized_name = job_name.strip()
        normalized_jd = jd_text.strip()
        self._raise_if_invalid(validate_job_name(normalized_name))
        self._raise_if_invalid(validate_jd_text(normalized_jd))
        if not company_id or not normalized_name or not normalized_jd:
            raise ValueError("company_id、job_name 和 jd_text 不能为空")
        for item in data.setdefault("job_profiles", []):
            if (
                item.get("company_id") == company_id
                and item.get("job_name") == normalized_name
                and item.get("status", "active") != "deleted"
            ):
                return item
        now = self._now()
        job_id = f"job_{uuid4().hex}"
        required_skills = extract_skills(normalized_jd)
        job = {
            "job_id": job_id,
            "company_id": company_id,
            "job_name": normalized_name,
            "jd_text": normalized_jd,
            "jd_version": 1,
            "required_skills": required_skills,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        data["job_profiles"].append(job)
        data.setdefault("job_versions", []).append(
            self._build_job_version(job_id, company_id, normalized_jd, required_skills, created_by)
        )
        self._save(data)
        return job

    def list_job_profiles(self, company_id: str, status: str = "active") -> List[Dict[str, Any]]:
        """读取当前企业可访问的岗位列表。"""

        jobs = [
            item
            for item in self._load().get("job_profiles", [])
            if item.get("company_id") == company_id
        ]
        if status:
            jobs = [item for item in jobs if item.get("status", "active") == status]
        jobs.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return jobs

    def get_job_profile(self, company_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """在 Company 租户范围内读取单个岗位。"""

        for job in self._load().get("job_profiles", []):
            if job.get("company_id") == company_id and job.get("job_id") == job_id:
                if job.get("status", "active") == "deleted":
                    return None
                return job
        return None

    def update_job_profile(
        self,
        company_id: str,
        job_id: str,
        job_name: str,
        jd_text: str,
        created_by: str = "",
    ) -> Optional[Dict[str, Any]]:
        """更新企业岗位并新增 JD 版本，不覆盖旧版本。"""

        data = self._load()
        normalized_name = job_name.strip()
        normalized_jd = jd_text.strip()
        self._raise_if_invalid(validate_job_name(normalized_name))
        self._raise_if_invalid(validate_jd_text(normalized_jd))
        if not normalized_name or not normalized_jd:
            raise ValueError("job_name 和 jd_text 不能为空")
        for item in data.get("job_profiles", []):
            if (
                item.get("company_id") == company_id
                and item.get("job_name") == normalized_name
                and item.get("job_id") != job_id
                and item.get("status", "active") != "deleted"
            ):
                raise ValueError("同一企业下岗位名称不能重复")
        for job in data.get("job_profiles", []):
            if job.get("company_id") == company_id and job.get("job_id") == job_id:
                required_skills = extract_skills(normalized_jd)
                job["job_name"] = normalized_name
                if job.get("jd_text") != normalized_jd:
                    job["jd_version"] = int(job.get("jd_version") or 1) + 1
                    data.setdefault("job_versions", []).append(
                        self._build_job_version(job_id, company_id, normalized_jd, required_skills, created_by)
                    )
                job["jd_text"] = normalized_jd
                job["required_skills"] = required_skills
                job["updated_at"] = self._now()
                self._save(data)
                return job
        return None

    def deactivate_job_profile(self, company_id: str, job_id: str) -> bool:
        """停用企业岗位，保留历史分析和 JD 版本。"""

        data = self._load()
        for job in data.get("job_profiles", []):
            if job.get("company_id") == company_id and job.get("job_id") == job_id:
                job["status"] = "inactive"
                job["updated_at"] = self._now()
                self._save(data)
                return True
        return False

    def restore_job_profile(self, company_id: str, job_id: str) -> bool:
        """恢复企业已停用的岗位。"""

        data = self._load()
        for job in data.get("job_profiles", []):
            if job.get("company_id") == company_id and job.get("job_id") == job_id:
                job["status"] = "active"
                job["updated_at"] = self._now()
                self._save(data)
                return True
        return False

    def list_job_versions(self, company_id: str, job_id: str) -> List[Dict[str, Any]]:
        """读取当前企业岗位的 JD 历史版本。"""

        versions = [
            item
            for item in self._load().get("job_versions", [])
            if item.get("company_id") == company_id and item.get("job_id") == job_id
        ]
        versions.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return versions

    def get_analysis_records(
        self,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        target_role_id: str = "",
        status: str = "active",
        search: str = "",
        sort_by: str = "created_at",
        descending: bool = True,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """按身份、租户、岗位和状态读取分析记录。"""

        records = list(self._load().get("analysis_records", []))
        if actor_type:
            records = [item for item in records if item.get("actor_type") == actor_type]
        if candidate_id:
            records = [item for item in records if item.get("candidate_id") == candidate_id]
        if company_id:
            records = [item for item in records if item.get("company_id") == company_id]
        if job_id:
            records = [item for item in records if item.get("job_id") == job_id]
        if target_role_id:
            records = [item for item in records if item.get("target_role_id") == target_role_id]
        if status:
            records = [item for item in records if item.get("status", "active") == status]
        if search:
            keyword = search.lower()
            records = [
                item
                for item in records
                if keyword in json.dumps(item, ensure_ascii=False).lower()
            ]
        records.sort(key=lambda item: item.get(sort_by) or "", reverse=descending)
        return records[offset : offset + limit]

    def count_analysis_records(
        self,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
        job_id: str = "",
        target_role_id: str = "",
        status: str = "active",
        search: str = "",
    ) -> int:
        """统计指定租户范围内可见的分析记录数量。"""

        return len(
            self.get_analysis_records(
                actor_type=actor_type,
                candidate_id=candidate_id,
                company_id=company_id,
                job_id=job_id,
                target_role_id=target_role_id,
                status=status,
                search=search,
                limit=10**9,
                offset=0,
            )
        )

    def get_analysis_record_by_id(
        self,
        analysis_id: str,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        """在租户约束内读取单条分析记录。"""

        for record in self._load().get("analysis_records", []):
            if record.get("analysis_id") != analysis_id:
                continue
            if actor_type and record.get("actor_type") != actor_type:
                continue
            if candidate_id and record.get("candidate_id") != candidate_id:
                continue
            if company_id and record.get("company_id") != company_id:
                continue
            if record.get("status", "active") == "deleted":
                return None
            return record
        return None

    def soft_delete_analysis_record(
        self,
        analysis_id: str,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
    ) -> bool:
        """在租户约束内软删除分析记录，避免物理删除审计链路。"""

        data = self._load()
        for record in data.get("analysis_records", []):
            if record.get("analysis_id") != analysis_id:
                continue
            if actor_type and record.get("actor_type") != actor_type:
                continue
            if candidate_id and record.get("candidate_id") != candidate_id:
                continue
            if company_id and record.get("company_id") != company_id:
                continue
            record["status"] = "deleted"
            record["deleted_at"] = self._now()
            self._save(data)
            return True
        return False

    def save_audit_log(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """保存历史中心操作审计日志。"""

        data = self._load()
        audit_logs = data.setdefault("audit_logs", [])
        audit_logs.append({**log, "timestamp": log.get("timestamp") or self._now()})
        self._save(data)
        return audit_logs[-1]

    def get_audit_logs(
        self,
        actor_type: str = "",
        candidate_id: str = "",
        company_id: str = "",
        analysis_id: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """按租户范围读取审计日志。"""

        logs = list(self._load().get("audit_logs", []))
        if actor_type:
            logs = [item for item in logs if item.get("actor_type") == actor_type]
        if candidate_id:
            logs = [item for item in logs if item.get("candidate_id") == candidate_id]
        if company_id:
            logs = [item for item in logs if item.get("company_id") == company_id]
        if analysis_id:
            logs = [item for item in logs if item.get("analysis_id") == analysis_id]
        logs.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return logs[:limit]

    def get_historical_matches(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """读取用户最近的历史匹配记录。"""

        records = [
            item
            for item in self._load().get("match_records", [])
            if item.get("user_id") == user_id
        ]
        records.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return records[:limit]

    def clear_user(self, user_id: str) -> None:
        """清除用户长期结构化记忆。"""

        data = self._load()
        data.get("profiles", {}).pop(user_id, None)
        data["resume_records"] = [
            item for item in data.get("resume_records", []) if item.get("user_id") != user_id
        ]
        data["match_records"] = [
            item for item in data.get("match_records", []) if item.get("user_id") != user_id
        ]
        data["analysis_records"] = [
            item
            for item in data.get("analysis_records", [])
            if item.get("candidate_id") != user_id and item.get("user_id") != user_id
        ]
        self._save(data)

    def _load(self) -> Dict[str, Any]:
        """读取本地长期记忆降级文件。"""

        if not self._path.exists():
            return self._empty_data()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            data.setdefault("profiles", {})
            data.setdefault("resume_records", [])
            data.setdefault("match_records", [])
            data.setdefault("analysis_records", [])
            data.setdefault("audit_logs", [])
            data.setdefault("candidate_target_roles", [])
            data.setdefault("job_profiles", [])
            data.setdefault("job_versions", [])
            return data
        except json.JSONDecodeError:
            return self._empty_data()

    def _save(self, data: Dict[str, Any]) -> None:
        """写入本地长期记忆降级文件。"""

        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _now(self) -> str:
        """生成 UTC 时间戳。"""

        return datetime.now(timezone.utc).isoformat()

    def _empty_data(self) -> Dict[str, Any]:
        """构造本地长期记忆文件的空数据结构。"""

        return {
            "profiles": {},
            "resume_records": [],
            "match_records": [],
            "analysis_records": [],
            "audit_logs": [],
            "candidate_target_roles": [],
            "job_profiles": [],
            "job_versions": [],
        }

    def _build_job_version(
        self,
        job_id: str,
        company_id: str,
        jd_text: str,
        required_skills: List[str],
        created_by: str,
    ) -> Dict[str, Any]:
        """构造岗位 JD 版本记录。"""

        return {
            "version_id": f"job_version_{uuid4().hex}",
            "job_id": job_id,
            "company_id": company_id,
            "jd_text": jd_text,
            "required_skills": required_skills,
            "created_at": self._now(),
            "created_by": created_by,
        }

    def _raise_if_invalid(self, validation: Dict[str, Any]) -> None:
        """在校验失败时抛出易读错误。"""

        if not validation.get("valid"):
            raise ValueError("；".join(validation.get("errors") or ["输入校验失败"]))
