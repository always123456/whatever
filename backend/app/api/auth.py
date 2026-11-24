from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.db_models import User
from ..schemas.user import LoginIn, Token, UserCreate
from .deps import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if payload.role not in ("seeker", "enterprise"):
        raise HTTPException(400, detail="角色必须是 seeker 或 enterprise")
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(400, detail="用户名已存在")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=Token)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, detail="用户名或密码错误")
    return Token(access_token=create_access_token(user.id), user=user)
