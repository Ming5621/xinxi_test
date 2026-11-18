"""权限与班级数据范围控制"""

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Query
from sqlalchemy.orm.attributes import flag_modified

from .models import SchoolClass, User, UserRole


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


def claim_class_for_teacher(db, user: User, class_name: str) -> str:
    """教师新建或认领班级，写入 assigned_classes 与 school_classes。管理员只规范化名称。"""
    class_name = (class_name or "").strip()
    if user.role == UserRole.admin:
        return class_name
    if user.role != UserRole.teacher:
        raise HTTPException(status_code=403, detail="无权管理班级")
    if not class_name:
        assigned = list(user.assigned_classes or [])
        return assigned[0] if assigned else "课堂"

    assigned = list(user.assigned_classes or [])
    if class_name not in assigned:
        assigned.append(class_name)
        user.assigned_classes = assigned
        flag_modified(user, "assigned_classes")

    exists = (
        db.query(SchoolClass)
        .filter(SchoolClass.teacher_id == user.id, SchoolClass.name == class_name)
        .first()
    )
    if not exists:
        db.add(SchoolClass(teacher_id=user.id, name=class_name))
        db.flush()
    return class_name


def student_in_scope(viewer: User, student: User | None) -> bool:
    """教师只能看到自己绑定的学生；未绑定的旧数据仍按班级共享。管理员可见全部。"""
    if student is None or student.role != UserRole.student:
        return False
    if viewer.role == UserRole.admin:
        return True
    if viewer.role != UserRole.teacher:
        return False
    if student.managed_by_teacher_id == viewer.id:
        return True
    if student.managed_by_teacher_id is None:
        return bool(student.class_name) and student.class_name in (viewer.assigned_classes or [])
    return False


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
    if classes is None:
        if class_name:
            return query.filter(UserModel.class_name == class_name)
        return query

    if not classes:
        return query.filter(False)

    if class_name:
        if class_name not in classes:
            raise HTTPException(status_code=403, detail="无权访问该班级数据")
        query = query.filter(UserModel.class_name == class_name)

    bound = UserModel.managed_by_teacher_id == user.id
    legacy = and_(UserModel.managed_by_teacher_id.is_(None), UserModel.class_name.in_(classes))
    return query.filter(or_(bound, legacy))


def list_accessible_classes(user: User, db) -> list[str]:
    from .models import User as UserModel

    names: list[str] = []
    seen: set[str] = set()

    def add(name: str | None) -> None:
        if name and name not in seen:
            seen.add(name)
            names.append(name)

    assigned = get_assigned_classes(user)
    if assigned is None:
        rows = (
            db.query(UserModel.class_name)
            .filter(UserModel.role == UserRole.student, UserModel.class_name != "")
            .distinct()
            .all()
        )
        for row in rows:
            add(row[0])
        owned = db.query(SchoolClass.name).distinct().all()
        for row in owned:
            add(row[0])
        return sorted(names)

    for name in assigned:
        add(name)
    owned = db.query(SchoolClass.name).filter(SchoolClass.teacher_id == user.id).all()
    for row in owned:
        add(row[0])
    return names


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
