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
    UserRole,
)
from ..permissions import ensure_owns_exam, filter_class_name, student_can_access_exam, student_in_scope
from ..import_utils import normalize_answer
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

SUBMIT_GRACE_SECONDS = 30

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
        has_sessions=bool(exam.sessions),
    )


def _grade_session(session: ExamSession, db: Session):
    exam = session.exam
    total_score = 0.0
    max_score = sum(q.score for q in exam.questions)

    existing = {a.question_id: a for a in session.answers}
    for question in exam.questions:
        answer = existing.get(question.id)
        if not answer:
            answer = Answer(session_id=session.id, question_id=question.id, student_answer="", is_correct=False, score=0)
            db.add(answer)
            continue
        if not answer.student_answer.strip():
            answer.is_correct = False
            answer.score = 0
            continue

        if question.type == QuestionType.typing:
            meta = answer.answer_meta or {}
            wpm = meta.get("wpm", 0)
            accuracy = meta.get("accuracy", 0)
            config = parse_typing_config(question.options)
            score, passed, remark = score_typing_question(wpm, accuracy, question.score, config)
            answer.is_correct = passed
            answer.score = score
            min_accuracy = float(config.get("min_accuracy", 95))
            level_name = get_typing_level(float(wpm or 0), float(accuracy or 0), min_accuracy)["level"]
            answer.answer_meta = {**meta, "remark": remark, "level": level_name}
            total_score += score
        else:
            student_ans = normalize_answer(answer.student_answer, question.type)
            correct_ans = normalize_answer(question.correct_answer, question.type)
            is_correct = student_ans.strip().upper() == correct_ans.strip().upper()
            answer.is_correct = is_correct
            answer.score = question.score if is_correct else 0.0
            total_score += answer.score

    session.total_score = total_score
    session.max_score = max_score
    session.status = SessionStatus.submitted
    session.submit_time = datetime.utcnow()


def _grade_in_progress_sessions(exam_id: int, db: Session):
    sessions = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.status == SessionStatus.in_progress)
        .all()
    )
    for session in sessions:
        _grade_session(session, db)


@router.get("", response_model=list[ExamOut])
def list_exams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Exam)
    if current_user.role == UserRole.teacher:
        query = query.filter(Exam.created_by == current_user.id)
    elif current_user.role == UserRole.student:
        if not current_user.managed_by_teacher_id:
            return []
        query = query.filter(
            Exam.created_by == current_user.managed_by_teacher_id,
            Exam.status.in_([ExamStatus.published, ExamStatus.ended]),
        )
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
    if current_user.role == UserRole.student:
        if not student_can_access_exam(current_user, exam) or exam.status not in (ExamStatus.published, ExamStatus.ended):
            raise HTTPException(status_code=404, detail="考试不存在")
    else:
        ensure_owns_exam(current_user, exam)
    out = _exam_to_out(exam)
    if current_user.role.value == "student":
        # 返回题目内容但不含标准答案，避免前端只读 get 接口时看不到题
        safe_questions = []
        for q in exam.questions:
            item = QuestionOut.model_validate(q)
            item.correct_answer = ""
            if q.type == QuestionType.typing:
                # 打字题 options 为配置对象，学生端用 content 作对照文
                pass
            safe_questions.append(item)
        return ExamDetailOut(**out.model_dump(), questions=safe_questions)
    return ExamDetailOut(**out.model_dump(), questions=[QuestionOut.model_validate(q) for q in exam.questions])


