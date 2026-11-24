import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from ..auth import DEFAULT_STUDENT_PASSWORD, get_password_hash, require_admin, require_teacher
from ..database import get_db
from ..models import (
    Answer,
    Exam,
    ExamSession,
    Question,
    SchoolClass,
    TypingClassSession,
    TypingRecord,
    TypingText,
    User,
    UserRole,
)
from ..permissions import (
    active_student_name_taken,
    apply_student_scope,
    filter_class_name,
    remember_class,
    resolve_student_class,
    set_teacher_classes,
    student_in_scope,
    teacher_can_manage_class,
    validate_student_teacher,
)
from ..schemas import UserCreate, UserOut, UserUpdate
from .presence import _is_online
from .typing import _record_to_out

router = APIRouter(prefix="/api/users", tags=["用户管理"])

MANAGEABLE_ROLES = (UserRole.teacher, UserRole.student)


def _ensure_manage_user(current_user: User, target: User) -> None:
    if current_user.role == UserRole.admin:
        return
    if target.role != UserRole.student:
        raise HTTPException(status_code=403, detail="仅管理员可管理教师账号")
    if not student_in_scope(current_user, target):
        raise HTTPException(status_code=403, detail="无权管理该学生")


def _clean_username(username: str) -> str:
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if len(username) > 50:
        raise HTTPException(status_code=400, detail="用户名不能超过50个字符")
    if re.search(r"[\r\n\t\x00]", username):
        raise HTTPException(status_code=400, detail="用户名包含非法字符")
    return username


def _clean_name(name: str, *, for_student: bool) -> str:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if for_student:
        if len(name) > 40:
            raise HTTPException(status_code=400, detail="学生姓名不能超过40个字")
        if re.search(r"[\r\n\t]", name):
            raise HTTPException(status_code=400, detail="姓名包含非法字符")
    elif len(name) > 100:
        raise HTTPException(status_code=400, detail="姓名过长")
    return name


def _clean_class_list(classes: list[str] | None) -> list[str]:
    seen: list[str] = []
    for item in classes or []:
        name = (item or "").strip()
        if len(name) > 100:
            raise HTTPException(status_code=400, detail="班级名称不能超过100个字符")
        if name and name not in seen:
            seen.append(name)
    return seen


def _resolve_password(password: str | None, *, required: bool) -> str:
    raw = password or ""
    if raw and not raw.strip():
        raise HTTPException(status_code=400, detail="密码不能只包含空格")
    cleaned = raw.strip()
    if not cleaned:
        if required:
            raise HTTPException(status_code=400, detail="请设置密码")
        return DEFAULT_STUDENT_PASSWORD
    if "\0" in cleaned or len(cleaned.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="密码过长")
    return cleaned


def _ensure_unique_username(db: Session, username: str, exclude_id: int | None = None) -> None:
    query = db.query(User).filter(User.username == username)
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=400, detail="用户名已存在")


def default_username(db: Session, name: str) -> str:
    username = _clean_username(name[:50])
    base = username
    index = 2
    while db.query(User.id).filter(User.username == username).first():
        suffix = f"_{index}"
        username = f"{base[:50 - len(suffix)]}{suffix}"
        index += 1
    return username


def _ensure_student_identity(db: Session, name: str, class_name: str, exclude_id: int | None = None) -> None:
    if active_student_name_taken(db, name, class_name, exclude_id):
        raise HTTPException(
            status_code=400,
            detail=f"班级「{class_name}」已有同名学生「{name}」，姓名登录无法区分",
        )


def _count_other_active_admins(db: Session, user_id: int) -> int:
    return (
        db.query(User)
        .filter(User.role == UserRole.admin, User.is_active == True, User.id != user_id)  # noqa: E712
        .count()
    )


def _check_assignment_fields(data: UserCreate | UserUpdate, current_user: User, role: UserRole) -> None:
    assignment_fields = {"assigned_classes", "managed_by_teacher_id"}
    if current_user.role == UserRole.teacher and assignment_fields.intersection(data.model_fields_set):
        raise HTTPException(status_code=403, detail="仅管理员可编辑班级与教师绑定")
    if role != UserRole.student and data.managed_by_teacher_id is not None:
        raise HTTPException(status_code=400, detail="只有学生账号可以绑定教师")


