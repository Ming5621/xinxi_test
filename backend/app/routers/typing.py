from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import (
    TypingClassSession,
    TypingClassSessionStatus,
    TypingDifficulty,
    TypingRecord,
    TypingText,
    User,
    UserRole,
)
from ..permissions import ensure_class_access, filter_class_name, get_assigned_classes
from ..schemas import (
    TypingClassSessionCreate,
    TypingClassSessionDetail,
    TypingClassSessionOut,
    TypingRecordOut,
    TypingResultOut,
    TypingStandardsOut,
    TypingSubmitRequest,
    TypingTextCreate,
    TypingTextOut,
)
from ..typing_utils import (
    DEFAULT_TYPING_CONFIG,
    TYPING_LEVELS,
    calculate_wpm,
    compare_text,
    get_typing_level,
    score_typing_question,
)

router = APIRouter(prefix="/api/typing", tags=["打字练习"])


@router.get("/standards", response_model=TypingStandardsOut)
def get_standards():
    return TypingStandardsOut(
        levels=TYPING_LEVELS,
        min_accuracy=95,
        description="参考中考信息技术（10字/分）及义务教育信息科技课标（30字/分、准确率95%）",
    )


@router.get("/texts", response_model=list[TypingTextOut])
def list_texts(
    difficulty: TypingDifficulty | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TypingText).filter(TypingText.is_active == True)
    if difficulty:
        query = query.filter(TypingText.difficulty == difficulty)
    return query.order_by(TypingText.id).all()


