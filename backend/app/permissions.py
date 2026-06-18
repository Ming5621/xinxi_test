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