@router.put("/{exam_id}", response_model=ExamDetailOut)
def update_exam(
    exam_id: int,
    data: ExamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    ensure_owns_exam(current_user, exam)

    # 已有答卷引用题目 ID；替换题目会使历史答案错配或失去关联。
    if exam.sessions and (
        data.questions is not None
        or (data.duration_minutes is not None and data.duration_minutes != exam.duration_minutes)
        or (data.pass_score is not None and data.pass_score != exam.pass_score)
        or data.status == ExamStatus.draft
    ):
        raise HTTPException(status_code=400, detail="已有学生开始考试，不能修改题目、时长、及格分或退回草稿")
    final_questions = data.questions if data.questions is not None else exam.questions
    final_status = data.status if data.status is not None else exam.status
    if final_status == ExamStatus.published and not final_questions:
        raise HTTPException(status_code=400, detail="考试没有题目，无法发布")

    if data.title is not None:
        exam.title = data.title
    if data.description is not None:
        exam.description = data.description
    if data.duration_minutes is not None:
        exam.duration_minutes = data.duration_minutes
    if data.pass_score is not None:
        exam.pass_score = data.pass_score
    if data.status is not None:
        if data.status == ExamStatus.published:
            exam.status = ExamStatus.published
            if not exam.start_time:
                exam.start_time = datetime.utcnow()
        elif data.status == ExamStatus.ended:
            exam.status = ExamStatus.ended
            if not exam.end_time:
                exam.end_time = datetime.utcnow()
            _grade_in_progress_sessions(exam_id, db)
        else:
            exam.status = data.status
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
    current_user: User = Depends(require_teacher),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    ensure_owns_exam(current_user, exam)
    db.delete(exam)
    db.commit()
    return {"message": "删除成功"}


@router.post("/{exam_id}/publish")
def publish_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    ensure_owns_exam(current_user, exam)
    if not exam.questions:
        raise HTTPException(status_code=400, detail="考试没有题目，无法发布")
    exam.status = ExamStatus.published
    exam.start_time = datetime.utcnow()
    db.commit()
    return {"message": "发布成功"}


@router.post("/{exam_id}/end")
def end_exam(exam_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_teacher)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    ensure_owns_exam(current_user, exam)
    exam.status = ExamStatus.ended
    exam.end_time = datetime.utcnow()
    _grade_in_progress_sessions(exam_id, db)
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
    if not exam or not student_can_access_exam(current_user, exam):
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
    if not exam or not student_can_access_exam(current_user, exam):
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
    if not exam or not student_can_access_exam(current_user, exam):
        raise HTTPException(status_code=404, detail="考试不存在")

    if exam.status != ExamStatus.published:
        raise HTTPException(status_code=400, detail="考试未开放或已结束")

    session = (
        db.query(ExamSession)
        .filter(ExamSession.exam_id == exam_id, ExamSession.student_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=400, detail="请先开始考试")
    if session.status == SessionStatus.submitted:
        raise HTTPException(status_code=400, detail="已提交，不能重复提交")

    elapsed = (datetime.utcnow() - session.start_time).total_seconds()
    max_seconds = exam.duration_minutes * 60 + SUBMIT_GRACE_SECONDS
    if elapsed > max_seconds:
        raise HTTPException(status_code=400, detail="考试时间已结束")

    db.query(Answer).filter(Answer.session_id == session.id).delete()
    question_map = {q.id: q for q in exam.questions}
    answers_by_qid = {}
    for item in data.answers:
        if item.question_id not in question_map:
            continue
        answers_by_qid[item.question_id] = item

    exam_elapsed = elapsed
    for qid, item in answers_by_qid.items():
        question = question_map[qid]
        meta = item.answer_meta or {}

        if question.type == QuestionType.typing:
            comparison = compare_text(question.content, item.student_answer)
            config = parse_typing_config(question.options)
            time_limit = config.get("time_limit", 120)
            client_duration = meta.get("duration_seconds")
            if client_duration:
                duration = min(max(float(client_duration), 5), time_limit, exam_elapsed)
            else:
                duration = min(max(30, len(item.student_answer)), time_limit, exam_elapsed)
            meta = {
                **meta,
                "wpm": calculate_wpm(comparison["correct_chars"], duration),
                "accuracy": comparison["accuracy"],
                "correct_chars": comparison["correct_chars"],
                "duration_seconds": duration,
            }

        answer = Answer(
            session_id=session.id,
            question_id=qid,
            student_answer=item.student_answer,
            answer_meta=meta,
        )
        db.add(answer)

    db.flush()
    _grade_session(session, db)
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

    student = session.student
    if student is None:
        raise HTTPException(status_code=404, detail="学生账号不存在")
    if current_user.role.value == "teacher" and not student_in_scope(current_user, student):
        raise HTTPException(status_code=403, detail="无权查看该学生成绩")

    exam = session.exam
    answers_out = []
    for ans in session.answers:
        q = ans.question
        meta = ans.answer_meta
        if q.type == QuestionType.typing and meta:
            config = parse_typing_config(q.options)
            wpm = float(meta.get("wpm") or 0)
            accuracy = float(meta.get("accuracy") or 0)
            min_accuracy = float(config.get("min_accuracy", 95))
            _, _, remark = score_typing_question(wpm, accuracy, q.score, config)
            meta = {
                **meta,
                "level": get_typing_level(wpm, accuracy, min_accuracy)["level"],
                "remark": remark,
            }
        answers_out.append(
            {
                "question_id": ans.question_id,
                "student_answer": ans.student_answer,
                "is_correct": ans.is_correct,
                "score": ans.score,
                "correct_answer": q.correct_answer if session.status == SessionStatus.submitted and q.type != QuestionType.typing else None,
                "question_content": q.content,
                "answer_meta": meta,
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
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    ensure_owns_exam(current_user, exam)
    sessions = db.query(ExamSession).filter(ExamSession.exam_id == exam_id).all()
    result = []
    for s in sessions:
        student = s.student
        if not student or not student_in_scope(current_user, student):
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
