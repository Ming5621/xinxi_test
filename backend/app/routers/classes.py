from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import get_db
from ..models import User
from ..permissions import list_accessible_classes

router = APIRouter(prefix="/api/classes", tags=["班级"])


@router.get("")
def list_classes(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    return {"classes": list_accessible_classes(current_user, db)}
