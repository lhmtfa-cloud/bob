from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    DateTime,
    Enum as SQLEnum,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from .database import Base

class Role(enum.Enum):
    user = "user"
    admin = "admin"
    superuser = "superuser"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(Role), default=Role.user, nullable=False)
    api_key = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    uploads = relationship("Upload", back_populates="owner", cascade="all, delete-orphan")
    stats = relationship("UsageStats", back_populates="user", uselist=False, cascade="all, delete-orphan")

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True, index=True)
    tracking_code = Column(String, unique=True, index=True)
    original_filename = Column(String)
    zip_file_path = Column(String, nullable=True)
    status = Column(String)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="uploads")

class UsageStats(Base):
    __tablename__ = "usage_stats"
    id = Column(Integer, primary_key=True, index=True)
    files_uploaded_count = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    last_activity = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="stats")
