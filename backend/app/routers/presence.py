from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_student, require_teacher
from ..database import get_db
from ..models import User, UserRole
from ..schemas import PresenceSummary, StudentPresenceOut

router = APIRouter(prefix="/api/presence", tags=["在线状态"])

ONLINE_THRESHOLD_SECONDS = 45


def _is_online(last_seen_at: datetime | None) -> bool:
    if not last_seen_at:
        return False
    return (datetime.utcnow() - last_seen_at).total_seconds() <= ONLINE_THRESHOLD_SECONDS


def _student_presence(user: User) -> StudentPresenceOut:
    return StudentPresenceOut(
        id=user.id,
        username=user.username,
        name=user.name,
        class_name=user.class_name,
        is_active=user.is_active,
        is_online=_is_online(user.last_seen_at),
        last_seen_at=user.last_seen_at,
    )


@router.post("/heartbeat")
def heartbeat(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    current_user.last_seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.get("/students", response_model=list[StudentPresenceOut])
def list_student_presence(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    students = (
        db.query(User)
        .filter(User.role == UserRole.student)
        .order_by(User.class_name, User.id)
        .all()
    )
    return [_student_presence(student) for student in students]


@router.get("/summary", response_model=PresenceSummary)
def presence_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    students = db.query(User).filter(User.role == UserRole.student, User.is_active == True).all()
    online = sum(1 for student in students if _is_online(student.last_seen_at))
    total = len(students)
    return PresenceSummary(
        total_students=total,
        online_students=online,
        offline_students=max(total - online, 0),
        online_threshold_seconds=ONLINE_THRESHOLD_SECONDS,
    )
