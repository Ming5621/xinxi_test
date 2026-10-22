"""权限与班级数据范围控制"""

from fastapi import HTTPException
from sqlalchemy.orm import Query

from .models import User, UserRole


def is_admin(user: User) -> bool:
    return user.role == UserRole.admin


def is_teacher_or_admin(user: User) -> bool:
    return user.role in (UserRole.teacher, UserRole.admin)


def get_assigned_classes(user: User) -> list[str] | None:
    """管理员返回 None 表示全部班级；教师返回分配的班级列表。"""
    if user.role == UserRole.admin:
        return None
    if user.role == UserRole.teacher:
        return list(user.assigned_classes or [])
    return []


def ensure_class_access(user: User, class_name: str) -> None:
    classes = get_assigned_classes(user)
    if classes is None:
        return
    if class_name not in classes:
        raise HTTPException(status_code=403, detail="无权访问该班级数据")


def filter_class_name(user: User, class_name: str | None) -> str | None:
    """教师只能查自己班级；若指定了无权限班级则拒绝。"""
    classes = get_assigned_classes(user)
    if classes is None:
        return class_name
    if not classes:
        raise HTTPException(status_code=403, detail="未分配管理班级")
    if class_name:
        if class_name not in classes:
            raise HTTPException(status_code=403, detail="无权访问该班级数据")
        return class_name
    return None


def apply_student_scope(query: Query, user: User, class_name: str | None = None) -> Query:
    from .models import User as UserModel

    query = query.filter(UserModel.role == UserRole.student)
    classes = get_assigned_classes(user)
    if classes is not None:
        if not classes:
            return query.filter(False)
        if class_name:
            if class_name not in classes:
                raise HTTPException(status_code=403, detail="无权访问该班级数据")
            return query.filter(UserModel.class_name == class_name)
        return query.filter(UserModel.class_name.in_(classes))
    if class_name:
        return query.filter(UserModel.class_name == class_name)
    return query


def list_accessible_classes(user: User, db) -> list[str]:
    from .models import User as UserModel

    q = db.query(UserModel.class_name).filter(
        UserModel.role == UserRole.student,
        UserModel.class_name != "",
    )
    classes = get_assigned_classes(user)
    if classes is not None:
        if not classes:
            return []
        q = q.filter(UserModel.class_name.in_(classes))
    rows = q.distinct().order_by(UserModel.class_name).all()
    return [r[0] for r in rows if r[0]]


def teacher_ids_for_class(db, class_name: str) -> list[int]:
    """返回管理该班级的教师 ID 列表（按 assigned_classes 匹配）。"""
    from .models import User as UserModel

    if not class_name:
        return []
    teachers = (
        db.query(UserModel)
        .filter(UserModel.role == UserRole.teacher, UserModel.is_active == True)
        .all()
    )
    return [t.id for t in teachers if class_name in (t.assigned_classes or [])]


def active_student_name_taken(db, name: str, class_name: str, exclude_id: int | None = None) -> bool:
    """同一班级的在读学生姓名必须唯一，否则姓名登录无法区分。"""
    query = db.query(User).filter(
        User.role == UserRole.student,
        User.name == name,
        User.class_name == class_name,
        User.is_active == True,  # noqa: E712
    )
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    return query.first() is not None


def can_manage_typing_text(user: User, text) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role == UserRole.teacher and text.teacher_id == user.id:
        return True
    return False
