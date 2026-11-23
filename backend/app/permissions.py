"""权限与班级数据范围控制"""

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Query

from .models import ClassCatalog, SchoolClass, TypingClassSession, TypingClassSessionStatus, User, UserRole
from .timeutil import utc_now

DEFAULT_STUDENT_CLASS = "课堂"


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


def resolve_student_class(user: User, class_name: str | None) -> str:
    class_name = (class_name or "").strip()
    assigned = get_assigned_classes(user)
    if len(class_name) > 100:
        raise HTTPException(status_code=400, detail="班级名称不能超过100个字符")
    if not class_name:
        class_name = assigned[0] if assigned else DEFAULT_STUDENT_CLASS
    ensure_class_access(user, class_name)
    return class_name


def remember_class(db, name: str) -> None:
    db.execute(insert(ClassCatalog).values(name=name).on_conflict_do_nothing())


def set_teacher_classes(db, teacher: User, names: list[str]) -> None:
    for name in set(teacher.assigned_classes or []) | set(names):
        remember_class(db, name)
    teacher.assigned_classes = names
    db.query(User).filter(
        User.role == UserRole.student,
        User.managed_by_teacher_id == teacher.id,
        ~User.class_name.in_(names),
    ).update({User.managed_by_teacher_id: None}, synchronize_session="fetch")
    db.query(TypingClassSession).filter(
        TypingClassSession.teacher_id == teacher.id,
        TypingClassSession.status == TypingClassSessionStatus.active,
        ~TypingClassSession.class_name.in_(names),
    ).update({
        TypingClassSession.status: TypingClassSessionStatus.ended,
        TypingClassSession.ended_at: utc_now(),
    }, synchronize_session="fetch")


def teacher_can_manage_class(teacher: User | None, class_name: str) -> bool:
    return bool(
        teacher and teacher.role == UserRole.teacher and teacher.is_active
        and class_name in (teacher.assigned_classes or [])
    )


def validate_student_teacher(teacher: User | None, class_name: str) -> None:
    if not teacher_can_manage_class(teacher, class_name):
        raise HTTPException(status_code=400, detail=f"请选择已分配到「{class_name}」的启用教师账号")


def student_in_scope(viewer: User, student: User | None) -> bool:
    """教师只能看到自己绑定的学生；未绑定的旧数据仍按班级共享。管理员可见全部。"""
    if student is None or student.role != UserRole.student:
        return False
    if viewer.role == UserRole.admin:
        return True
    if viewer.role != UserRole.teacher:
        return False
    return (
        student.class_name in (viewer.assigned_classes or [])
        and student.managed_by_teacher_id in (None, viewer.id)
    )


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

    return query.filter(
        UserModel.class_name.in_(classes),
        or_(UserModel.managed_by_teacher_id == user.id, UserModel.managed_by_teacher_id.is_(None)),
    )


def list_accessible_classes(user: User, db) -> list[str]:
    assigned = get_assigned_classes(user)
    if assigned is not None:
        return assigned
    return list_all_classes(db)


def list_all_classes(db) -> list[str]:
    names = {name for name, in db.query(ClassCatalog.name)}
    names.update(name for name, in db.query(SchoolClass.name).distinct())
    names.update(name for name, in db.query(User.class_name).filter(User.role == UserRole.student).distinct())
    for classes, in db.query(User.assigned_classes).filter(User.role == UserRole.teacher):
        names.update(classes or [])
    return sorted(name for name in names if name)


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
