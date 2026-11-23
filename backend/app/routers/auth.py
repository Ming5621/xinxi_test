from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import (
    STUDENT_PASSWORD_CHANGE_PURPOSE,
    create_access_token,
    get_current_user,
    get_password_hash,
    require_student_password_change,
    student_credential,
    verify_password,
)
from ..database import get_db
from ..models import User, UserRole
from ..permissions import list_all_classes
from ..schemas import (
    LoginRequest,
    StudentLoginRequest,
    StudentPasswordChallenge,
    StudentPasswordChange,
    TokenResponse,
    UserOut,
)
from ..timeutil import utc_now

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.get("/student-classes")
def student_classes(db: Session = Depends(get_db)):
    return {"classes": list_all_classes(db)}


def _student_token(user_id: int, password_hash: str, *, pending: bool = False) -> str:
    claims = {"sub": str(user_id), "student_credential": student_credential(user_id, password_hash)}
    if pending:
        claims["purpose"] = STUDENT_PASSWORD_CHANGE_PURPOSE
        return create_access_token(claims, expires_delta=timedelta(minutes=10))
    return create_access_token(claims)


def _issue_token(user: User, db: Session) -> TokenResponse:
    user.last_seen_at = utc_now()
    profile = UserOut.model_validate(user)
    token = (
        _student_token(user.id, user.password_hash)
        if user.role == UserRole.student
        else create_access_token(data={"sub": str(user.id)})
    )
    db.commit()
    return TokenResponse(access_token=token, user=profile)


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """教师/管理员账号密码登录。"""
    user = db.query(User).filter(User.username == request.username.strip()).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user.role == UserRole.student:
        raise HTTPException(status_code=400, detail="学生请使用学生登录入口")
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    return _issue_token(user, db)


@router.post("/student-login", response_model=TokenResponse | StudentPasswordChallenge)
def student_login(request: StudentLoginRequest, db: Session = Depends(get_db)):
    name = request.username.strip()
    if not name or len(name) > 40 or any(c in name for c in "\r\n\t"):
        raise HTTPException(status_code=400, detail="请输入有效的学生姓名")
    class_name = request.class_name.strip()
    password = request.password
    if not class_name or not password or "\0" in password or len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="请选择班级并输入有效密码")

    user = db.query(User).filter(
        User.role == UserRole.student,
        User.name == name,
        User.class_name == class_name,
        User.is_active.is_(True),
    ).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名、密码或班级不正确")
    if user.must_change_password:
        return StudentPasswordChallenge(password_change_token=_student_token(user.id, user.password_hash, pending=True))
    return _issue_token(user, db)


@router.post("/student-password", response_model=TokenResponse)
def change_student_password(
    request: StudentPasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(require_student_password_change),
):
    password = request.new_password
    if len(password) < 8 or not password.strip() or "\0" in password or len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="新密码至少 8 个字符，且不能超过 72 字节")
    if verify_password(password, user.password_hash):
        raise HTTPException(status_code=400, detail="新密码不能与初始密码相同")

    new_hash = get_password_hash(password)
    profile = UserOut.model_validate(user)
    changed = db.query(User).filter(
        User.id == user.id,
        User.is_active.is_(True),
        User.role == UserRole.student,
        User.must_change_password.is_(True),
        User.password_hash == user.password_hash,
    ).update({
        User.password_hash: new_hash,
        User.must_change_password: False,
        User.last_seen_at: utc_now(),
    }, synchronize_session=False)
    if not changed:
        raise HTTPException(status_code=401, detail="改密凭证已失效，请重新登录")
    db.commit()
    return TokenResponse(access_token=_student_token(profile.id, new_hash), user=profile)


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
