from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# 评分范围（与前端星级组件一致）
RATING_MIN = 1
RATING_MAX = 5


class ReviewCreate(BaseModel):
    """求职者提交一条岗位评价（一人对同一岗位仅一条，重复提交 409）。"""

    job_id: int
    rating: int = Field(ge=RATING_MIN, le=RATING_MAX, description="总体评分 1-5")
    content: str = Field(default="", max_length=2000, description="文字评价，可空")
    anonymous: bool = False


class ReviewUpdate(BaseModel):
    """修改自己已提交的评价：只更新显式给出的字段。"""

    rating: Optional[int] = Field(default=None, ge=RATING_MIN, le=RATING_MAX)
    content: Optional[str] = Field(default=None, max_length=2000)
    anonymous: Optional[bool] = None


class ReviewOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    job_id: int
    reviewer_id: int
    reviewer_name: str = ""       # 由 service 回填；匿名时返回「匿名求职者」
    rating: int
    content: str = ""
    anonymous: bool = False
    is_mine: bool = False         # 是否当前用户所写（前端据此渲染编辑/删除）
    created_at: datetime
    updated_at: datetime


class ReviewStats(BaseModel):
    """某岗位的评价聚合：条数 + 平均分（无评价时 avg_rating 为 None）。"""

    job_id: int
    count: int = 0
    avg_rating: Optional[float] = None


class ReviewListOut(BaseModel):
    """GET /reviews?job_id= 的返回：岗位信息 + 聚合 + 评价列表。"""

    job_id: int
    job_title: str = ""
    company_name: str = ""
    stats: ReviewStats
    reviews: List[ReviewOut] = []
