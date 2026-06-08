"""长期记忆使用的数据模型定义。"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class UserProfile:
    """用户画像数据模型。"""

    user_id: str
    profile: Dict[str, Any]


@dataclass
class ResumeRecord:
    """简历版本记录数据模型。"""

    user_id: str
    resume_text: str
    resume_info: Dict[str, Any]
    created_at: str


@dataclass
class MatchRecord:
    """历史匹配记录数据模型。"""

    user_id: str
    jd_text: str
    match_score: float
    match_reason: str
    missing_skills: List[str]
    created_at: str


@dataclass
class CandidateProfile:
    """candidate_profiles 表对应的数据模型。"""

    candidate_id: str
    profile: Dict[str, Any]


@dataclass
class CandidateMatchRecord:
    """candidate_match_records 表对应的数据模型。"""

    candidate_id: str
    job_id: str
    match_score: float
    missing_skills: List[str]
    created_at: str


@dataclass
class CandidateResumeVersion:
    """candidate_resume_versions 表对应的数据模型。"""

    candidate_id: str
    resume_info: Dict[str, Any]
    created_at: str


@dataclass
class CompanyProfile:
    """company_profiles 表对应的数据模型。"""

    company_id: str
    profile: Dict[str, Any]


@dataclass
class JobProfile:
    """job_profiles 表对应的数据模型。"""

    job_id: str
    company_id: str
    profile: Dict[str, Any]


@dataclass
class CandidateEvaluation:
    """candidate_evaluations 表对应的数据模型。"""

    company_id: str
    job_id: str
    candidate_id: str
    score: float
    decision: str
    created_at: str


@dataclass
class InterviewFeedback:
    """interview_feedback 表对应的数据模型。"""

    company_id: str
    job_id: str
    candidate_id: str
    feedback: Dict[str, Any]
    created_at: str
