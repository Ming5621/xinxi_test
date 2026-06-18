from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_password_hash, require_admin, require_teacher
from ..database import get_db
from ..models import User, UserRole
from ..permissions import apply_student_scope, ensure_class_access, filter_class_name
from ..schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["用户管理"])


def _ensure_manage_user(current_user: User, target: User) -> None:
    if current_user.role == UserRole.admin:
        return
    if target.role != UserRole.student:
        raise HTTPException(status_code=403, detail="仅管理员可管理教师账号")
    ensure_class_access(current_user, target.class_name)


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
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")

    if current_user.role == UserRole.teacher:
        if data.role != UserRole.student:
            raise HTTPException(status_code=403, detail="仅管理员可创建教师账号")
        ensure_class_access(current_user, data.class_name)

    if current_user.role == UserRole.admin and data.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能通过接口创建管理员")

    user = User(
        username=data.username,
        password_hash=get_password_hash(data.password),
        name=data.name,
        role=data.role,
        class_name=data.class_name if data.role == UserRole.student else "",
        assigned_classes=data.assigned_classes if data.role == UserRole.teacher else [],
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

    if data.name is not None:
        user.name = data.name
    if data.class_name is not None:
        if user.role == UserRole.student:
            ensure_class_access(current_user, data.class_name)
            user.class_name = data.class_name
    if data.assigned_classes is not None and current_user.role == UserRole.admin:
        if user.role == UserRole.teacher:
            user.assigned_classes = data.assigned_classes
    if data.password:
        user.password_hash = get_password_hash(data.password)
    if data.is_active is not None:
        user.is_active = data.is_active

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
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    _ensure_manage_user(current_user, user)
    db.delete(user)
    db.commit()
    return {"message": "删除成功"}
