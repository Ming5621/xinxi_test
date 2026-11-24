"""教师机之间同步班级、学生、考试和打字素材。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from .auth import DEFAULT_STUDENT_PASSWORD, get_password_hash
from .models import Exam, Question, QuestionType, TypingDifficulty, TypingRecord, TypingText, User, UserRole
from .permissions import (
    active_student_name_taken,
    apply_student_scope,
    list_all_classes,
    remember_class,
    resolve_student_class,
    set_teacher_classes,
    student_in_scope,
    teacher_can_manage_class,
)
from .timeutil import serialize_utc_datetime, utc_now
from .schemas import ExamCreate, TypingTextCreate

PACK_FORMAT = "xinxi_teacher_pack"
PACK_VERSION = 2
SUPPORTED_VERSIONS = {1, 2}


def build_teacher_pack(db: Session, current_user: User) -> dict:
    students = apply_student_scope(db.query(User), current_user).order_by(User.class_name, User.id).all()
    if current_user.role == UserRole.admin:
        texts = db.query(TypingText).order_by(TypingText.id).all()
        exams = db.query(Exam).options(joinedload(Exam.questions)).order_by(Exam.id).all()
        classes = list_all_classes(db)
        teachers = db.query(User).filter(User.role == UserRole.teacher).order_by(User.id).all()
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
        teachers = [current_user]

    teacher_names = {
        teacher.id: teacher.username
        for teacher in db.query(User).filter(User.role == UserRole.teacher).all()
    }
    exported_teachers = teachers if current_user.role == UserRole.admin else [current_user]
    return {
        "format": PACK_FORMAT,
        "version": PACK_VERSION,
        "exported_at": serialize_utc_datetime(utc_now()),
        "teacher": {
            "username": current_user.username,
            "name": current_user.name,
            "role": current_user.role.value,
        },
        "teachers": [_dump_teacher(teacher) for teacher in exported_teachers],
        "classes": classes,
        "students": [
            {
                "username": s.username,
                "name": s.name,
                "class_name": s.class_name,
                "is_active": bool(s.is_active),
                "teacher_username": teacher_names.get(s.managed_by_teacher_id, ""),
                "password_hash": s.password_hash or "",
                "must_change_password": bool(s.must_change_password),
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
                "owner_username": teacher_names.get(t.teacher_id, ""),
            }
            for t in texts
        ],
        "exams": [_dump_exam(exam, teacher_names.get(exam.created_by, "")) for exam in exams],
    }


def import_teacher_pack(db: Session, current_user: User, payload: dict, overwrite: bool = False) -> dict:
    if not isinstance(payload, dict) or payload.get("format") != PACK_FORMAT:
        raise HTTPException(status_code=400, detail="不是有效的教师数据包")
    try:
        version = int(payload.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    if version not in SUPPORTED_VERSIONS:
        raise HTTPException(status_code=400, detail="数据包版本不受支持")
    for key in ("teachers", "classes", "students", "typing_texts", "exams"):
        if payload.get(key) is not None and not isinstance(payload[key], list):
            raise HTTPException(status_code=400, detail=f"数据包 {key} 必须是列表")

    errors: list[str] = []
    class_count = 0
    teacher_created = 0
    teacher_updated = 0
    student_created = 0
    student_updated = 0
    student_removed = 0
    text_count = 0
    exam_count = 0

    is_admin = current_user.role == UserRole.admin

    for raw_name in payload.get("classes") or []:
        name = str(raw_name or "").strip()
        if not name:
            continue
        try:
            resolve_student_class(current_user, name)
        except HTTPException as exc:
            errors.append(f"班级 {name}：{exc.detail}")
            continue
        if is_admin:
            remember_class(db, name)
        class_count += 1

    if is_admin:
        teacher_created, teacher_updated = _import_teachers(db, payload.get("teachers") or [], overwrite, errors)

    imported_student_names: set[str] = set()
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
            managed_by = _student_owner_id(db, current_user, item, class_name)
        except HTTPException as exc:
            errors.append(f"学生 {username or name}：{exc.detail}")
            continue

        imported_student_names.add(username)
        existing = db.query(User).filter(User.username == username).first()
        is_active = bool(item.get("is_active", existing.is_active if existing else True))
        password_hash = _usable_password_hash(item.get("password_hash"))
        if existing:
            if not overwrite:
                errors.append(f"学生账号 {username} 已存在，未覆盖")
                continue
            if existing.role != UserRole.student:
                errors.append(f"用户名 {username} 已被其他角色占用，已跳过")
                continue
            if current_user.role == UserRole.teacher and not student_in_scope(current_user, existing):
                errors.append(f"无权管理学生 {username}，已跳过")
                continue
            if is_active and active_student_name_taken(db, name, class_name, existing.id):
                errors.append(f"班级 {class_name} 已有同名学生 {name}，已跳过")
                continue
            if is_admin:
                remember_class(db, class_name)
            existing.name = name
            existing.class_name = class_name
            existing.is_active = is_active
            existing.managed_by_teacher_id = managed_by
            if password_hash:
                existing.password_hash = password_hash
                existing.must_change_password = bool(item.get("must_change_password", False))
            db.flush()
            student_updated += 1
            continue

        if is_active and active_student_name_taken(db, name, class_name):
            errors.append(f"班级 {class_name} 已有同名学生 {name}，已跳过")
            continue

        if is_admin:
            remember_class(db, class_name)
        db.add(
            User(
                username=username,
                password_hash=password_hash or get_password_hash(DEFAULT_STUDENT_PASSWORD),
                must_change_password=bool(item.get("must_change_password", True)),
                name=name,
                role=UserRole.student,
                class_name=class_name,
                assigned_classes=[],
                managed_by_teacher_id=managed_by,
                is_active=is_active,
            )
        )
        db.flush()
        student_created += 1

    if overwrite and "students" in payload:
        student_removed = _remove_missing_students(db, current_user, payload, imported_student_names)

    text_count = _import_texts(db, current_user, payload, overwrite, errors)
    exam_count = _import_exams(db, current_user, payload, overwrite, errors)

    db.commit()
    return {
        "class_count": class_count,
        "teacher_created": teacher_created,
        "teacher_updated": teacher_updated,
        "student_created": student_created,
        "student_updated": student_updated,
        "student_removed": student_removed,
        "text_count": text_count,
        "exam_count": exam_count,
        "errors": errors,
    }


def pack_filename(user: User) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"教师数据_{user.username}_{stamp}.json"


def _dump_teacher(teacher: User) -> dict:
    return {
        "username": teacher.username,
        "name": teacher.name,
        "assigned_classes": list(teacher.assigned_classes or []),
        "is_active": bool(teacher.is_active),
        "password_hash": teacher.password_hash or "",
        "must_change_password": bool(teacher.must_change_password),
    }


def _dump_exam(exam: Exam, owner_username: str = "") -> dict:
    questions = sorted(exam.questions or [], key=lambda q: q.order_num or 0)
    return {
        "title": exam.title,
        "owner_username": owner_username,
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


def _usable_password_hash(value) -> str | None:
    text = str(value or "").strip()
    if text.startswith("$2"):
        return text
    return None


def _class_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        name = str(item or "").strip()
        if name and name not in names and len(name) <= 100:
            names.append(name)
    return names


def _import_teachers(db: Session, items: list, overwrite: bool, errors: list[str]) -> tuple[int, int]:
    created = updated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        name = str(item.get("name") or "").strip()
        if not username or not name:
            errors.append("跳过缺少用户名或姓名的教师")
            continue
        try:
            from .routers.users import _clean_name, _clean_username
            username = _clean_username(username)
            name = _clean_name(name, for_student=False)
        except HTTPException as exc:
            errors.append(f"教师 {username or name}：{exc.detail}")
            continue
        classes = _class_list(item.get("assigned_classes"))
        existing = db.query(User).filter(User.username == username).first()
        if existing and existing.role != UserRole.teacher:
            errors.append(f"用户名 {username} 已被其他角色占用，已跳过")
            continue
        if existing and not overwrite:
            errors.append(f"教师账号 {username} 已存在，未覆盖")
            continue
        password_hash = _usable_password_hash(item.get("password_hash"))
        if existing is None:
            teacher = User(
                username=username,
                password_hash=password_hash or get_password_hash("teacher123"),
                must_change_password=bool(item.get("must_change_password", not password_hash)),
                name=name,
                role=UserRole.teacher,
                class_name="",
                assigned_classes=[],
                is_active=bool(item.get("is_active", True)),
            )
            db.add(teacher)
            db.flush()
            set_teacher_classes(db, teacher, classes)
            created += 1
            continue
        existing.name = name
        existing.is_active = bool(item.get("is_active", existing.is_active))
        if password_hash:
            existing.password_hash = password_hash
            existing.must_change_password = bool(item.get("must_change_password", False))
        set_teacher_classes(db, existing, classes)
        db.flush()
        updated += 1
    return created, updated


def _student_owner_id(db: Session, current_user: User, item: dict, class_name: str) -> int | None:
    if current_user.role == UserRole.teacher:
        return current_user.id
    teacher_username = str(item.get("teacher_username") or "").strip()
    if not teacher_username:
        return None
    teacher = db.query(User).filter(User.username == teacher_username, User.role == UserRole.teacher).first()
    if not teacher_can_manage_class(teacher, class_name):
        raise HTTPException(status_code=400, detail=f"教师 {teacher_username} 不能管理班级 {class_name}")
    return teacher.id


def _delete_student(db: Session, student: User) -> None:
    for session in list(student.exam_sessions):
        db.delete(session)
    db.query(TypingRecord).filter(TypingRecord.student_id == student.id).delete(synchronize_session=False)
    db.flush()
    db.delete(student)


def _remove_missing_students(db: Session, current_user: User, payload: dict, imported_names: set[str]) -> int:
    """覆盖导入时，删掉数据包里已经没有、且仍绑定该教师的学生。"""
    removed = 0
    if current_user.role == UserRole.teacher:
        owner_ids = {current_user.id}
        stale_names = imported_names
        query = db.query(User).filter(User.role == UserRole.student, User.managed_by_teacher_id.in_(owner_ids))
        for student in query.all():
            if student.username not in stale_names:
                _delete_student(db, student)
                removed += 1
        return removed

    by_teacher: dict[str, set[str]] = {}
    for item in payload.get("teachers") or []:
        if isinstance(item, dict) and str(item.get("username") or "").strip():
            by_teacher.setdefault(str(item["username"]).strip(), set())
    for item in payload.get("students") or []:
        if not isinstance(item, dict):
            continue
        teacher_username = str(item.get("teacher_username") or "").strip()
        username = str(item.get("username") or "").strip()
        if teacher_username and username:
            by_teacher.setdefault(teacher_username, set()).add(username)
    for teacher_username, usernames in by_teacher.items():
        teacher = db.query(User).filter(User.username == teacher_username, User.role == UserRole.teacher).first()
        if not teacher:
            continue
        bound = db.query(User).filter(User.role == UserRole.student, User.managed_by_teacher_id == teacher.id).all()
        for student in bound:
            if student.username not in usernames:
                _delete_student(db, student)
                removed += 1
    return removed


def _content_owner_id(db: Session, current_user: User, item: dict) -> int | None:
    if current_user.role == UserRole.teacher:
        return current_user.id
    owner_name = str(item.get("owner_username") or "").strip()
    if not owner_name:
        return current_user.id
    owner = db.query(User).filter(User.username == owner_name, User.role == UserRole.teacher).first()
    return owner.id if owner else None


def _import_texts(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> int:
    parsed: list[tuple[int, TypingTextCreate, bool]] = []
    protected_titles: dict[int, set[str]] = {}
    for item in payload.get("typing_texts") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            errors.append("跳过缺少标题或正文的打字文章")
            continue
        owner_id = _content_owner_id(db, current_user, item)
        if owner_id is None:
            errors.append(f"打字文章「{title}」找不到对应教师，已跳过")
            continue
        try:
            data = TypingTextCreate.model_validate({**item, "title": title, "content": content})
        except ValidationError:
            errors.append(f"打字文章「{title}」字段无效，已跳过")
            protected_titles.setdefault(owner_id, set()).add(title)
            continue
        parsed.append((owner_id, data, bool(item.get("is_active", True))))
        protected_titles.setdefault(owner_id, set()).add(title)

    written = 0
    if not overwrite:
        for owner_id, data, is_active in parsed:
            exists = (
                db.query(TypingText)
                .filter(TypingText.teacher_id == owner_id, TypingText.title == data.title)
                .first()
            )
            if exists:
                errors.append(f"打字文章「{data.title}」已存在，未覆盖")
                continue
            db.add(_new_text(owner_id, data, is_active))
            written += 1
        return written

    owners = set(protected_titles)
    if current_user.role == UserRole.teacher and "typing_texts" in payload:
        owners.add(current_user.id)
    if current_user.role == UserRole.admin and "typing_texts" in payload:
        for item in payload.get("teachers") or []:
            if not isinstance(item, dict):
                continue
            owner = db.query(User).filter(
                User.username == str(item.get("username") or "").strip(),
                User.role == UserRole.teacher,
            ).first()
            if owner:
                owners.add(owner.id)
    for owner_id in owners:
        existing = db.query(TypingText).filter(TypingText.teacher_id == owner_id).all()
        by_title: dict[str, list[TypingText]] = {}
        for text in existing:
            by_title.setdefault(text.title, []).append(text)
        incoming = [row for row in parsed if row[0] == owner_id]
        seen = protected_titles.get(owner_id, set())
        for _owner_id, data, is_active in incoming:
            matches = by_title.get(data.title) or []
            if matches:
                text = matches[0]
                text.content = data.content
                text.difficulty = data.difficulty
                text.char_count = len(data.content)
                text.time_limit = data.time_limit
                text.is_active = is_active
                for extra in matches[1:]:
                    extra.is_active = False
            else:
                db.add(_new_text(owner_id, data, is_active))
            written += 1
        for title, rows in by_title.items():
            if title not in seen:
                for text in rows:
                    text.is_active = False
    return written


def _new_text(owner_id: int, data: TypingTextCreate, is_active: bool) -> TypingText:
    return TypingText(
        teacher_id=owner_id,
        title=data.title,
        content=data.content,
        difficulty=data.difficulty,
        char_count=len(data.content),
        time_limit=data.time_limit,
        is_active=is_active,
    )


def _import_exams(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> int:
    parsed: list[tuple[int, object, object, str]] = []
    protected_titles: dict[int, set[str]] = {}
    for item in payload.get("exams") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            errors.append("跳过缺少标题的考试")
            continue
        owner_id = _content_owner_id(db, current_user, item)
        if owner_id is None:
            errors.append(f"考试「{title}」找不到对应教师，已跳过")
            continue
        try:
            data = ExamCreate.model_validate({**item, "title": title})
        except ValidationError:
            errors.append(f"考试「{title}」字段无效，已跳过")
            protected_titles.setdefault(owner_id, set()).add(title)
            continue
        status = _parse_exam_status(item.get("status"))
        if status.value == "published" and not data.questions:
            errors.append(f"考试「{title}」没有题目，已跳过")
            protected_titles.setdefault(owner_id, set()).add(title)
            continue
        parsed.append((owner_id, data, status, title))
        protected_titles.setdefault(owner_id, set()).add(title)

    written = 0
    if not overwrite:
        for owner_id, data, status, title in parsed:
            exists = db.query(Exam).filter(Exam.created_by == owner_id, Exam.title == title).first()
            if exists:
                errors.append(f"考试「{title}」已存在，未覆盖")
                continue
            _add_exam(db, owner_id, data, status)
            written += 1
        return written

    owners = set(protected_titles)
    if current_user.role == UserRole.teacher and "exams" in payload:
        owners.add(current_user.id)
    if current_user.role == UserRole.admin and "exams" in payload:
        for item in payload.get("teachers") or []:
            if not isinstance(item, dict):
                continue
            owner = db.query(User).filter(
                User.username == str(item.get("username") or "").strip(),
                User.role == UserRole.teacher,
            ).first()
            if owner:
                owners.add(owner.id)
    for owner_id in owners:
        existing = db.query(Exam).filter(Exam.created_by == owner_id).all()
        by_title: dict[str, list[Exam]] = {}
        for exam in existing:
            by_title.setdefault(exam.title, []).append(exam)
        seen = protected_titles.get(owner_id, set())
        for item_owner, data, status, title in parsed:
            if item_owner != owner_id:
                continue
            matches = by_title.get(title) or []
            if matches:
                exam = matches[0]
                for extra in matches[1:]:
                    db.delete(extra)
                for session in list(exam.sessions):
                    db.delete(session)
                db.flush()
                for question in list(exam.questions):
                    db.delete(question)
                db.flush()
                exam.description = data.description
                exam.duration_minutes = data.duration_minutes
                exam.pass_score = data.pass_score
                exam.status = status
                _add_questions(db, exam, data.questions)
            else:
                _add_exam(db, owner_id, data, status)
            written += 1
        for title, rows in by_title.items():
            if title not in seen:
                for exam in rows:
                    db.delete(exam)
    return written


def _add_exam(db: Session, owner_id: int, data, status) -> Exam:
    exam = Exam(
        title=data.title,
        description=data.description,
        duration_minutes=data.duration_minutes,
        pass_score=data.pass_score,
        created_by=owner_id,
        status=status,
    )
    db.add(exam)
    db.flush()
    _add_questions(db, exam, data.questions)
    return exam


def _add_questions(db: Session, exam: Exam, questions) -> None:
    for idx, question in enumerate(questions):
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
