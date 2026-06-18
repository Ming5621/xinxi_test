from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..models import (
    Answer,
    Exam,
    ExamSession,
    ExamStatus,
    Question,
    QuestionType,
    SessionStatus,
    User,
)
from ..permissions import ensure_class_access, filter_class_name, get_assigned_classes
from ..typing_utils import compare_text, calculate_wpm, parse_typing_config, score_typing_question, get_typing_level
from ..schemas import (
    ExamCreate,
    ExamDetailOut,
    ExamOut,
    ExamSubmitRequest,
    ExamUpdate,
    QuestionOut,
    QuestionStudentOut,
    SessionDetailOut,
    SessionOut,
)

router = APIRouter(prefix="/api/exams", tags=["考试管理"])


def _exam_to_out(exam: Exam) -> ExamOut:
    total = sum(q.score for q in exam.questions)
    return ExamOut(
        id=exam.id,
        title=exam.title,
        description=exam.description,
        duration_minutes=exam.duration_minutes,
        pass_score=exam.pass_score,
        status=exam.status,
        start_time=exam.start_time,
        end_time=exam.end_time,
        created_at=exam.created_at,
        question_count=len(exam.questions),
        total_score=total,
    )


def _grade_session(session: ExamSession, db: Session):
    exam = session.exam
    total_score = 0.0
    max_score = sum(q.score for q in exam.questions)

    existing = {a.question_id: a for a in session.answers}
    for question in exam.questions:
        answer = existing.get(question.id)
        if not answer:
            continue

        if question.type == QuestionType.typing:
            meta = answer.answer_meta or {}
            wpm = meta.get("wpm", 0)
            accuracy = meta.get("accuracy", 0)
            config = parse_typing_config(question.options)
            score, passed, remark = score_typing_question(wpm, accuracy, question.score, config)
            answer.is_correct = passed
            answer.score = score
            answer.answer_meta = {**meta, "remark": remark, "level": get_typing_level(wpm)["level"]}
            total_score += score
        else:
            is_correct = answer.student_answer.strip().upper() == question.correct_answer.strip().upper()
            answer.is_correct = is_correct
            answer.score = question.score if is_correct else 0.0
            total_score += answer.score

    session.total_score = total_score
    session.max_score = max_score
    session.status = SessionStatus.submitted
    session.submit_time = datetime.utcnow()
    db.commit()


@router.get("", response_model=list[ExamOut])
def list_exams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Exam)
    if current_user.role.value == "student":
        query = query.filter(Exam.status.in_([ExamStatus.published, ExamStatus.ended]))
    return [_exam_to_out(e) for e in query.order_by(Exam.id.desc()).all()]


@router.post("", response_model=ExamDetailOut)
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    exam = Exam(
        title=data.title,
        description=data.description,
        duration_minutes=data.duration_minutes,
        pass_score=data.pass_score,
        created_by=current_user.id,
    )
    db.add(exam)
    db.flush()

    for i, q in enumerate(data.questions):
        question = Question(
            exam_id=exam.id,
            type=q.type,
            content=q.content,
            options=q.options,
            correct_answer=q.correct_answer,
            score=q.score,
            order_num=q.order_num or i,
        )
        db.add(question)

    db.commit()
    db.refresh(exam)
    out = _exam_to_out(exam)
    return ExamDetailOut(**out.model_dump(), questions=[QuestionOut.model_validate(q) for q in exam.questions])


@router.get("/{exam_id}", response_model=ExamDetailOut)
def get_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    out = _exam_to_out(exam)
    return ExamDetailOut(**out.model_dump(), questions=[QuestionOut.model_validate(q) for q in exam.questions])


