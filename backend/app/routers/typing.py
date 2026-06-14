from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import TypingDifficulty, TypingRecord, TypingText, User, UserRole
from ..schemas import (
    TypingRecordOut,
    TypingResultOut,
    TypingStandardsOut,
    TypingSubmitRequest,
    TypingTextCreate,
    TypingTextOut,
)
from ..typing_utils import (
    TYPING_LEVELS,
    compare_text,
    calculate_wpm,
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


@router.post("/submit", response_model=TypingResultOut)
def submit_typing(
    data: TypingSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    comparison = compare_text(data.reference_text, data.typed_text)
    wpm = calculate_wpm(comparison["correct_chars"], data.duration_seconds)
    level_info = get_typing_level(wpm)
    passed = wpm >= 10 and comparison["accuracy"] >= 95

    record = TypingRecord(
        student_id=current_user.id,
        text_id=data.text_id,
        source=data.source,
        reference_text=data.reference_text,
        typed_text=data.typed_text,
        duration_seconds=data.duration_seconds,
        wpm=wpm,
        accuracy=comparison["accuracy"],
        correct_chars=comparison["correct_chars"],
        level=level_info["level"],
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
    )


@router.get("/records/my", response_model=list[TypingRecordOut])
def my_records(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    records = (
        db.query(TypingRecord)
        .filter(TypingRecord.student_id == current_user.id)
        .order_by(TypingRecord.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for r in records:
        title = r.text.title if r.text else "自定义练习"
        result.append(
            TypingRecordOut(
                id=r.id,
                text_id=r.text_id,
                text_title=title,
                source=r.source,
                wpm=r.wpm,
                accuracy=r.accuracy,
                correct_chars=r.correct_chars,
                level=r.level,
                duration_seconds=r.duration_seconds,
                created_at=r.created_at,
            )
        )
    return result


@router.get("/records/stats")
def class_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    students = db.query(User).filter(User.role == UserRole.student).all()
    stats = []
    for s in students:
        records = (
            db.query(TypingRecord)
            .filter(TypingRecord.student_id == s.id, TypingRecord.source == "practice")
            .order_by(TypingRecord.id.desc())
            .limit(10)
            .all()
        )
        if records:
            avg_wpm = round(sum(r.wpm for r in records) / len(records), 1)
            best_wpm = max(r.wpm for r in records)
            avg_acc = round(sum(r.accuracy for r in records) / len(records), 1)
            latest_level = records[0].level
        else:
            avg_wpm = best_wpm = avg_acc = 0
            latest_level = "—"
        stats.append({
            "student_id": s.id,
            "student_name": s.name,
            "class_name": s.class_name,
            "practice_count": len(records),
            "avg_wpm": avg_wpm,
            "best_wpm": best_wpm,
            "avg_accuracy": avg_acc,
            "latest_level": latest_level,
        })
    return stats
