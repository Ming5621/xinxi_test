from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_teacher
from ..database import get_db
from ..models import Exam, ExamSession, SessionStatus, User, UserRole
from ..schemas import DashboardStats, ExamStatistics, QuestionStat

router = APIRouter(prefix="/api/stats", tags=["统计分析"])

ONLINE_THRESHOLD_SECONDS = 45


def _count_online_students(db: Session) -> int:
    cutoff = datetime.utcnow() - timedelta(seconds=ONLINE_THRESHOLD_SECONDS)
    return (
        db.query(User)
        .filter(
            User.role == UserRole.student,
            User.is_active == True,
            User.last_seen_at.isnot(None),
            User.last_seen_at >= cutoff,
        )
        .count()
    )


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_stats(db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    from ..models import ExamStatus

    return DashboardStats(
        total_students=db.query(User).filter(User.role == UserRole.student).count(),
        online_students=_count_online_students(db),
        total_exams=db.query(Exam).count(),
        active_exams=db.query(Exam).filter(Exam.status == ExamStatus.published).count(),
        completed_sessions=db.query(ExamSession).filter(ExamSession.status == SessionStatus.submitted).count(),
    )


@router.get("/exam/{exam_id}", response_model=ExamStatistics)
def exam_statistics(exam_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id).all()
    submitted = [s for s in sessions if s.status == SessionStatus.submitted]
    scores = [s.total_score for s in submitted]
    total_possible = sum(q.score for q in exam.questions)
    pass_count = sum(1 for s in submitted if s.total_score >= exam.pass_score)

    question_stats = []
    for q in exam.questions:
        correct = 0
        total = 0
        for s in submitted:
            for ans in s.answers:
                if ans.question_id == q.id:
                    total += 1
                    if ans.is_correct:
                        correct += 1
        rate = (correct / total * 100) if total > 0 else 0
        question_stats.append(
            QuestionStat(
                question_id=q.id,
                content=q.content[:80] + ("..." if len(q.content) > 80 else ""),
                type=q.type,
                correct_count=correct,
                total_count=total,
                correct_rate=round(rate, 1),
            )
        )

    distribution = {"0-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
    for score in scores:
        if total_possible > 0:
            pct = score / total_possible * 100
        else:
            pct = 0
        if pct < 60:
            distribution["0-59"] += 1
        elif pct < 70:
            distribution["60-69"] += 1
        elif pct < 80:
            distribution["70-79"] += 1
        elif pct < 90:
            distribution["80-89"] += 1
        else:
            distribution["90-100"] += 1

    return ExamStatistics(
        exam_id=exam.id,
        exam_title=exam.title,
        total_students=len(sessions),
        submitted_count=len(submitted),
        average_score=round(sum(scores) / len(scores), 1) if scores else 0,
        max_score=max(scores) if scores else 0,
        min_score=min(scores) if scores else 0,
        pass_count=pass_count,
        pass_rate=round(pass_count / len(submitted) * 100, 1) if submitted else 0,
        total_possible_score=total_possible,
        question_stats=question_stats,
        score_distribution=distribution,
    )