@router.put("/{exam_id}", response_model=ExamDetailOut)
def update_exam(
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    if data.title is not None:
        exam.title = data.title
    if data.description is not None:
        exam.description = data.description
    if data.duration_minutes is not None:
        exam.duration_minutes = data.duration_minutes
    if data.pass_score is not None:
        exam.pass_score = data.pass_score
    if data.status is not None:
        exam.status = data.status
        if data.status == ExamStatus.published and not exam.start_time:
            exam.start_time = datetime.utcnow()
        if data.status == ExamStatus.ended and not exam.end_time:
            exam.end_time = datetime.utcnow()
    if data.start_time is not None:
        exam.start_time = data.start_time
    if data.end_time is not None:
        exam.end_time = data.end_time

    if data.questions is not None:
        db.query(Question).filter(Question.exam_id == exam_id).delete()
        for i, q in enumerate(data.questions):
            question = Question(
                exam_id=exam.id,
                type=q.type,
                content=q.content,
                options=q.options,
                correct_answer=q.correct_answer,
                score=q.score,
                order_num=q.order_num or i,
            )
            db.add(question)

    db.commit()
    db.refresh(exam)
    out = _exam_to_out(exam)
    return ExamDetailOut(**out.model_dump(), questions=[QuestionOut.model_validate(q) for q in exam.questions])


@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    db.delete(exam)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{exam_id}/publish")
def publish_exam(exam_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    if not exam.questions:
        raise HTTPException(status_code=400, detail="考试没有题目，无法发布")
    exam.status = ExamStatus.published
    exam.start_time = datetime.utcnow()
    db.commit()
    return {"message": "发布成功"}


@router.post("/{exam_id}/end")
def end_exam(exam_id: int, db: Session = Depends(get_db), _: User = Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    exam.status = ExamStatus.ended
    exam.end_time = datetime.utcnow()

    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.status == SessionStatus.in_progress)
        .all()
    )
    for session in sessions:
        _grade_session(session, db)

    db.commit()
    return {"message": "考试已结束"}


# Student exam flow
@router.post("/{exam_id}/start", response_model=SessionOut)
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    if exam.status != ExamStatus.published:
        raise HTTPException(status_code=400, detail="考试未开放")

    existing = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.student_id == current_user.id)
        .first()
    )
    if existing:
        if existing.status == SessionStatus.submitted:
            raise HTTPException(status_code=400, detail="您已提交过本次考试")
        return SessionOut(
            id=existing.id,
            exam_id=exam.id,
            exam_title=exam.title,
            student_id=current_user.id,
            student_name=current_user.name,
            class_name=current_user.class_name,
            status=existing.status,
            start_time=existing.start_time,
            submit_time=existing.submit_time,
            total_score=existing.total_score,
            max_score=existing.max_score,
            pass_score=exam.pass_score,
            is_passed=existing.total_score >= exam.pass_score,
        )

    session = ExamSession(
        exam_id=exam_id,
        student_id=current_user.id,
        max_score=sum(q.score for q in exam.questions),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut(
        id=session.id,
        exam_id=exam.id,
        exam_title=exam.title,
        student_id=current_user.id,
        student_name=current_user.name,
        class_name=current_user.class_name,
        status=session.status,
        start_time=session.start_time,
        submit_time=session.submit_time,
        total_score=session.total_score,
        max_score=session.max_score,
        pass_score=exam.pass_score,
        is_passed=False,
    )


@router.get("/{exam_id}/questions", response_model=list[QuestionStudentOut])
def get_exam_questions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")
    if exam.status != ExamStatus.published:
        raise HTTPException(status_code=400, detail="考试未开放")

    session = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.student_id == current_user.id)
        .first()
    )
    if not session or session.status == SessionStatus.submitted:
        raise HTTPException(status_code=400, detail="请先开始考试")

    result = []
    for q in exam.questions:
        item = QuestionStudentOut.model_validate(q)
        if q.type == QuestionType.typing:
            item.typing_config = parse_typing_config(q.options)
        result.append(item)
    return result


