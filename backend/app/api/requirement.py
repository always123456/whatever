from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm.extract import extract_card
from ..models.db_models import User
from ..schemas.requirement import (
    RequirementApplyRequest,
    RequirementCard,
    RequirementParseRequest,
    RequirementParseResponse,
)
from ..services.matching_service import apply_extracted_card
from .deps import get_current_user

router = APIRouter(prefix="/requirement", tags=["requirement"])


@router.post("/parse", response_model=RequirementParseResponse)
def parse_requirement(
    payload: RequirementParseRequest,
    _user: User = Depends(get_current_user),
):
    """原文（JD / 简历自述）→ 需求卡预览，供用户校对后再合并进卡。"""
    card, warnings = extract_card(payload.role, payload.raw_text)
    return RequirementParseResponse(card=card, warnings=warnings)


@router.post("/apply", response_model=RequirementCard)
def apply_requirement(
    payload: RequirementApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """把抽取预览卡合并写回目标实体（简历/职位）的需求卡。"""
    return apply_extracted_card(db, user, payload)
