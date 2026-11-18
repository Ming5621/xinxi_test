from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import get_db
from ..models import User, UserRole
from ..permissions import claim_class_for_teacher, list_accessible_classes

router = APIRouter(prefix="/api/classes", tags=["班级"])


class ClassCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


@router.get("")
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    return {"classes": list_accessible_classes(current_user, db)}


@router.post("")
def create_class(
    data: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    name = (data.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="班级名称不能为空")
    if current_user.role == UserRole.admin:
        claim_class_for_teacher(db, current_user, name)
        db.commit()
        return {"classes": list_accessible_classes(current_user, db), "name": name}

    assigned = list(current_user.assigned_classes or [])
    if name in assigned:
        return {"classes": list_accessible_classes(current_user, db), "name": name}

    claim_class_for_teacher(db, current_user, name)
    db.commit()
    db.refresh(current_user)
    return {"classes": list_accessible_classes(current_user, db), "name": name}
