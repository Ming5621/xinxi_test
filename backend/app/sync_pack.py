"""教师机之间同步班级、学生、考试和打字素材。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from .auth import DEFAULT_STUDENT_PASSWORD, get_password_hash
from .models import (
    Answer,
    Exam,
    ExamSession,
    Question,
    QuestionType,
    SessionStatus,
    TypingClassSession,
    TypingClassSessionStatus,
    TypingDifficulty,
    TypingRecord,
    TypingText,
    User,
    UserRole,
)
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
PACK_VERSION = 3
SUPPORTED_VERSIONS = {1, 2, 3}


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
        for teacher in db.query(User).filter(User.role.in_([UserRole.teacher, UserRole.admin])).all()
    }
    exported_teachers = teachers if current_user.role == UserRole.admin else [current_user]
    admins = []
    if current_user.role == UserRole.admin:
        admins = db.query(User).filter(User.role == UserRole.admin).order_by(User.id).all()
    student_ids = [student.id for student in students]
    student_usernames = {student.id: student.username for student in students}
    typing_sessions = _sessions_for_export(db, current_user)
    typing_records = _records_for_export(db, student_ids)
    exam_results = _exam_results_for_export(db, current_user, student_ids, {exam.id for exam in exams})
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
        "admins": [_dump_admin(admin) for admin in admins],
        "typing_sessions": [_dump_typing_session(session, teacher_names) for session in typing_sessions],
        "typing_records": [_dump_typing_record(record, student_usernames, teacher_names) for record in typing_records],
        "exam_results": exam_results,
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
    for key in ("teachers", "classes", "students", "typing_texts", "exams", "admins", "typing_sessions", "typing_records", "exam_results"):
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
    if is_admin:
        _import_admins(db, payload.get("admins") or [], overwrite, errors)
    activity = _import_activity(db, current_user, payload, overwrite, errors)

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
        "typing_session_count": activity["typing_session_count"],
        "typing_record_count": activity["typing_record_count"],
        "exam_result_count": activity["exam_result_count"],
        "errors": errors,
    }


def _sessions_for_export(db: Session, current_user: User) -> list[TypingClassSession]:
    query = db.query(TypingClassSession).options(joinedload(TypingClassSession.text))
    if current_user.role != UserRole.admin:
        query = query.filter(TypingClassSession.teacher_id == current_user.id)
    return query.order_by(TypingClassSession.id).all()


def _records_for_export(db: Session, student_ids: list[int]) -> list[TypingRecord]:
    if not student_ids:
        return []
    return (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.text), joinedload(TypingRecord.typing_session))
        .filter(TypingRecord.student_id.in_(student_ids))
        .order_by(TypingRecord.id)
        .all()
    )


def _exam_results_for_export(db: Session, current_user: User, student_ids: list[int], exam_ids: set[int]) -> list[dict]:
    if not student_ids:
        return []
    query = (
        db.query(ExamSession)
        .options(joinedload(ExamSession.answers), joinedload(ExamSession.exam).joinedload(Exam.questions), joinedload(ExamSession.student))
        .filter(ExamSession.student_id.in_(student_ids))
    )
    if current_user.role != UserRole.admin:
        query = query.filter(ExamSession.exam_id.in_(exam_ids or {-1}))
    owners = {
        user.id: user.username
        for user in db.query(User).filter(User.role == UserRole.teacher).all()
    }
    results = []
    seen_sessions: set[int] = set()
    for session in query.order_by(ExamSession.id).all():
        if session.id in seen_sessions:
            continue
        seen_sessions.add(session.id)
        exam = session.exam
        student = session.student
        if not exam or not student:
            continue
        order_by_question = {question.id: question.order_num for question in exam.questions}
        seen_answers: set[int] = set()
        answers = []
        for answer in session.answers:
            if answer.id in seen_answers:
                continue
            seen_answers.add(answer.id)
            answers.append({
                "order_num": order_by_question.get(answer.question_id, 0),
                "student_answer": answer.student_answer or "",
                "is_correct": bool(answer.is_correct),
                "score": answer.score,
                "answer_meta": answer.answer_meta or {},
            })
        results.append({
            "student_username": student.username,
            "exam_title": exam.title,
            "owner_username": current_user.username if current_user.role != UserRole.admin else owners.get(exam.created_by, ""),
            "status": session.status.value if session.status else SessionStatus.submitted.value,
            "start_time": serialize_utc_datetime(session.start_time) if session.start_time else "",
            "submit_time": serialize_utc_datetime(session.submit_time) if session.submit_time else "",
            "total_score": session.total_score,
            "max_score": session.max_score,
            "answers": answers,
        })
    return results


def _dump_admin(admin: User) -> dict:
    return {
        "username": admin.username,
        "name": admin.name,
        "is_active": bool(admin.is_active),
        "password_hash": admin.password_hash or "",
        "must_change_password": bool(admin.must_change_password),
    }


def _dump_typing_session(session: TypingClassSession, teacher_names: dict[int, str]) -> dict:
    return {
        "owner_username": teacher_names.get(session.teacher_id, ""),
        "class_name": session.class_name,
        "title": session.title or "",
        "text_title": session.text.title if session.text else "",
        "status": session.status.value if session.status else TypingClassSessionStatus.ended.value,
        "duration_seconds": session.duration_seconds,
        "started_at": serialize_utc_datetime(session.started_at) if session.started_at else "",
        "ended_at": serialize_utc_datetime(session.ended_at) if session.ended_at else "",
        "created_at": serialize_utc_datetime(session.created_at) if session.created_at else "",
    }


def _dump_typing_record(record: TypingRecord, student_usernames: dict[int, str], teacher_names: dict[int, str]) -> dict:
    session = record.typing_session
    text = record.text
    return {
        "student_username": student_usernames.get(record.student_id, ""),
        "text_title": text.title if text else "",
        "text_owner_username": teacher_names.get(text.teacher_id, "") if text and text.teacher_id else "",
        "session_owner_username": teacher_names.get(session.teacher_id, "") if session else "",
        "session_class_name": session.class_name if session else "",
        "session_title": (session.title or "") if session else "",
        "session_created_at": serialize_utc_datetime(session.created_at) if session and session.created_at else "",
        "source": record.source or "practice",
        "reference_text": record.reference_text or "",
        "typed_text": record.typed_text or "",
        "duration_seconds": record.duration_seconds,
        "wpm": record.wpm,
        "accuracy": record.accuracy,
        "correct_chars": record.correct_chars,
        "level": record.level or "",
        "score": record.score,
        "created_at": serialize_utc_datetime(record.created_at) if record.created_at else "",
    }


def _import_admins(db: Session, items: list, overwrite: bool, errors: list[str]) -> None:
    for item in items:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        name = str(item.get("name") or "").strip()
        if not username or not name:
            errors.append("跳过缺少用户名或姓名的管理员")
            continue
        existing = db.query(User).filter(User.username == username).first()
        password_hash = _usable_password_hash(item.get("password_hash"))
        if existing is None:
            db.add(User(
                username=username,
                password_hash=password_hash or get_password_hash("admin123"),
                must_change_password=bool(item.get("must_change_password", not password_hash)),
                name=name,
                role=UserRole.admin,
                class_name="",
                assigned_classes=[],
                is_active=bool(item.get("is_active", True)),
            ))
            db.flush()
            continue
        if existing.role != UserRole.admin:
            errors.append(f"用户名 {username} 已被其他角色占用，已跳过")
            continue
        if not overwrite:
            errors.append(f"管理员账号 {username} 已存在，未覆盖")
            continue
        existing.name = name
        existing.is_active = bool(item.get("is_active", existing.is_active))
        if password_hash:
            existing.password_hash = password_hash
            existing.must_change_password = bool(item.get("must_change_password", False))
        db.flush()


def _parse_dt(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _import_activity(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> dict:
    counts = {"typing_session_count": 0, "typing_record_count": 0, "exam_result_count": 0}
    if any(key in payload for key in ("typing_sessions", "typing_records", "exam_results")):
        counts["typing_session_count"] = _import_typing_sessions(db, current_user, payload, overwrite, errors)
        counts["exam_result_count"] = _import_exam_results(db, current_user, payload, overwrite, errors)
        counts["typing_record_count"] = _import_typing_records(db, current_user, payload, overwrite, errors)
    return counts


def _owner_user(db: Session, current_user: User, username: str) -> User | None:
    if current_user.role == UserRole.teacher:
        return current_user
    name = str(username or "").strip()
    if not name:
        return None
    return db.query(User).filter(User.username == name, User.role == UserRole.teacher).first()


def _import_typing_sessions(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> int:
    items = payload.get("typing_sessions") or []
    if overwrite and "typing_sessions" in payload:
        owner_ids = {current_user.id} if current_user.role == UserRole.teacher else set()
        if current_user.role == UserRole.admin:
            for item in items:
                if not isinstance(item, dict):
                    continue
                owner = _owner_user(db, current_user, item.get("owner_username"))
                if owner:
                    owner_ids.add(owner.id)
        if owner_ids:
            session_ids = [
                row.id for row in db.query(TypingClassSession.id).filter(TypingClassSession.teacher_id.in_(owner_ids))
            ]
            if session_ids:
                db.query(TypingRecord).filter(TypingRecord.typing_session_id.in_(session_ids)).delete(synchronize_session=False)
            db.query(TypingClassSession).filter(TypingClassSession.teacher_id.in_(owner_ids)).delete(synchronize_session=False)
            db.flush()
    written = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        owner = _owner_user(db, current_user, item.get("owner_username"))
        class_name = str(item.get("class_name") or "").strip()
        title = str(item.get("title") or "").strip()
        if owner is None or not class_name:
            errors.append(f"课堂测试「{title or '未命名'}」找不到教师或班级，已跳过")
            continue
        text = None
        text_title = str(item.get("text_title") or "").strip()
        if text_title:
            text = db.query(TypingText).filter(TypingText.teacher_id == owner.id, TypingText.title == text_title).first()
        if text is None:
            errors.append(f"课堂测试「{title or text_title}」找不到对应文章，已跳过")
            continue
        created_at = _parse_dt(item.get("created_at")) or utc_now()
        if not overwrite:
            exists = db.query(TypingClassSession).filter(
                TypingClassSession.teacher_id == owner.id,
                TypingClassSession.class_name == class_name,
                TypingClassSession.title == title,
                TypingClassSession.created_at == created_at,
            ).first()
            if exists:
                continue
        status = item.get("status")
        try:
            status = TypingClassSessionStatus(status)
        except ValueError:
            status = TypingClassSessionStatus.ended
        db.add(TypingClassSession(
            teacher_id=owner.id,
            text_id=text.id,
            class_name=class_name,
            title=title,
            status=status,
            duration_seconds=int(item.get("duration_seconds") or 300),
            started_at=_parse_dt(item.get("started_at")),
            ended_at=_parse_dt(item.get("ended_at")),
            created_at=created_at,
        ))
        written += 1
    db.flush()
    return written


def _import_exam_results(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> int:
    items = payload.get("exam_results") or []
    written = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        username = str(item.get("student_username") or "").strip()
        title = str(item.get("exam_title") or "").strip()
        student = db.query(User).filter(User.username == username, User.role == UserRole.student).first()
        owner = _owner_user(db, current_user, item.get("owner_username"))
        if student is None or owner is None or not title:
            errors.append(f"考试成绩「{title or username}」找不到学生或教师，已跳过")
            continue
        if current_user.role == UserRole.teacher and not student_in_scope(current_user, student):
            errors.append(f"无权导入学生 {username} 的考试成绩，已跳过")
            continue
        exam = (
            db.query(Exam)
            .options(joinedload(Exam.questions))
            .filter(Exam.created_by == owner.id, Exam.title == title)
            .first()
        )
        if exam is None:
            errors.append(f"考试成绩「{title}」找不到对应考试，已跳过")
            continue
        start_time = _parse_dt(item.get("start_time")) or utc_now()
        existing = db.query(ExamSession).filter(
            ExamSession.exam_id == exam.id,
            ExamSession.student_id == student.id,
            ExamSession.start_time == start_time,
        ).first()
        if existing and not overwrite:
            continue
        if existing and overwrite:
            db.delete(existing)
            db.flush()
        try:
            status = SessionStatus(item.get("status"))
        except ValueError:
            status = SessionStatus.submitted
        session = ExamSession(
            exam_id=exam.id,
            student_id=student.id,
            status=status,
            start_time=start_time,
            submit_time=_parse_dt(item.get("submit_time")),
            total_score=float(item.get("total_score") or 0),
            max_score=float(item.get("max_score") or 0),
        )
        db.add(session)
        db.flush()
        questions = {question.order_num: question for question in exam.questions}
        for answer in item.get("answers") or []:
            if not isinstance(answer, dict):
                continue
            question = questions.get(answer.get("order_num"))
            if question is None:
                continue
            db.add(Answer(
                session_id=session.id,
                question_id=question.id,
                student_answer=str(answer.get("student_answer") or ""),
                is_correct=bool(answer.get("is_correct")),
                score=float(answer.get("score") or 0),
                answer_meta=answer.get("answer_meta") if isinstance(answer.get("answer_meta"), dict) else {},
            ))
        written += 1
    db.flush()
    return written


def _find_typing_session(db: Session, owner: User | None, item: dict) -> TypingClassSession | None:
    if owner is None:
        return None
    created_at = _parse_dt(item.get("session_created_at"))
    query = db.query(TypingClassSession).filter(
        TypingClassSession.teacher_id == owner.id,
        TypingClassSession.class_name == str(item.get("session_class_name") or ""),
        TypingClassSession.title == str(item.get("session_title") or ""),
    )
    if created_at is not None:
        query = query.filter(TypingClassSession.created_at == created_at)
    return query.order_by(TypingClassSession.id.desc()).first()


def _import_typing_records(db: Session, current_user: User, payload: dict, overwrite: bool, errors: list[str]) -> int:
    items = payload.get("typing_records") or []
    if overwrite and "typing_records" in payload:
        usernames = {
            str(item.get("student_username") or "").strip()
            for item in items if isinstance(item, dict)
        }
        usernames.discard("")
        if usernames:
            student_ids = [
                row.id for row in db.query(User.id).filter(User.role == UserRole.student, User.username.in_(usernames))
            ]
            if student_ids:
                db.query(TypingRecord).filter(TypingRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
                db.flush()
    written = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        username = str(item.get("student_username") or "").strip()
        student = db.query(User).filter(User.username == username, User.role == UserRole.student).first()
        if student is None:
            errors.append(f"打字记录找不到学生 {username or '未命名'}，已跳过")
            continue
        if current_user.role == UserRole.teacher and not student_in_scope(current_user, student):
            errors.append(f"无权导入学生 {username} 的打字记录，已跳过")
            continue
        created_at = _parse_dt(item.get("created_at")) or utc_now()
        if not overwrite:
            exists = db.query(TypingRecord).filter(
                TypingRecord.student_id == student.id,
                TypingRecord.source == str(item.get("source") or "practice"),
                TypingRecord.created_at == created_at,
            ).first()
            if exists:
                continue
        text = None
        text_title = str(item.get("text_title") or "").strip()
        if text_title:
            owner = _owner_user(db, current_user, item.get("text_owner_username"))
            if owner:
                text = db.query(TypingText).filter(TypingText.teacher_id == owner.id, TypingText.title == text_title).first()
        session_owner = _owner_user(db, current_user, item.get("session_owner_username"))
        typing_session = _find_typing_session(db, session_owner, item)
        db.add(TypingRecord(
            student_id=student.id,
            text_id=text.id if text else None,
            typing_session_id=typing_session.id if typing_session else None,
            source=str(item.get("source") or "practice")[:20],
            reference_text=str(item.get("reference_text") or ""),
            typed_text=str(item.get("typed_text") or ""),
            duration_seconds=float(item.get("duration_seconds") or 0),
            wpm=float(item.get("wpm") or 0),
            accuracy=float(item.get("accuracy") or 0),
            correct_chars=int(item.get("correct_chars") or 0),
            level=str(item.get("level") or ""),
            score=float(item.get("score") or 0),
            created_at=created_at,
        ))
        written += 1
    db.flush()
    return written


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
