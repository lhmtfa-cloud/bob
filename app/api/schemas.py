from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from .models import Role

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str
    role: Role = Role.user

class UserUpdateRole(BaseModel):
    role: Role

class User(UserBase):
    id: int
    role: Role
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UploadRecord(BaseModel):
    id: int
    tracking_code: str
    original_filename: str
    status: str
    upload_time: datetime
    owner: User

    class Config:
        from_attributes = True

class UserStats(BaseModel):
    user: User
    files_uploaded_count: int
    request_count: int
    last_activity: datetime

    class Config:
        from_attributes = True

class DashboardData(BaseModel):
    recent_uploads: list[UploadRecord]
    user_stats: list[UserStats]

class UserPasswordChange(BaseModel):
    current_password: str
    new_password: str
