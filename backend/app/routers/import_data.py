from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_password_hash, require_teacher
from ..database import get_db
from ..import_utils import parse_questions_text, parse_students_text
from ..models import QuestionType, User, UserRole
from ..schemas import BatchImportRequest, BatchImportResult, QuestionCreate, QuestionParseResult

router = APIRouter(prefix="/api/import", tags=["批量导入"])


@router.post("/students", response_model=BatchImportResult)
def batch_import_students(
    data: BatchImportRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_teacher),
):
    students, parse_errors = parse_students_text(data.text, data.default_password)
    if not students and parse_errors:
        return BatchImportResult(success_count=0, fail_count=0, errors=parse_errors)

    success = 0
    errors = list(parse_errors)

    for item in students:
        existing = db.query(User).filter(User.username == item["username"]).first()
        if existing:
            errors.append(f"用户名 {item['username']} 已存在，已跳过")
            continue
        user = User(
            username=item["username"],
            password_hash=get_password_hash(item["password"]),
            name=item["name"],
            role=UserRole.student,
            class_name=item.get("class_name", ""),
        )
        db.add(user)
        success += 1

    db.commit()
    return BatchImportResult(
        success_count=success,
        fail_count=len(students) - success,
        errors=errors,
        preview=students[:10],
    )


@router.post("/students/file", response_model=BatchImportResult)
async def batch_import_students_file(
    file: UploadFile = File(...),
    default_password: str = "123456",
    db: Session = Depends(get_db),
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

    return batch_import_students(
        BatchImportRequest(text=text, default_password=default_password),
        db=db,
        _=_,
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
