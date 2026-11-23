from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_admin, require_teacher
from ..database import get_db
from ..models import ClassCatalog, SchoolClass, TypingClassSession, TypingClassSessionStatus, User, UserRole
from ..permissions import list_accessible_classes, remember_class, set_teacher_classes
from ..timeutil import utc_now

router = APIRouter(prefix="/api/classes", tags=["班级"])


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    teacher_ids: list[int] | None = None


class ClassUpdate(ClassCreate):
    original_name: str


@router.get("")
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    return {"classes": list_accessible_classes(current_user, db)}


def _save_class(data: ClassCreate, db: Session, current_user: User, original_name: str | None = None):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="班级名称不能为空")

    names = list_accessible_classes(current_user, db)
    if original_name is not None and original_name not in names:
        raise HTTPException(status_code=404, detail="班级不存在")
    if name != original_name and name in names:
        raise HTTPException(status_code=400, detail="班级名称已存在")

    teachers = {u.id: u for u in db.query(User).filter(User.role == UserRole.teacher)}
    if data.teacher_ids is None:
        selected = {t.id for t in teachers.values() if original_name in (t.assigned_classes or [])}
    else:
        selected = set(data.teacher_ids)
    if selected.difference(teachers):
        raise HTTPException(status_code=400, detail="所选教师账号不存在")

    if name != original_name and original_name is not None:
        db.query(ClassCatalog).filter_by(name=original_name).delete()
        db.query(SchoolClass).filter_by(name=original_name).update({SchoolClass.name: name})
        db.query(User).filter_by(role=UserRole.student, class_name=original_name).update({User.class_name: name})
        db.query(TypingClassSession).filter_by(class_name=original_name).update({TypingClassSession.class_name: name})

    remember_class(db, name)
    for teacher in teachers.values():
        previous = teacher.assigned_classes or []
        classes = [name if c == original_name else c for c in previous]
        if teacher.id in selected and name not in classes:
            classes.append(name)
        if teacher.id not in selected and name in classes:
            classes.remove(name)
        if classes != previous:
            # A retained teacher's old class name was renamed, not removed.
            teacher.assigned_classes = [name if c == original_name else c for c in previous]
            set_teacher_classes(db, teacher, classes)
    db.commit()
    return {"classes": list_accessible_classes(current_user, db), "name": name}


@router.post("")
def create_class(
    data: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return _save_class(data, db, current_user)


@router.put("")
def update_class(
    data: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return _save_class(data, db, current_user, data.original_name)


@router.delete("")
def delete_class(
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if name not in list_accessible_classes(current_user, db):
        raise HTTPException(status_code=404, detail="班级不存在")

    for teacher in db.query(User).filter(User.role == UserRole.teacher):
        if name in (teacher.assigned_classes or []):
            teacher.assigned_classes = [item for item in teacher.assigned_classes if item != name]

    db.query(User).filter_by(role=UserRole.student, class_name=name).update({
        User.class_name: "",
        User.managed_by_teacher_id: None,
    })
    db.query(TypingClassSession).filter(
        TypingClassSession.class_name == name,
        TypingClassSession.status != TypingClassSessionStatus.ended,
    ).update({
        TypingClassSession.status: TypingClassSessionStatus.ended,
        TypingClassSession.ended_at: utc_now(),
    })
    db.query(SchoolClass).filter_by(name=name).delete()
    db.query(ClassCatalog).filter_by(name=name).delete()
    db.commit()
    return {"message": "班级已删除"}