@router.post("/{exam_id}/submit", response_model=SessionOut)
def submit_exam(
    exam_id: int,
    data: ExamSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    session = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.student_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=400, detail="请先开始考试")
    if session.status == SessionStatus.submitted:
        raise HTTPException(status_code=400, detail="已提交，不能重复提交")

    db.query(Answer).filter(Answer.session_id == session.id).delete()
    question_map = {q.id: q for q in exam.questions}
    for item in data.answers:
        if item.question_id not in question_map:
            continue
        question = question_map[item.question_id]
        meta = item.answer_meta or {}

        if question.type == QuestionType.typing:
            comparison = compare_text(question.content, item.student_answer)
            duration = meta.get("duration_seconds") or max(30, len(item.student_answer))
            meta = {
                **meta,
                "wpm": calculate_wpm(comparison["correct_chars"], duration),
                "accuracy": comparison["accuracy"],
                "correct_chars": comparison["correct_chars"],
                "duration_seconds": duration,
            }

        answer = Answer(
            session_id=session.id,
            question_id=item.question_id,
            student_answer=item.student_answer,
            answer_meta=meta,
        )
        db.add(answer)

    db.flush()
    _grade_session(session, db)
    db.refresh(session)

    return SessionOut(
        id=session.id,
        exam_id=exam.id,
        exam_title=exam.title,
        student_id=current_user.id,
        student_name=current_user.name,
        class_name=current_user.class_name,
        status=session.status,
        start_time=session.start_time,
        submit_time=session.submit_time,
        total_score=session.total_score,
        max_score=session.max_score,
        pass_score=exam.pass_score,
        is_passed=session.total_score >= exam.pass_score,
    )


@router.get("/sessions/my", response_model=list[SessionOut])
def my_sessions(db: Session = Depends(get_db), current_user: User = Depends(require_student)):
    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.student_id == current_user.id)
        .order_by(ExamSession.id.desc())
        .all()
    )
    result = []
    for s in sessions:
        exam = s.exam
        result.append(
            SessionOut(
                id=s.id,
                exam_id=s.exam_id,
                exam_title=exam.title,
                student_id=current_user.id,
                student_name=current_user.name,
                class_name=current_user.class_name,
                status=s.status,
                start_time=s.start_time,
                submit_time=s.submit_time,
                total_score=s.total_score,
                max_score=s.max_score,
                pass_score=exam.pass_score,
                is_passed=s.total_score >= exam.pass_score if s.status == SessionStatus.submitted else False,
            )
        )
    return result


@router.get("/sessions/{session_id}", response_model=SessionDetailOut)
def get_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="记录不存在")

    if current_user.role.value == "student" and session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看")

    exam = session.exam
    student = session.student
    answers_out = []
    for ans in session.answers:
        q = ans.question
        answers_out.append(
            {
                "question_id": ans.question_id,
                "student_answer": ans.student_answer,
                "is_correct": ans.is_correct,
                "score": ans.score,
                "correct_answer": q.correct_answer if session.status == SessionStatus.submitted and q.type != QuestionType.typing else None,
                "question_content": q.content,
                "answer_meta": ans.answer_meta,
            }
        )

    return SessionDetailOut(
        id=session.id,
        exam_id=session.exam_id,
        exam_title=exam.title,
        student_id=student.id,
        student_name=student.name,
        class_name=student.class_name,
        status=session.status,
        start_time=session.start_time,
        submit_time=session.submit_time,
        total_score=session.total_score,
        max_score=session.max_score,
        pass_score=exam.pass_score,
        is_passed=session.total_score >= exam.pass_score,
        answers=answers_out,
    )


@router.get("/{exam_id}/sessions", response_model=list[SessionOut])
def list_exam_sessions(
    exam_id: int,
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id).all()
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    classes = get_assigned_classes(current_user)
    result = []
    for s in sessions:
        student = s.student
        if not student:
            continue
        if classes is not None and student.class_name not in classes:
            continue
        if class_name and student.class_name != class_name:
            continue
        result.append(
            SessionOut(
                id=s.id,
                exam_id=s.exam_id,
                exam_title=exam.title,
                student_id=student.id,
                student_name=student.name,
                class_name=student.class_name,
                status=s.status,
                start_time=s.start_time,
                submit_time=s.submit_time,
                total_score=s.total_score,
                max_score=s.max_score,
                pass_score=exam.pass_score,
                is_passed=s.total_score >= exam.pass_score if s.status == SessionStatus.submitted else False,
            )
        )
    return result
