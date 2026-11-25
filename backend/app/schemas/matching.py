from typing import List, Literal, Optional

from pydantic import BaseModel


class MatchRequest(BaseModel):
    direction: Literal["seeker_to_jobs", "enterprise_to_seekers"] = "seeker_to_jobs"
    target_id: Optional[int] = None  # resume id 或 job id；缺省用当前用户最新一份
    top_n: Optional[int] = None
    availability: Optional[str] = None  # 企业端按求职状态筛选（随时到岗/本月到岗/观望了解）；None=不筛


class MatchItem(BaseModel):
    candidate_id: int
    score: float  # 0-1
    matched_rules: List[str]  # 通过哪些硬条件
    reasons: List[str]  # 评分维度说明
    payload: dict  # 候选对象展示信息


class MatchResult(BaseModel):
    direction: str
    results: List[MatchItem]
