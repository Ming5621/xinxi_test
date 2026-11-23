from datetime import datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .database import engine, get_db
from .models import AuthSigningKey, User, UserRole

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12
DEFAULT_STUDENT_PASSWORD = "123456"
STUDENT_PASSWORD_CHANGE_PURPOSE = "student_password_change"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def migrate_student_passwords(engine: Engine) -> None:
    """旧版学生未使用密码。升级时保留账号和成绩，并设置一次初始密码。"""
    if "must_change_password" in {col["name"] for col in inspect(engine).get_columns("users")}:
        return
    with engine.begin() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        if "must_change_password" in {col["name"] for col in inspect(conn).get_columns("users")}:
            return
        conn.exec_driver_sql("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT 0")
        conn.execute(
            text("UPDATE users SET password_hash = :password_hash, must_change_password = 1 WHERE role = 'student'"),
            {"password_hash": get_password_hash(DEFAULT_STUDENT_PASSWORD)},
        )


def student_credential(user_id: int, password_hash: str) -> str:
    return sha256(f"{user_id}:{password_hash}".encode()).hexdigest()


@lru_cache(maxsize=1)
def auth_signing_key() -> str:
    key = select(AuthSigningKey.secret).where(AuthSigningKey.id == 1)
    with engine.begin() as conn:
        secret = conn.execute(key).scalar_one_or_none()
        if secret is not None:
            return secret
        conn.execute(insert(AuthSigningKey).values(id=1, secret=token_urlsafe(48)).on_conflict_do_nothing())
        return conn.execute(key).scalar_one()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, auth_signing_key(), algorithm=ALGORITHM)


def _get_session_user(token: str, db: Session, *, password_change: bool = False) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth_signing_key(), algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        user_id = int(user_id)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    expected_purpose = STUDENT_PASSWORD_CHANGE_PURPOSE if password_change else None
    if payload.get("purpose") != expected_purpose:
        raise credentials_exception
    credential = payload.get("student_credential")
    if user.role == UserRole.student:
        if (
            not isinstance(credential, str)
            or not compare_digest(credential.encode(), student_credential(user.id, user.password_hash).encode())
            or user.must_change_password != password_change
        ):
            raise credentials_exception
    elif password_change or credential is not None:
        raise credentials_exception
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return _get_session_user(token, db)


def require_student_password_change(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return _get_session_user(token, db, password_change=True)


def require_teacher(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (UserRole.teacher, UserRole.admin):
        raise HTTPException(status_code=403, detail="需要教师权限")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.student:
        raise HTTPException(status_code=403, detail="需要学生权限")
    return current_user
