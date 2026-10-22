import re
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_password_hash, require_teacher
from ..database import get_db
from ..models import User, UserRole
from ..permissions import active_student_name_taken, apply_student_scope, ensure_class_access, filter_class_name
from ..schemas import UserCreate, UserOut, UserUpdate
from .auth import DEFAULT_STUDENT_CLASS

router = APIRouter(prefix="/api/users", tags=["用户管理"])

MANAGEABLE_ROLES = (UserRole.teacher, UserRole.student)


def _ensure_manage_user(current_user: User, target: User) -> None:
    if current_user.role == UserRole.admin:
        return
    if target.role != UserRole.student:
        raise HTTPException(status_code=403, detail="仅管理员可管理教师账号")
    ensure_class_access(current_user, target.class_name)


def _clean_username(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(username) > 50:
        raise HTTPException(status_code=400, detail="用户名不能超过50个字符")
    if re.search(r"\s", username):
        raise HTTPException(status_code=400, detail="用户名不能包含空格")
    return username


def _clean_name(name: str, *, for_student: bool) -> str:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if for_student:
        if len(name) > 40:
            raise HTTPException(status_code=400, detail="学生姓名不能超过40个字")
        if re.search(r"[\r\n\t]", name):
            raise HTTPException(status_code=400, detail="姓名包含非法字符")
    elif len(name) > 100:
        raise HTTPException(status_code=400, detail="姓名过长")
    return name


def _clean_class_list(classes: list[str] | None) -> list[str]:
    seen: list[str] = []
    for item in classes or []:
        name = (item or "").strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _resolve_password(password: str | None, *, required: bool) -> str:
    raw = password or ""
    if raw and not raw.strip():
        raise HTTPException(status_code=400, detail="密码不能只包含空格")
    cleaned = raw.strip()
    if not cleaned:
        if required:
            raise HTTPException(status_code=400, detail="请设置密码")
        return secrets.token_urlsafe(16)
    if len(cleaned) > 72:
        raise HTTPException(status_code=400, detail="密码过长")
    return cleaned


def _ensure_unique_username(db: Session, username: str, exclude_id: int | None = None) -> None:
    query = db.query(User).filter(User.username == username)
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="用户名已存在")


def _ensure_student_identity(db: Session, name: str, class_name: str, exclude_id: int | None = None) -> None:
    if active_student_name_taken(db, name, class_name, exclude_id):
        raise HTTPException(
            status_code=400,
            detail=f"班级「{class_name}」已有同名学生「{name}」，姓名登录无法区分",
        )


def _count_other_active_admins(db: Session, user_id: int) -> int:
    return (
        db.query(User)
        .filter(User.role == UserRole.admin, User.is_active == True, User.id != user_id)  # noqa: E712
        .count()
    )


@router.get("", response_model=list[UserOut])
def list_users(
    role: UserRole | None = None,
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    query = db.query(User)
    if current_user.role == UserRole.teacher:
        if role and role != UserRole.student:
            raise HTTPException(status_code=403, detail="无权查看该角色用户")
        query = apply_student_scope(query, current_user, class_name)
    else:
        if role:
            query = query.filter(User.role == role)
        if class_name:
            query = query.filter(User.class_name == class_name)
    return query.order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    if current_user.role == UserRole.teacher and data.role != UserRole.student:
        raise HTTPException(status_code=403, detail="仅管理员可创建教师账号")
    if data.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能通过接口创建管理员")
    if data.role not in MANAGEABLE_ROLES:
        raise HTTPException(status_code=400, detail="不支持的角色")

    username = _clean_username(data.username)
    _ensure_unique_username(db, username)
    name = _clean_name(data.name, for_student=data.role == UserRole.student)
    password = _resolve_password(data.password, required=data.role != UserRole.student)

    if data.role == UserRole.student:
        class_name = (data.class_name or "").strip() or DEFAULT_STUDENT_CLASS
        ensure_class_access(current_user, class_name)
        _ensure_student_identity(db, name, class_name)
        assigned_classes: list[str] = []
    else:
        class_name = ""
        assigned_classes = _clean_class_list(data.assigned_classes)

    user = User(
        username=username,
        password_hash=get_password_hash(password),
        name=name,
        role=data.role,
        class_name=class_name,
        assigned_classes=assigned_classes,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_manage_user(current_user, user)

    original_role = user.role
    original_active = bool(user.is_active)
    new_role = original_role

    if data.role is not None and data.role != original_role:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="仅管理员可修改角色")
        if data.role == UserRole.admin:
            raise HTTPException(status_code=400, detail="不能将账号设为管理员")
        if original_role == UserRole.admin or user.id == current_user.id:
            raise HTTPException(status_code=400, detail="不能修改管理员角色")
        if data.role not in MANAGEABLE_ROLES:
            raise HTTPException(status_code=400, detail="不支持的角色")
        new_role = data.role

    if data.username is not None:
        username = _clean_username(data.username)
        if username != user.username:
            if current_user.role != UserRole.admin:
                raise HTTPException(status_code=403, detail="仅管理员可修改用户名")
            _ensure_unique_username(db, username, exclude_id=user.id)
            user.username = username

    if data.name is not None or (new_role == UserRole.student and original_role != UserRole.student):
        user.name = _clean_name(data.name if data.name is not None else user.name, for_student=new_role == UserRole.student)

    if new_role == UserRole.student:
        if data.class_name is not None or original_role != UserRole.student:
            raw_class = data.class_name if data.class_name is not None else user.class_name
            class_name = (raw_class or "").strip() or DEFAULT_STUDENT_CLASS
            ensure_class_access(current_user, class_name)
            user.class_name = class_name
        user.assigned_classes = []
    elif new_role == UserRole.teacher:
        if current_user.role == UserRole.admin and (
            data.assigned_classes is not None or original_role != UserRole.teacher
        ):
            source = data.assigned_classes if data.assigned_classes is not None else (user.assigned_classes or [])
            user.assigned_classes = _clean_class_list(source)
        user.class_name = ""

    user.role = new_role

    if data.password:
        password = _resolve_password(data.password, required=True)
        user.password_hash = get_password_hash(password)

    if data.is_active is not None and data.is_active != user.is_active:
        if data.is_active is False:
            if user.id == current_user.id:
                raise HTTPException(status_code=400, detail="不能禁用自己的账号")
            if user.role == UserRole.admin and _count_other_active_admins(db, user.id) == 0:
                raise HTTPException(status_code=400, detail="不能禁用最后一名管理员")
        user.is_active = data.is_active

    identity_touched = (
        data.name is not None
        or data.class_name is not None
        or new_role != original_role
        or (data.is_active is True and not original_active)
    )
    if user.role == UserRole.student and user.is_active and identity_touched:
        _ensure_student_identity(db, user.name, user.class_name or "", exclude_id=user.id)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == UserRole.admin:
        if _count_other_active_admins(db, user.id) == 0 and user.is_active:
            raise HTTPException(status_code=400, detail="不能删除最后一名管理员")
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    _ensure_manage_user(current_user, user)
    db.delete(user)
    db.commit()
    return {"message": "删除成功"}
