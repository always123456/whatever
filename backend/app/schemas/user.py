from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "seeker"  # seeker | enterprise
    display_name: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    role: str
    display_name: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
