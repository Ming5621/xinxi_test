"""教师机之间同步班级、学生、考试和打字素材。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from .auth import DEFAULT_STUDENT_PASSWORD, get_password_hash
from .models import Exam, Question, QuestionType, TypingDifficulty, TypingText, User, UserRole
from .permissions import (
    active_student_name_taken,
    apply_student_scope,
    list_all_classes,
    remember_class,
    resolve_student_class,
    student_in_scope,
    teacher_can_manage_class,
)
from .timeutil import serialize_utc_datetime, utc_now
from .schemas import ExamCreate, TypingTextCreate

PACK_FORMAT = "xinxi_teacher_pack"
PACK_VERSION = 1


def build_teacher_pack(db: Session, current_user: User) -> dict:
    students = apply_student_scope(db.query(User), current_user).order_by(User.class_name, User.id).all()
    if current_user.role == UserRole.admin:
        texts = db.query(TypingText).order_by(TypingText.id).all()
        exams = db.query(Exam).options(joinedload(Exam.questions)).order_by(Exam.id).all()
        classes = list_all_classes(db)
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
    for key in ("classes", "students", "typing_texts", "exams"):
        if payload.get(key) is not None and not isinstance(payload[key], list):
            raise HTTPException(status_code=400, detail=f"数据包 {key} 必须是列表")

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
        try:
            resolve_student_class(current_user, name)
        except HTTPException as exc:
            errors.append(f"班级 {name}：{exc.detail}")
            continue
        if current_user.role == UserRole.admin:
            remember_class(db, name)
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
        try:
            from .routers.users import _clean_name, _clean_username
            username = _clean_username(username)
            name = _clean_name(name, for_student=True)
            class_name = resolve_student_class(current_user, class_name)
        except HTTPException as exc:
            errors.append(f"学生 {username}：{exc.detail}")
            continue

        existing = db.query(User).filter(User.username == username).first()
        is_active = bool(item.get("is_active", existing.is_active if existing else True))
        if existing:
            if existing.role != UserRole.student:
                errors.append(f"用户名 {username} 已被其他角色占用，已跳过")
                continue
            if current_user.role == UserRole.teacher and not student_in_scope(current_user, existing):
                errors.append(f"无权管理学生 {username}，已跳过")
                continue
            if is_active and active_student_name_taken(db, name, class_name, existing.id):
                errors.append(f"班级 {class_name} 已有同名学生 {name}，已跳过")
                continue
            if current_user.role == UserRole.admin:
                remember_class(db, class_name)
                if existing.managed_by_teacher_id is not None and class_name != existing.class_name:
                    if not teacher_can_manage_class(db.get(User, existing.managed_by_teacher_id), class_name):
                        existing.managed_by_teacher_id = None
            existing.name = name
            existing.class_name = class_name
            existing.is_active = is_active
            db.flush()
            student_updated += 1
            continue

        if is_active and active_student_name_taken(db, name, class_name):
            errors.append(f"班级 {class_name} 已有同名学生 {name}，已跳过")
            continue

        if current_user.role == UserRole.admin:
            remember_class(db, class_name)
        db.add(
            User(
                username=username,
                password_hash=get_password_hash(DEFAULT_STUDENT_PASSWORD),
                must_change_password=True,
                name=name,
                role=UserRole.student,
                class_name=class_name,
                assigned_classes=[],
                managed_by_teacher_id=owner_id,
                is_active=is_active,
            )
        )
        db.flush()
        student_created += 1

    for item in payload.get("typing_texts") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            errors.append("跳过缺少标题或正文的打字文章")
            continue
        try:
            data = TypingTextCreate.model_validate({**item, "title": title, "content": content})
        except ValidationError:
            errors.append(f"打字文章「{title}」字段无效，已跳过")
            continue
        query = db.query(TypingText).filter(TypingText.title == title)
        if current_user.role == UserRole.teacher:
            query = query.filter(TypingText.teacher_id == current_user.id)
        if query.first():
            errors.append(f"打字文章「{title}」已存在，已跳过")
            continue
        db.add(
            TypingText(
                teacher_id=owner_id,
                title=title,
                content=content,
                difficulty=data.difficulty,
                char_count=len(content),
                time_limit=data.time_limit,
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
        try:
            data = ExamCreate.model_validate({**item, "title": title})
        except ValidationError:
            errors.append(f"考试「{title}」字段无效，已跳过")
            continue
        status = _parse_exam_status(item.get("status"))
        if status.value == "published" and not data.questions:
            errors.append(f"考试「{title}」没有题目，已跳过")
            continue
        query = db.query(Exam).filter(Exam.title == title)
        if current_user.role == UserRole.teacher:
            query = query.filter(Exam.created_by == current_user.id)
        if query.first():
            errors.append(f"考试「{title}」已存在，已跳过")
            continue
        exam = Exam(
            title=title,
            description=data.description,
            duration_minutes=data.duration_minutes,
            pass_score=data.pass_score,
            created_by=current_user.id,
            status=status,
        )
        db.add(exam)
        db.flush()
        for idx, question in enumerate(data.questions):
            db.add(
                Question(
                    exam_id=exam.id,
                    type=question.type,
                    content=question.content,
                    options=question.options,
                    correct_answer=question.correct_answer,
                    score=question.score,
                    order_num=question.order_num or idx,
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