@router.post("/texts", response_model=TypingTextOut)
def create_text(
    data: TypingTextCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    text = TypingText(
        title=data.title,
        content=data.content.strip(),
        difficulty=data.difficulty,
        char_count=len(data.content.strip()),
        time_limit=data.time_limit,
    )
    db.add(text)
    db.commit()
    db.refresh(text)
    return text


@router.delete("/texts/{text_id}")
def delete_text(
    text_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    text = db.query(TypingText).filter(TypingText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="素材不存在")
    text.is_active = False
    db.commit()
    return {"message": "已删除"}


def _session_to_out(session: TypingClassSession, db: Session) -> TypingClassSessionOut:
    participant_count = (
        db.query(User)
        .filter(User.role == UserRole.student, User.class_name == session.class_name, User.is_active == True)
        .count()
    )
    submitted_count = (
        db.query(TypingRecord).filter(TypingRecord.typing_session_id == session.id).count()
    )
    return TypingClassSessionOut(
        id=session.id,
        teacher_id=session.teacher_id,
        teacher_name=session.teacher.name if session.teacher else "",
        text_id=session.text_id,
        text_title=session.text.title if session.text else "",
        class_name=session.class_name,
        title=session.title or (session.text.title if session.text else "课堂打字测试"),
        status=session.status,
        duration_seconds=session.duration_seconds,
        started_at=session.started_at,
        ended_at=session.ended_at,
        created_at=session.created_at,
        participant_count=participant_count,
        submitted_count=submitted_count,
    )


@router.get("/sessions", response_model=list[TypingClassSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    query = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .order_by(TypingClassSession.id.desc())
    )
    classes = get_assigned_classes(current_user)
    if classes is not None:
        if not classes:
            return []
        query = query.filter(TypingClassSession.class_name.in_(classes))
    sessions = query.limit(50).all()
    return [_session_to_out(s, db) for s in sessions]


@router.get("/sessions/active", response_model=TypingClassSessionOut | None)
def active_session_for_student(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(
            TypingClassSession.class_name == current_user.class_name,
            TypingClassSession.status == TypingClassSessionStatus.active,
        )
        .order_by(TypingClassSession.id.desc())
        .first()
    )
    if not session:
        return None
    return _session_to_out(session, db)


@router.get("/sessions/{session_id}", response_model=TypingClassSessionDetail)
def session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    if current_user.role == UserRole.student:
        if session.class_name != current_user.class_name:
            raise HTTPException(status_code=403, detail="无权查看")
    else:
        ensure_class_access(current_user, session.class_name)

    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .filter(TypingRecord.typing_session_id == session_id)
        .order_by(TypingRecord.score.desc())
        .all()
    )
    out = _session_to_out(session, db)
    return TypingClassSessionDetail(**out.model_dump(), records=[_record_to_out(r) for r in records])


@router.post("/sessions", response_model=TypingClassSessionOut)
def create_session(
    data: TypingClassSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    ensure_class_access(current_user, data.class_name)
    text = db.query(TypingText).filter(TypingText.id == data.text_id, TypingText.is_active == True).first()
    if not text:
        raise HTTPException(status_code=404, detail="文章不存在")
    active = (
        db.query(TypingClassSession)
        .filter(
            TypingClassSession.class_name == data.class_name,
            TypingClassSession.status == TypingClassSessionStatus.active,
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="该班级已有进行中的打字测试")

    session = TypingClassSession(
        teacher_id=current_user.id,
        text_id=data.text_id,
        class_name=data.class_name,
        title=data.title or f"{data.class_name} · 5分钟打字测试",
        duration_seconds=data.duration_seconds,
        status=TypingClassSessionStatus.pending,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session.id)
        .first()
    )
    return _session_to_out(session, db)


@router.post("/sessions/{session_id}/start", response_model=TypingClassSessionOut)
def start_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    ensure_class_access(current_user, session.class_name)
    if session.status != TypingClassSessionStatus.pending:
        raise HTTPException(status_code=400, detail="测试状态不允许开始")
    session.status = TypingClassSessionStatus.active
    session.started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_out(session, db)


@router.post("/sessions/{session_id}/end", response_model=TypingClassSessionOut)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    ensure_class_access(current_user, session.class_name)
    if session.status != TypingClassSessionStatus.active:
        raise HTTPException(status_code=400, detail="测试未在进行中")
    session.status = TypingClassSessionStatus.ended
    session.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_out(session, db)


@router.post("/submit", response_model=TypingResultOut)
def submit_typing(
    data: TypingSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    typing_session = None
    source = data.source
    if data.typing_session_id:
        typing_session = db.query(TypingClassSession).filter(TypingClassSession.id == data.typing_session_id).first()
        if not typing_session:
            raise HTTPException(status_code=404, detail="课堂测试不存在")
        if typing_session.class_name != current_user.class_name:
            raise HTTPException(status_code=403, detail="无权参加该测试")
        if typing_session.status != TypingClassSessionStatus.active:
            raise HTTPException(status_code=400, detail="课堂测试未在进行中")
        existing = (
            db.query(TypingRecord)
            .filter(
                TypingRecord.typing_session_id == typing_session.id,
                TypingRecord.student_id == current_user.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="您已提交过本次测试")
        source = "class_test"

    comparison = compare_text(data.reference_text, data.typed_text)
    wpm = calculate_wpm(comparison["correct_chars"], data.duration_seconds)
    level_info = get_typing_level(wpm)
    score, passed, remark = score_typing_question(
        wpm, comparison["accuracy"], 100, DEFAULT_TYPING_CONFIG
    )

    record = TypingRecord(
        student_id=current_user.id,
        text_id=data.text_id,
        typing_session_id=typing_session.id if typing_session else None,
        source=source,
        reference_text=data.reference_text,
        typed_text=data.typed_text,
        duration_seconds=data.duration_seconds,
        wpm=wpm,
        accuracy=comparison["accuracy"],
        correct_chars=comparison["correct_chars"],
        level=level_info["level"],
        score=score,
    )
    db.add(record)
    db.commit()

    return TypingResultOut(
        wpm=wpm,
        accuracy=comparison["accuracy"],
        correct_chars=comparison["correct_chars"],
        error_chars=comparison["error_chars"],
        total_chars=comparison["total_chars"],
        level=level_info["level"],
        level_desc=level_info["desc"],
        passed=passed,
        score=score,
        remark=remark,
    )


def _record_to_out(record: TypingRecord) -> TypingRecordOut:
    title = record.text.title if record.text else "自定义练习"
    score = record.score
    if not score:
        score, _, _ = score_typing_question(record.wpm, record.accuracy, 100, DEFAULT_TYPING_CONFIG)
    return TypingRecordOut(
        id=record.id,
        student_id=record.student_id,
        student_name=record.student.name if record.student else "",
        class_name=record.student.class_name if record.student else "",
        text_id=record.text_id,
        text_title=title,
        source=record.source,
        wpm=record.wpm,
        accuracy=record.accuracy,
        correct_chars=record.correct_chars,
        level=record.level,
        duration_seconds=record.duration_seconds,
        score=score,
        created_at=record.created_at,
    )


@router.get("/records/my", response_model=list[TypingRecordOut])
def my_records(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .filter(TypingRecord.student_id == current_user.id)
        .order_by(TypingRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [_record_to_out(r) for r in records]


@router.get("/records", response_model=list[TypingRecordOut])
def list_records(
    student_id: int | None = None,
    class_name: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    query = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .order_by(TypingRecord.id.desc())
    )
    if student_id:
        query = query.filter(TypingRecord.student_id == student_id)
    elif class_name:
        query = query.join(User).filter(User.class_name == class_name)
    else:
        classes = get_assigned_classes(current_user)
        if classes is not None:
            query = query.join(User).filter(User.class_name.in_(classes))
    return [_record_to_out(r) for r in query.limit(limit).all()]


@router.get("/records/stats")
def class_stats(
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    q = db.query(User).filter(User.role == UserRole.student, User.is_active == True)
    classes = get_assigned_classes(current_user)
    if classes is not None:
        if class_name:
            q = q.filter(User.class_name == class_name)
        else:
            q = q.filter(User.class_name.in_(classes))
    elif class_name:
        q = q.filter(User.class_name == class_name)
    students = q.order_by(User.class_name, User.id).all()

    stats = []
    for s in students:
        records = (
            db.query(TypingRecord)
            .filter(TypingRecord.student_id == s.id)
            .order_by(TypingRecord.id.desc())
            .limit(20)
            .all()
        )
        if records:
            avg_wpm = round(sum(r.wpm for r in records) / len(records), 1)
            best_wpm = max(r.wpm for r in records)
            avg_acc = round(sum(r.accuracy for r in records) / len(records), 1)
            scores = [
                r.score if r.score else score_typing_question(r.wpm, r.accuracy, 100, DEFAULT_TYPING_CONFIG)[0]
                for r in records
            ]
            avg_score = round(sum(scores) / len(scores), 1)
            latest_level = records[0].level
            total_count = db.query(TypingRecord).filter(TypingRecord.student_id == s.id).count()
        else:
            avg_wpm = best_wpm = avg_acc = avg_score = 0
            latest_level = "—"
            total_count = 0
        stats.append({
            "student_id": s.id,
            "student_name": s.name,
            "class_name": s.class_name,
            "practice_count": total_count,
            "avg_wpm": avg_wpm,
            "best_wpm": best_wpm,
            "avg_accuracy": avg_acc,
            "avg_score": avg_score,
            "latest_level": latest_level,
        })
    return stats
