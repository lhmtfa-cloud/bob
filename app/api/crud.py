from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from datetime import datetime, timedelta

from . import models, schemas, auth

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password, role=user.role, api_key=user.api_key)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_role(db: Session, user_id: int, role: models.Role):
    db_user = get_user(db, user_id)
    if db_user:
        db_user.role = role
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user

def create_upload_record(db: Session, user_id: int, filename: str, tracking_code: str, status: str):
    db_upload = models.Upload(
        user_id=user_id,
        original_filename=filename,
        tracking_code=tracking_code,
        status=status,
    )
    db.add(db_upload)
    db.commit()
    db.refresh(db_upload)
    return db_upload

def update_upload_status(db: Session, tracking_code: str, status: str, zip_path: str = None):
    db_upload = db.query(models.Upload).filter(models.Upload.tracking_code == tracking_code).first()
    if db_upload:
        db_upload.status = status
        if zip_path:
            db_upload.zip_file_path = zip_path
        db.commit()

def get_uploads_last_24h(db: Session):
    time_24h_ago = datetime.utcnow() - timedelta(hours=24)
    return (
        db.query(models.Upload)
        .join(models.User)
        .options(joinedload(models.Upload.owner))
        .filter(models.Upload.upload_time >= time_24h_ago)
        .order_by(desc(models.Upload.upload_time))
        .all()
    )

def update_user_stats(db: Session, user_id: int):
    stats = db.query(models.UsageStats).filter(models.UsageStats.user_id == user_id).first()
    if not stats:
        stats = models.UsageStats(user_id=user_id)
        db.add(stats)
    
    stats.request_count = (stats.request_count or 0) + 1
    stats.last_activity = datetime.utcnow()
    db.commit()

def increment_files_uploaded_stat(db: Session, user_id: int):
    stats = db.query(models.UsageStats).filter(models.UsageStats.user_id == user_id).first()
    if not stats:
        stats = models.UsageStats(user_id=user_id)
        db.add(stats)
        
    stats.files_uploaded_count = (stats.files_uploaded_count or 0) + 1
    db.commit()

def get_all_user_stats(db: Session):
    return (
        db.query(models.UsageStats)
        .join(models.User)
        .options(joinedload(models.UsageStats.user))
        .all()
    )

def update_user_password(db: Session, user: models.User, new_password: str):
    user.hashed_password = auth.get_password_hash(new_password)
    db.commit()
    return user


def get_uploads_by_user_id(db: Session, user_id: int):
    return (
        db.query(models.Upload)
        .filter(models.Upload.user_id == user_id)
        .order_by(desc(models.Upload.upload_time))
        .all()
    )