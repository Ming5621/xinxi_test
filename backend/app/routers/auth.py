import re
import secrets
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, get_password_hash, verify_password
from ..database import get_db
from ..models import User, UserRole
from ..schemas import LoginRequest, StudentLoginRequest, TokenResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["认证"])

DEFAULT_STUDENT_CLASS = "课堂"


def _issue_token(user: User, db: Session) -> TokenResponse:
    user.last_seen_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """教师/管理员账号密码登录。"""
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 学生账号一律引导姓名登录（不校验密码，避免误导）
    if user.role == UserRole.student:
        raise HTTPException(status_code=400, detail="学生请使用姓名登录")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return _issue_token(user, db)


@router.post("/student-login", response_model=TokenResponse)
def student_login(request: StudentLoginRequest, db: Session = Depends(get_db)):
    """学生姓名登录：无需预设账号，输入姓名即可进入。"""
    name = (request.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请输入姓名")
    if len(name) > 40:
        raise HTTPException(status_code=400, detail="姓名过长")
    if re.search(r"[\r\n\t]", name):
        raise HTTPException(status_code=400, detail="姓名包含非法字符")

    class_name = (request.class_name or DEFAULT_STUDENT_CLASS).strip() or DEFAULT_STUDENT_CLASS

    user = (
        db.query(User)
        .filter(
            User.role == UserRole.student,
            User.name == name,
            User.class_name == class_name,
            User.is_active == True,
        )
        .first()
    )
    if not user:
        username = f"stu_{uuid.uuid4().hex[:12]}"
        user = User(
            username=username,
            password_hash=get_password_hash(secrets.token_urlsafe(16)),
            name=name,
            role=UserRole.student,
            class_name=class_name,
            is_active=True,
        )
        db.add(user)
        db.flush()

    return _issue_token(user, db)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
