import json

from fastapi import APIRouter, Body, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_password_hash, require_teacher
from ..database import get_db
from ..import_utils import parse_questions_text, parse_students_text
from ..models import QuestionType, User, UserRole
from ..permissions import (
    remember_class,
    resolve_student_class,
    teacher_can_manage_class,
    validate_student_teacher,
)
from ..schemas import BatchImportRequest, BatchImportResult, QuestionCreate, QuestionParseResult
from ..sync_pack import import_teacher_pack
from .users import _clean_name, _clean_username, _ensure_student_identity, _resolve_password, default_username

router = APIRouter(prefix="/api/import", tags=["批量导入"])


@router.post("/students", response_model=BatchImportResult)
def batch_import_students(
    data: BatchImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    is_admin = current_user.role == UserRole.admin
    if data.update_existing and not is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可批量更新已有学生")

    students, errors = parse_students_text(data.text, data.default_password)
    success = updated = 0
    preview = []
    imported_students: set[int] = set()

    for item in students:
        try:
            username = _clean_username(item["username"]) if item["username"] else None
            name = _clean_name(item["name"], for_student=True)
            student = db.query(User).filter(User.username == username).first() if username else None
            if student and (not data.update_existing or student.role != UserRole.student):
                raise HTTPException(status_code=400, detail=f"用户名 {username} 已存在，已跳过")

            class_name = resolve_student_class(
                current_user, item["class_name"] or (student.class_name if student else None)
            )
            if data.update_existing and username is None:
                matches = db.query(User).filter_by(role=UserRole.student, name=name, class_name=class_name).limit(2).all()
                if len(matches) > 1:
                    raise HTTPException(status_code=400, detail="同班有多个同名账号，请提供用户名以确认")
                student = matches[0] if matches else None
            if student and student.id in imported_students:
                raise HTTPException(status_code=400, detail="同一学生在本次导入中重复")
            teacher_username = item["teacher_username"]
            if not is_admin and teacher_username:
                raise HTTPException(status_code=403, detail="仅管理员可编辑学生绑定教师")

            owner_id = student.managed_by_teacher_id if student else None
            if not is_admin:
                owner_id = current_user.id
            elif teacher_username == "未绑定":
                owner_id = None
            elif teacher_username:
                teacher = db.query(User).filter(User.username == teacher_username).first()
                validate_student_teacher(teacher, class_name)
                owner_id = teacher.id
            elif student and owner_id is not None and class_name != student.class_name:
                if not teacher_can_manage_class(db.get(User, owner_id), class_name):
                    owner_id = None

            if student is None or student.is_active:
                _ensure_student_identity(db, name, class_name, exclude_id=student.id if student else None)
            new_password = None
            if student is None or item["explicit_password"]:
                password = _resolve_password(item["password"], required=False)
                new_password = get_password_hash(password)
            if student is None and username is None:
                username = default_username(db, name)
        except HTTPException as exc:
            errors.append(f"第 {item['line_no']} 行：{exc.detail}")
            continue

        if is_admin:
            remember_class(db, class_name)
        if student is None:
            student = User(username=username, role=UserRole.student)
            db.add(student)
        else:
            updated += 1
        student.name = name
        student.class_name = class_name
        student.managed_by_teacher_id = owner_id
        if new_password is not None:
            student.password_hash = new_password
            student.must_change_password = True
            student.last_seen_at = None
        db.flush()
        imported_students.add(student.id)
        success += 1
        if len(preview) < 10:
            preview.append({"username": student.username, "name": name, "class_name": class_name})

    db.commit()
    return BatchImportResult(
        success_count=success,
        fail_count=len(errors),
        updated_count=updated,
        errors=errors,
        preview=preview,
    )


@router.post("/students/file", response_model=BatchImportResult)
def batch_import_students_file(
    file: UploadFile = File(...),
    default_password: str = "123456",
    update_existing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    content = file.file.read()
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=400, detail="文件编码无法识别，请使用 UTF-8 或 GBK 编码")

    return batch_import_students(
        BatchImportRequest(text=text, default_password=default_password, update_existing=update_existing),
        db=db,
        current_user=current_user,
    )


@router.post("/questions/parse", response_model=QuestionParseResult)
def parse_questions(
    data: BatchImportRequest,
    _: User = Depends(require_teacher),
):
    parsed, errors = parse_questions_text(data.text, data.default_score)
    questions = []
    for item in parsed:
        questions.append(
            QuestionCreate(
                type=item["type"],
                content=item["content"],
                options=item["options"],
                correct_answer=item["correct_answer"],
                score=item["score"],
                order_num=item["order_num"],
            )
        )
    return QuestionParseResult(questions=questions, errors=errors)


@router.post("/questions/file", response_model=QuestionParseResult)
async def parse_questions_file(
    file: UploadFile = File(...),
    default_score: float = 10.0,
    _: User = Depends(require_teacher),
):
    content = await file.read()
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise HTTPException(status_code=400, detail="文件编码无法识别，请使用 UTF-8 或 GBK 编码")

    return parse_questions(
        BatchImportRequest(text=text, default_score=default_score),
        _=_,
    )


@router.post("/teacher-pack")
def import_teacher_data(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    return import_teacher_pack(db, current_user, payload)


@router.post("/teacher-pack/file")
async def import_teacher_data_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(status_code=400, detail="无法解析教师数据包，请使用 UTF-8 JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="教师数据包格式不正确")
    return import_teacher_pack(db, current_user, payload)
