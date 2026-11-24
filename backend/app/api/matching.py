from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import User
from ..schemas.matching import MatchRequest, MatchResult
from ..services.matching_service import match
from .deps import get_current_user

router = APIRouter(prefix="/match", tags=["matching"])


@router.post("", response_model=MatchResult)
def run_match(
    req: MatchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return match(db, user, req)