@router.get("", response_model=list[UserOut])
def list_users(
    role: UserRole | None = None,
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    query = db.query(User)
    if current_user.role == UserRole.teacher:
        if role and role != UserRole.student:
            raise HTTPException(status_code=403, detail="无权查看该角色用户")
        query = apply_student_scope(query, current_user, class_name)
    else:
        if role:
            query = query.filter(User.role == role)
        if class_name:
            query = query.filter(User.class_name == class_name)
    return query.order_by(User.id).all()


@router.post("", response_model=UserOut)
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    if current_user.role == UserRole.teacher and data.role != UserRole.student:
        raise HTTPException(status_code=403, detail="仅管理员可创建教师账号")
    if data.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能通过接口创建管理员")
    if data.role not in MANAGEABLE_ROLES:
        raise HTTPException(status_code=400, detail="不支持的角色")
    _check_assignment_fields(data, current_user, data.role)

    name = _clean_name(data.name, for_student=data.role == UserRole.student)
    password = _resolve_password(data.password, required=data.role != UserRole.student)

    managed_by_teacher_id = None
    if data.role == UserRole.student:
        class_name = resolve_student_class(current_user, data.class_name)
        if current_user.role == UserRole.teacher:
            managed_by_teacher_id = current_user.id
        else:
            if data.managed_by_teacher_id is not None:
                validate_student_teacher(db.get(User, data.managed_by_teacher_id), class_name)
                managed_by_teacher_id = data.managed_by_teacher_id
            remember_class(db, class_name)
        _ensure_student_identity(db, name, class_name)
        assigned_classes: list[str] = []
    else:
        class_name = ""
        assigned_classes = _clean_class_list(data.assigned_classes)
        for name_of_class in assigned_classes:
            remember_class(db, name_of_class)

    username = _clean_username(data.username) if (data.username or "").strip() else default_username(db, name)
    _ensure_unique_username(db, username)
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        must_change_password=data.role == UserRole.student,
        name=name,
        role=data.role,
        class_name=class_name,
        assigned_classes=assigned_classes,
        managed_by_teacher_id=managed_by_teacher_id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_manage_user(current_user, user)

    original_role = user.role
    original_active = bool(user.is_active)
    original_class = user.class_name
    new_role = original_role

    if data.role is not None and data.role != original_role:
        if current_user.role != UserRole.admin:
            raise HTTPException(status_code=403, detail="仅管理员可修改角色")
        if data.role == UserRole.admin:
            raise HTTPException(status_code=400, detail="不能将账号设为管理员")
        if original_role == UserRole.admin or user.id == current_user.id:
            raise HTTPException(status_code=400, detail="不能修改管理员角色")
        if data.role not in MANAGEABLE_ROLES:
            raise HTTPException(status_code=400, detail="不支持的角色")
        new_role = data.role
    _check_assignment_fields(data, current_user, new_role)

    if data.username is not None:
        username = _clean_username(data.username)
        if username != user.username:
            if current_user.role != UserRole.admin:
                raise HTTPException(status_code=403, detail="仅管理员可修改用户名")
            _ensure_unique_username(db, username, exclude_id=user.id)
            user.username = username

    if data.name is not None or (new_role == UserRole.student and original_role != UserRole.student):
        user.name = _clean_name(data.name if data.name is not None else user.name, for_student=new_role == UserRole.student)

    if original_role == UserRole.teacher and new_role != UserRole.teacher:
        set_teacher_classes(db, user, [])

    if new_role == UserRole.student:
        if data.class_name is not None or original_role != UserRole.student:
            user.class_name = resolve_student_class(current_user, data.class_name)
        if current_user.role == UserRole.admin:
            if "managed_by_teacher_id" in data.model_fields_set:
                if data.managed_by_teacher_id is not None:
                    teacher = db.get(User, data.managed_by_teacher_id)
                    if teacher is user:
                        teacher = None
                    validate_student_teacher(teacher, user.class_name)
                user.managed_by_teacher_id = data.managed_by_teacher_id
            elif user.managed_by_teacher_id is not None and user.class_name != original_class:
                if not teacher_can_manage_class(db.get(User, user.managed_by_teacher_id), user.class_name):
                    user.managed_by_teacher_id = None
            if user.class_name:
                remember_class(db, user.class_name)
        user.assigned_classes = []
    elif new_role == UserRole.teacher:
        if current_user.role == UserRole.admin and (
            data.assigned_classes is not None or original_role != UserRole.teacher
        ):
            source = data.assigned_classes if data.assigned_classes is not None else (user.assigned_classes or [])
            set_teacher_classes(db, user, _clean_class_list(source))
        user.class_name = ""
        user.managed_by_teacher_id = None

    user.role = new_role

    if data.password or new_role != original_role:
        password = _resolve_password(data.password, required=new_role != UserRole.student)
        user.password_hash = get_password_hash(password)
        user.must_change_password = new_role == UserRole.student
        if new_role == UserRole.student:
            user.last_seen_at = None

    if data.is_active is not None and data.is_active != user.is_active:
        if data.is_active is False:
            if user.id == current_user.id:
                raise HTTPException(status_code=400, detail="不能禁用自己的账号")
            if user.role == UserRole.admin and _count_other_active_admins(db, user.id) == 0:
                raise HTTPException(status_code=400, detail="不能禁用最后一名管理员")
        user.is_active = data.is_active

    identity_touched = (
        data.name is not None
        or data.class_name is not None
        or new_role != original_role
        or (data.is_active is True and not original_active)
    )
    if user.role == UserRole.student and user.is_active and user.class_name and identity_touched:
        _ensure_student_identity(db, user.name, user.class_name, exclude_id=user.id)

    db.commit()
    db.refresh(user)
    return user


class BatchDeleteRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=500)
    force: bool = False


