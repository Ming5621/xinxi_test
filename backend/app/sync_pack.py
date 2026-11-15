"""教师机之间同步班级、学生、考试和打字素材。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from .auth import get_password_hash
from .models import Exam, Question, QuestionType, TypingDifficulty, TypingText, User, UserRole
from .permissions import (
    active_student_name_taken,
    apply_student_scope,
    claim_class_for_teacher,
)
from .timeutil import serialize_utc_datetime, utc_now

PACK_FORMAT = "xinxi_teacher_pack"
PACK_VERSION = 1


def build_teacher_pack(db: Session, current_user: User) -> dict:
    students = apply_student_scope(db.query(User), current_user).order_by(User.class_name, User.id).all()
    if current_user.role == UserRole.admin:
        texts = db.query(TypingText).order_by(TypingText.id).all()
        exams = db.query(Exam).options(joinedload(Exam.questions)).order_by(Exam.id).all()
        classes = sorted({s.class_name for s in students if s.class_name})
    else:
        texts = (
            db.query(TypingText)
            .filter(TypingText.teacher_id == current_user.id)
            .order_by(TypingText.id)
            .all()
        )
        exams = (
            db.query(Exam)
            .options(joinedload(Exam.questions))
            .filter(Exam.created_by == current_user.id)
            .order_by(Exam.id)
            .all()
        )
        classes = list(current_user.assigned_classes or [])

    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "exported_at": serialize_utc_datetime(utc_now()),
        "teacher": {
            "username": current_user.username,
            "name": current_user.name,
            "role": current_user.role.value,
        },
        "classes": classes,
        "students": [
            {
                "username": s.username,
                "name": s.name,
                "class_name": s.class_name,
                "is_active": bool(s.is_active),
            }
            for s in students
        ],
        "typing_texts": [
            {
                "title": t.title,
                "content": t.content,
                "difficulty": t.difficulty.value if t.difficulty else TypingDifficulty.basic.value,
                "char_count": t.char_count,
                "time_limit": t.time_limit,
                "is_active": bool(t.is_active),
            }
            for t in texts
        ],
        "exams": [_dump_exam(exam) for exam in exams],
    }


def import_teacher_pack(db: Session, current_user: User, payload: dict) -> dict:
    if not isinstance(payload, dict) or payload.get("format") != PACK_FORMAT:
        raise HTTPException(status_code=400, detail="不是有效的教师数据包")
    try:
        version = int(payload.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    if version != PACK_VERSION:
        raise HTTPException(status_code=400, detail="数据包版本不受支持")

    errors: list[str] = []
    class_count = 0
    student_created = 0
    student_updated = 0
    text_count = 0
    exam_count = 0

    owner_id = current_user.id if current_user.role == UserRole.teacher else None

    for raw_name in payload.get("classes") or []:
        name = str(raw_name or "").strip()
        if not name:
            continue
        if current_user.role == UserRole.teacher:
            claim_class_for_teacher(db, current_user, name)
        class_count += 1

    for item in payload.get("students") or []:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        name = str(item.get("name") or "").strip()
        class_name = str(item.get("class_name") or "").strip()
        if not username or not name:
            errors.append("跳过缺少用户名或姓名的学生")
            continue
        if current_user.role == UserRole.teacher:
            class_name = claim_class_for_teacher(db, current_user, class_name)
        elif not class_name:
            class_name = "课堂"

        existing = db.query(User).filter(User.username == username).first()
        if existing:
            if existing.role != UserRole.student:
                errors.append(f"用户名 {username} 已被其他角色占用，已跳过")
                continue
            if current_user.role == UserRole.teacher:
                if existing.managed_by_teacher_id not in (None, current_user.id):
                    errors.append(f"学生 {username} 已绑定其他教师，已跳过")
                    continue
                existing.managed_by_teacher_id = current_user.id
            existing.name = name
            existing.class_name = class_name
            if "is_active" in item:
                existing.is_active = bool(item.get("is_active"))
            student_updated += 1
            continue

        if active_student_name_taken(db, name, class_name):
            errors.append(f"班级 {class_name} 已有同名学生 {name}，已跳过")
            continue

        db.add(
            User(
                username=username,
                password_hash=get_password_hash("123456"),
                name=name,
                role=UserRole.student,
                class_name=class_name,
                assigned_classes=[],
                managed_by_teacher_id=owner_id,
                is_active=bool(item.get("is_active", True)),
            )
        )
        student_created += 1

    for item in payload.get("typing_texts") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            errors.append("跳过缺少标题或正文的打字文章")
            continue
        query = db.query(TypingText).filter(TypingText.title == title)
        if current_user.role == UserRole.teacher:
            query = query.filter(TypingText.teacher_id == current_user.id)
        if query.first():
            errors.append(f"打字文章「{title}」已存在，已跳过")
            continue
        difficulty = _parse_difficulty(item.get("difficulty"))
        db.add(
            TypingText(
                teacher_id=owner_id,
                title=title,
                content=content,
                difficulty=difficulty,
                char_count=int(item.get("char_count") or len(content)),
                time_limit=int(item.get("time_limit") or 120),
                is_active=bool(item.get("is_active", True)),
            )
        )
        text_count += 1

    for item in payload.get("exams") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            errors.append("跳过缺少标题的考试")
            continue
        query = db.query(Exam).filter(Exam.title == title)
        if current_user.role == UserRole.teacher:
            query = query.filter(Exam.created_by == current_user.id)
        if query.first():
            errors.append(f"考试「{title}」已存在，已跳过")
            continue
        exam = Exam(
            title=title,
            description=str(item.get("description") or ""),
            duration_minutes=int(item.get("duration_minutes") or 60),
            pass_score=float(item.get("pass_score") or 60),
            created_by=current_user.id,
            status=_parse_exam_status(item.get("status")),
        )
        db.add(exam)
        db.flush()
        for idx, raw_q in enumerate(item.get("questions") or []):
            if not isinstance(raw_q, dict):
                continue
            content = str(raw_q.get("content") or "").strip()
            if not content:
                continue
            try:
                qtype = QuestionType(raw_q.get("type"))
            except ValueError:
                continue
            db.add(
                Question(
                    exam_id=exam.id,
                    type=qtype,
                    content=content,
                    options=raw_q.get("options") or [],
                    correct_answer=str(raw_q.get("correct_answer") or ""),
                    score=float(raw_q.get("score") or 5),
                    order_num=int(raw_q.get("order_num") or idx),
                )
            )
        exam_count += 1

    db.commit()
    return {
        "class_count": class_count,
        "student_created": student_created,
        "student_updated": student_updated,
        "text_count": text_count,
        "exam_count": exam_count,
        "errors": errors,
    }


def pack_filename(user: User) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"教师数据_{user.username}_{stamp}.json"


def _dump_exam(exam: Exam) -> dict:
    questions = sorted(exam.questions or [], key=lambda q: q.order_num or 0)
    return {
        "title": exam.title,
        "description": exam.description or "",
        "duration_minutes": exam.duration_minutes,
        "pass_score": exam.pass_score,
        "status": exam.status.value if exam.status else "draft",
        "questions": [
            {
                "type": q.type.value if q.type else "choice",
                "content": q.content,
                "options": q.options or [],
                "correct_answer": q.correct_answer or "",
                "score": q.score,
                "order_num": q.order_num,
            }
            for q in questions
        ],
    }


def _parse_difficulty(value) -> TypingDifficulty:
    try:
        return TypingDifficulty(value)
    except ValueError:
        return TypingDifficulty.basic


def _parse_exam_status(value):
    from .models import ExamStatus

    try:
        return ExamStatus(value)
    except ValueError:
        return ExamStatus.draft
