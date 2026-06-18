from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..auth import require_teacher
from ..database import get_db
from ..models import Exam, ExamSession, SessionStatus, User, UserRole
from ..permissions import apply_student_scope, filter_class_name, get_assigned_classes
from ..schemas import ClassExamStat, DashboardStats, ExamStatistics, QuestionStat

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
def dashboard_stats(db: Session = Depends(get_db), current_user: User = Depends(require_teacher)):
    from ..models import ExamStatus

    student_q = db.query(User).filter(User.role == UserRole.student)
    student_q = apply_student_scope(student_q, current_user)

    online_q = student_q.filter(
        User.is_active == True,
        User.last_seen_at.isnot(None),
        User.last_seen_at >= datetime.utcnow() - timedelta(seconds=ONLINE_THRESHOLD_SECONDS),
    )

    return DashboardStats(
        total_students=student_q.count(),
        online_students=online_q.count(),
        total_exams=db.query(Exam).count(),
        active_exams=db.query(Exam).filter(Exam.status == ExamStatus.published).count(),
        completed_sessions=db.query(ExamSession).filter(ExamSession.status == SessionStatus.submitted).count(),
    )


@router.get("/exam/{exam_id}", response_model=ExamStatistics)
def exam_statistics(
    exam_id: int,
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    sessions = (
        db.query(ExamSession)
        .options(joinedload(ExamSession.student))
        .filter(ExamSession.exam_id == exam_id)
        .all()
    )
    classes = get_assigned_classes(current_user)
    filtered = []
    for s in sessions:
        stu = s.student
        if not stu:
            continue
        if classes is not None and stu.class_name not in classes:
            continue
        if class_name and stu.class_name != class_name:
            continue
        filtered.append(s)

    submitted = [s for s in filtered if s.status == SessionStatus.submitted]
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

    class_groups: dict[str, list] = {}
    for s in filtered:
        cn = s.student.class_name if s.student else "未分班"
        class_groups.setdefault(cn, []).append(s)

    class_stats = []
    for cn, group in sorted(class_groups.items()):
        sub = [s for s in group if s.status == SessionStatus.submitted]
        sub_scores = [s.total_score for s in sub]
        c_pass = sum(1 for s in sub if s.total_score >= exam.pass_score)
        class_stats.append(
            ClassExamStat(
                class_name=cn,
                student_count=len(group),
                submitted_count=len(sub),
                average_score=round(sum(sub_scores) / len(sub_scores), 1) if sub_scores else 0,
                pass_count=c_pass,
                pass_rate=round(c_pass / len(sub) * 100, 1) if sub else 0,
            )
        )

    return ExamStatistics(
        exam_id=exam.id,
        exam_title=exam.title,
        total_students=len(filtered),
        submitted_count=len(submitted),
        average_score=round(sum(scores) / len(scores), 1) if scores else 0,
        max_score=max(scores) if scores else 0,
        min_score=min(scores) if scores else 0,
        pass_count=pass_count,
        pass_rate=round(pass_count / len(submitted) * 100, 1) if submitted else 0,
        total_possible_score=total_possible,
        question_stats=question_stats,
        score_distribution=distribution,
        class_stats=class_stats,
    )