def _teacher_has_teaching_data(db: Session, teacher_id: int) -> bool:
    return bool(
        db.query(Exam.id).filter(Exam.created_by == teacher_id).first()
        or db.query(TypingText.id).filter(TypingText.teacher_id == teacher_id).first()
        or db.query(TypingClassSession.id).filter(TypingClassSession.teacher_id == teacher_id).first()
    )


def _purge_teacher_data(db: Session, teacher: User) -> None:
    text_ids = [row.id for row in db.query(TypingText.id).filter(TypingText.teacher_id == teacher.id)]
    session_query = db.query(TypingClassSession.id).filter(TypingClassSession.teacher_id == teacher.id)
    if text_ids:
        session_query = db.query(TypingClassSession.id).filter(
            (TypingClassSession.teacher_id == teacher.id) | (TypingClassSession.text_id.in_(text_ids))
        )
    session_ids = [row.id for row in session_query]
    if session_ids:
        db.query(TypingRecord).filter(TypingRecord.typing_session_id.in_(session_ids)).update(
            {TypingRecord.typing_session_id: None}, synchronize_session=False
        )
        db.query(TypingClassSession).filter(TypingClassSession.id.in_(session_ids)).delete(synchronize_session=False)
    if text_ids:
        db.query(TypingRecord).filter(TypingRecord.text_id.in_(text_ids)).update(
            {TypingRecord.text_id: None}, synchronize_session=False
        )
        db.query(TypingText).filter(TypingText.id.in_(text_ids)).delete(synchronize_session=False)

    exam_ids = [row.id for row in db.query(Exam.id).filter(Exam.created_by == teacher.id)]
    if exam_ids:
        question_ids = [row.id for row in db.query(Question.id).filter(Question.exam_id.in_(exam_ids))]
        exam_session_ids = [row.id for row in db.query(ExamSession.id).filter(ExamSession.exam_id.in_(exam_ids))]
        if exam_session_ids:
            db.query(Answer).filter(Answer.session_id.in_(exam_session_ids)).delete(synchronize_session=False)
            db.query(ExamSession).filter(ExamSession.id.in_(exam_session_ids)).delete(synchronize_session=False)
        if question_ids:
            db.query(Answer).filter(Answer.question_id.in_(question_ids)).delete(synchronize_session=False)
            db.query(Question).filter(Question.id.in_(question_ids)).delete(synchronize_session=False)
        db.query(Exam).filter(Exam.id.in_(exam_ids)).delete(synchronize_session=False)

    db.query(SchoolClass).filter(SchoolClass.teacher_id == teacher.id).delete(synchronize_session=False)
    db.query(User).filter(User.managed_by_teacher_id == teacher.id).update(
        {User.managed_by_teacher_id: None}, synchronize_session=False
    )
    set_teacher_classes(db, teacher, [])


def _delete_user_record(db: Session, current_user: User, user: User, force: bool) -> None:
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    if user.role == UserRole.admin:
        raise HTTPException(status_code=400, detail="不能删除管理员账号")
    _ensure_manage_user(current_user, user)
    if user.role == UserRole.teacher:
        if force:
            if current_user.role != UserRole.admin:
                raise HTTPException(status_code=403, detail="仅管理员可强制删除教师")
            if user.is_active:
                raise HTTPException(status_code=400, detail="只能强制删除已停用的教师")
            _purge_teacher_data(db, user)
        elif _teacher_has_teaching_data(db, user.id):
            raise HTTPException(status_code=400, detail="教师已有教学数据，请禁用账号以保留文章、考试与历史记录")
        else:
            set_teacher_classes(db, user, [])
    if user.role == UserRole.student:
        for session in list(user.exam_sessions):
            db.delete(session)
        db.query(TypingRecord).filter(TypingRecord.student_id == user.id).delete(synchronize_session=False)
        db.flush()
    db.delete(user)


@router.get("/{user_id}/panel")
def student_panel(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    student = db.query(User).filter(User.id == user_id, User.role == UserRole.student).first()
    if not student or not student_in_scope(current_user, student):
        raise HTTPException(status_code=404, detail="学生不存在")
    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text), joinedload(TypingRecord.typing_session))
        .filter(TypingRecord.student_id == student.id)
        .order_by(TypingRecord.id.desc())
        .limit(200)
        .all()
    )
    sessions = (
        db.query(ExamSession)
        .options(joinedload(ExamSession.exam))
        .filter(ExamSession.student_id == student.id)
        .order_by(ExamSession.id.desc())
        .all()
    )
    if current_user.role == UserRole.teacher:
        records = [
            record for record in records
            if (record.text is None or record.text.teacher_id in (None, current_user.id))
            and (record.typing_session is None or record.typing_session.teacher_id == current_user.id)
        ]
        sessions = [session for session in sessions if session.exam and session.exam.created_by == current_user.id]
    practice = [record for record in records if record.source == "practice"]
    tests = [record for record in records if record.source in ("test", "class_test")]
    exam_typing = [record for record in records if record.source == "exam"]
    return {
        "student": {
            "id": student.id,
            "username": student.username,
            "name": student.name,
            "class_name": student.class_name or "",
            "is_active": bool(student.is_active),
            "is_online": _is_online(student.last_seen_at),
            "last_seen_at": student.last_seen_at,
        },
        "summary": {
            "practice_count": len(practice),
            "test_count": len(tests),
            "exam_count": len(sessions),
            "avg_wpm": round(sum(record.wpm for record in practice) / len(practice), 1) if practice else 0,
            "avg_accuracy": round(sum(record.accuracy for record in practice) / len(practice), 1) if practice else 0,
            "best_wpm": max((record.wpm for record in records), default=0),
        },
        "practice_records": [_record_to_out(record).model_dump(mode="json") for record in practice],
        "test_records": [_record_to_out(record).model_dump(mode="json") for record in tests],
        "exam_typing_records": [_record_to_out(record).model_dump(mode="json") for record in exam_typing],
        "exams": [
            {
                "id": session.id,
                "exam_title": session.exam.title if session.exam else "",
                "status": session.status.value if session.status else "",
                "total_score": session.total_score,
                "max_score": session.max_score,
                "pass_score": session.exam.pass_score if session.exam else 0,
                "start_time": session.start_time,
                "submit_time": session.submit_time,
            }
            for session in sessions
        ],
    }


@router.post("/batch-delete")
def batch_delete_users(
    data: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deleted = 0
    errors: list[str] = []
    for user_id in dict.fromkeys(data.user_ids):
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            errors.append(f"账号 {user_id} 不存在")
            continue
        nested = db.begin_nested()
        try:
            _delete_user_record(db, current_user, user, data.force)
            nested.commit()
            deleted += 1
        except HTTPException as exc:
            nested.rollback()
            errors.append(f"{user.name}：{exc.detail}")
    db.commit()
    return {"deleted": deleted, "errors": errors}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    _delete_user_record(db, current_user, user, force)
    db.commit()
    return {"message": "删除成功"}
