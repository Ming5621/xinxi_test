from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user, require_student, require_teacher
from ..database import get_db
from ..import_utils import MAX_TYPING_ARTICLES, decode_uploaded_text, parse_typing_articles
from ..models import (
    TypingClassSession,
    TypingClassSessionStatus,
    TypingDifficulty,
    TypingRecord,
    TypingText,
    User,
    UserRole,
)
from ..permissions import (
    can_manage_typing_text,
    ensure_class_access,
    filter_class_name,
    get_assigned_classes,
    teacher_ids_for_class,
)
from ..schemas import (
    TypingClassSessionCreate,
    TypingClassSessionDetail,
    TypingClassSessionOut,
    TypingRecordOut,
    TypingResultOut,
    TypingStandardsOut,
    TypingSubmitRequest,
    TypingTextCreate,
    TypingTextImportRequest,
    TypingTextImportResult,
    TypingTextOut,
    TypingTextUpdate,
)
from ..typing_utils import (
    DEFAULT_TYPING_CONFIG,
    TYPING_LEVELS,
    calculate_wpm,
    compare_text,
    get_typing_level,
    score_typing_question,
)

router = APIRouter(prefix="/api/typing", tags=["打字练习"])


@router.get("/standards", response_model=TypingStandardsOut)
def get_standards():
    return TypingStandardsOut(
        levels=TYPING_LEVELS,
        min_accuracy=95,
        description="参考中考信息技术（10字/分）及义务教育信息科技课标（30字/分、准确率95%）",
    )


def _text_to_out(text: TypingText) -> TypingTextOut:
    return TypingTextOut(
        id=text.id,
        teacher_id=text.teacher_id,
        teacher_name=text.teacher.name if text.teacher else "",
        title=text.title,
        content=text.content,
        difficulty=text.difficulty,
        char_count=text.char_count,
        time_limit=text.time_limit,
        is_active=text.is_active,
    )


def _student_visible_teacher_ids(db: Session, student: User) -> list[int]:
    return teacher_ids_for_class(db, student.class_name or "")


@router.get("/texts", response_model=list[TypingTextOut])
def list_texts(
    difficulty: TypingDifficulty | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """练习素材按教师账号隔离：教师看自己的；学生看管理其班级的教师素材。"""
    query = (
        db.query(TypingText)
        .options(joinedload(TypingText.teacher))
        .filter(TypingText.is_active == True)
    )
    if difficulty:
        query = query.filter(TypingText.difficulty == difficulty)

    if current_user.role == UserRole.admin:
        texts = query.order_by(TypingText.id).all()
    elif current_user.role == UserRole.teacher:
        texts = query.filter(TypingText.teacher_id == current_user.id).order_by(TypingText.id).all()
    else:
        teacher_ids = _student_visible_teacher_ids(db, current_user)
        if not teacher_ids:
            return []
        texts = query.filter(TypingText.teacher_id.in_(teacher_ids)).order_by(TypingText.id).all()
    return [_text_to_out(t) for t in texts]


@router.post("/texts", response_model=TypingTextOut)
def create_text(
    data: TypingTextCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    owner_id = current_user.id
    content = data.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="练习内容不能为空")
    text = TypingText(
        teacher_id=owner_id,
        title=data.title.strip(),
        content=content,
        difficulty=data.difficulty,
        char_count=len(content),
        time_limit=data.time_limit,
    )
    db.add(text)
    db.commit()
    text = (
        db.query(TypingText)
        .options(joinedload(TypingText.teacher))
        .filter(TypingText.id == text.id)
        .first()
    )
    return _text_to_out(text)


@router.put("/texts/{text_id}", response_model=TypingTextOut)
def update_text(
    text_id: int,
    data: TypingTextUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    text = (
        db.query(TypingText)
        .options(joinedload(TypingText.teacher))
        .filter(TypingText.id == text_id)
        .first()
    )
    if not text or not text.is_active:
        raise HTTPException(status_code=404, detail="素材不存在")
    if not can_manage_typing_text(current_user, text):
        raise HTTPException(status_code=403, detail="只能管理自己创建的练习内容")

    if data.title is not None:
        text.title = data.title.strip()
    if data.content is not None:
        content = data.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="练习内容不能为空")
        text.content = content
        text.char_count = len(content)
    if data.difficulty is not None:
        text.difficulty = data.difficulty
    if data.time_limit is not None:
        text.time_limit = data.time_limit
    db.commit()
    db.refresh(text)
    return _text_to_out(text)


@router.delete("/texts/{text_id}")
def delete_text(
    text_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    text = db.query(TypingText).filter(TypingText.id == text_id).first()
    if not text:
        raise HTTPException(status_code=404, detail="素材不存在")
    if not can_manage_typing_text(current_user, text):
        raise HTTPException(status_code=403, detail="只能管理自己创建的练习内容")
    text.is_active = False
    db.commit()
    return {"message": "已删除"}


_TEXT_FILE_SUFFIXES = {".txt", ".csv", ".tsv", ".text"}
_MAX_IMPORT_BYTES = 2 * 1024 * 1024


def _check_import_time_limit(time_limit: int) -> None:
    if time_limit < 30 or time_limit > 600:
        raise HTTPException(status_code=400, detail="建议时长需在 30 到 600 秒之间")


def _filename_stem(filename: str | None) -> str:
    name = Path(filename or "").name
    if not name:
        return ""
    return Path(name).stem.strip()


def _save_imported_articles(
    db: Session,
    owner: User,
    text: str,
    default_title: str,
    difficulty: TypingDifficulty,
    time_limit: int,
) -> TypingTextImportResult:
    _check_import_time_limit(time_limit)
    articles, errors = parse_typing_articles(
        text,
        default_title=default_title,
        default_difficulty=difficulty,
        default_time_limit=time_limit,
    )
    if len(articles) > MAX_TYPING_ARTICLES:
        extra = len(articles) - MAX_TYPING_ARTICLES
        errors.append(f"一次最多导入 {MAX_TYPING_ARTICLES} 篇，已忽略其余 {extra} 篇")
        articles = articles[:MAX_TYPING_ARTICLES]

    created_ids: list[int] = []
    for item in articles:
        row = TypingText(
            teacher_id=owner.id,
            title=item["title"],
            content=item["content"],
            difficulty=item["difficulty"],
            char_count=len(item["content"]),
            time_limit=item["time_limit"],
        )
        db.add(row)
        db.flush()
        created_ids.append(row.id)
    db.commit()

    rows: list[TypingText] = []
    if created_ids:
        rows = (
            db.query(TypingText)
            .options(joinedload(TypingText.teacher))
            .filter(TypingText.id.in_(created_ids))
            .order_by(TypingText.id)
            .all()
        )
    return TypingTextImportResult(
        success_count=len(rows),
        fail_count=len(errors),
        errors=errors,
        texts=[_text_to_out(row) for row in rows],
    )


@router.post("/texts/import", response_model=TypingTextImportResult)
def import_texts(
    data: TypingTextImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """粘贴导入一篇或多篇打字文章，归属当前教师。"""
    return _save_imported_articles(
        db,
        current_user,
        data.text,
        data.title.strip(),
        data.difficulty,
        data.time_limit,
    )


@router.post("/texts/import/file", response_model=TypingTextImportResult)
async def import_texts_file(
    file: UploadFile = File(...),
    title: str = "",
    difficulty: TypingDifficulty = TypingDifficulty.basic,
    time_limit: int = 120,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """上传 txt / csv / tsv 导入打字文章。纯文本文件名作为单篇标题。"""
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix and suffix not in _TEXT_FILE_SUFFIXES:
        raise HTTPException(status_code=400, detail="仅支持 .txt / .csv / .tsv 文件")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="文件内容为空")
    if len(raw) > _MAX_IMPORT_BYTES:
        raise HTTPException(status_code=400, detail="文件不能超过 2MB")
    try:
        text = decode_uploaded_text(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    default_title = title.strip() or _filename_stem(filename)
    return _save_imported_articles(db, current_user, text, default_title, difficulty, time_limit)


def _session_to_out(session: TypingClassSession, db: Session) -> TypingClassSessionOut:
    participant_count = (
        db.query(User)
        .filter(User.role == UserRole.student, User.class_name == session.class_name, User.is_active == True)
        .count()
    )
    submitted_count = (
        db.query(TypingRecord).filter(TypingRecord.typing_session_id == session.id).count()
    )
    return TypingClassSessionOut(
        id=session.id,
        teacher_id=session.teacher_id,
        teacher_name=session.teacher.name if session.teacher else "",
        text_id=session.text_id,
        text_title=session.text.title if session.text else "",
        class_name=session.class_name,
        title=session.title or (session.text.title if session.text else "课堂打字测试"),
        status=session.status,
        duration_seconds=session.duration_seconds,
        started_at=session.started_at,
        ended_at=session.ended_at,
        created_at=session.created_at,
        participant_count=participant_count,
        submitted_count=submitted_count,
    )


@router.get("/sessions", response_model=list[TypingClassSessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    query = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .order_by(TypingClassSession.id.desc())
    )
    classes = get_assigned_classes(current_user)
    if classes is not None:
        if not classes:
            return []
        query = query.filter(TypingClassSession.class_name.in_(classes))
    sessions = query.limit(50).all()
    return [_session_to_out(s, db) for s in sessions]


@router.get("/sessions/active", response_model=TypingClassSessionOut | None)
def active_session_for_student(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(
            TypingClassSession.class_name == current_user.class_name,
            TypingClassSession.status == TypingClassSessionStatus.active,
        )
        .order_by(TypingClassSession.id.desc())
        .first()
    )
    if not session:
        return None
    return _session_to_out(session, db)


@router.get("/sessions/{session_id}", response_model=TypingClassSessionDetail)
def session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    if current_user.role == UserRole.student:
        if session.class_name != current_user.class_name:
            raise HTTPException(status_code=403, detail="无权查看")
    else:
        ensure_class_access(current_user, session.class_name)

    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .filter(TypingRecord.typing_session_id == session_id)
        .order_by(TypingRecord.score.desc())
        .all()
    )
    out = _session_to_out(session, db)
    return TypingClassSessionDetail(**out.model_dump(), records=[_record_to_out(r) for r in records])


@router.post("/sessions", response_model=TypingClassSessionOut)
def create_session(
    data: TypingClassSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    ensure_class_access(current_user, data.class_name)
    text = db.query(TypingText).filter(TypingText.id == data.text_id, TypingText.is_active == True).first()
    if not text:
        raise HTTPException(status_code=404, detail="文章不存在")
    if not can_manage_typing_text(current_user, text):
        raise HTTPException(status_code=403, detail="只能使用自己创建的练习文章发起课堂测试")
    active = (
        db.query(TypingClassSession)
        .filter(
            TypingClassSession.class_name == data.class_name,
            TypingClassSession.status == TypingClassSessionStatus.active,
        )
        .first()
    )
    if active:
        raise HTTPException(status_code=400, detail="该班级已有进行中的打字测试")

    session = TypingClassSession(
        teacher_id=current_user.id,
        text_id=data.text_id,
        class_name=data.class_name,
        title=data.title or f"{data.class_name} · 5分钟打字测试",
        duration_seconds=data.duration_seconds,
        status=TypingClassSessionStatus.pending,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session.id)
        .first()
    )
    return _session_to_out(session, db)


@router.post("/sessions/{session_id}/start", response_model=TypingClassSessionOut)
def start_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    ensure_class_access(current_user, session.class_name)
    if session.status != TypingClassSessionStatus.pending:
        raise HTTPException(status_code=400, detail="测试状态不允许开始")
    session.status = TypingClassSessionStatus.active
    session.started_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_out(session, db)


@router.post("/sessions/{session_id}/end", response_model=TypingClassSessionOut)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.teacher), joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    ensure_class_access(current_user, session.class_name)
    if session.status != TypingClassSessionStatus.active:
        raise HTTPException(status_code=400, detail="测试未在进行中")
    session.status = TypingClassSessionStatus.ended
    session.ended_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return _session_to_out(session, db)


@router.post("/submit", response_model=TypingResultOut)
def submit_typing(
    data: TypingSubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    typing_session = None
    source = data.source
    if data.typing_session_id:
        typing_session = db.query(TypingClassSession).filter(TypingClassSession.id == data.typing_session_id).first()
        if not typing_session:
            raise HTTPException(status_code=404, detail="课堂测试不存在")
        if typing_session.class_name != current_user.class_name:
            raise HTTPException(status_code=403, detail="无权参加该测试")
        if typing_session.status != TypingClassSessionStatus.active:
            raise HTTPException(status_code=400, detail="课堂测试未在进行中")
        existing = (
            db.query(TypingRecord)
            .filter(
                TypingRecord.typing_session_id == typing_session.id,
                TypingRecord.student_id == current_user.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="您已提交过本次测试")
        source = "class_test"

    reference_text = data.reference_text
    if data.text_id:
        text = db.query(TypingText).filter(TypingText.id == data.text_id, TypingText.is_active == True).first()
        if not text:
            raise HTTPException(status_code=404, detail="练习文章不存在")
        visible_teachers = _student_visible_teacher_ids(db, current_user)
        if text.teacher_id not in visible_teachers and not typing_session:
            raise HTTPException(status_code=403, detail="无权练习该文章")
        # 课堂测试允许使用本场指定文章
        if typing_session and text.id != typing_session.text_id:
            raise HTTPException(status_code=403, detail="课堂测试文章不匹配")
        reference_text = text.content

    comparison = compare_text(reference_text, data.typed_text)
    wpm = calculate_wpm(comparison["correct_chars"], data.duration_seconds)
    level_info = get_typing_level(wpm)
    score, passed, remark = score_typing_question(
        wpm, comparison["accuracy"], 100, DEFAULT_TYPING_CONFIG
    )

    record = TypingRecord(
        student_id=current_user.id,
        text_id=data.text_id,
        typing_session_id=typing_session.id if typing_session else None,
        source=source,
        reference_text=reference_text,
        typed_text=data.typed_text,
        duration_seconds=data.duration_seconds,
        wpm=wpm,
        accuracy=comparison["accuracy"],
        correct_chars=comparison["correct_chars"],
        level=level_info["level"],
        score=score,
    )
    db.add(record)
    db.commit()

    return TypingResultOut(
        wpm=wpm,
        accuracy=comparison["accuracy"],
        correct_chars=comparison["correct_chars"],
        error_chars=comparison["error_chars"],
        total_chars=comparison["total_chars"],
        level=level_info["level"],
        level_desc=level_info["desc"],
        passed=passed,
        score=score,
        remark=remark,
    )


def _record_to_out(record: TypingRecord) -> TypingRecordOut:
    title = record.text.title if record.text else "自定义练习"
    score = record.score
    if score is None:
        score, _, _ = score_typing_question(record.wpm, record.accuracy, 100, DEFAULT_TYPING_CONFIG)
    return TypingRecordOut(
        id=record.id,
        student_id=record.student_id,
        student_name=record.student.name if record.student else "",
        class_name=record.student.class_name if record.student else "",
        text_id=record.text_id,
        text_title=title,
        source=record.source,
        wpm=record.wpm,
        accuracy=record.accuracy,
        correct_chars=record.correct_chars,
        level=record.level,
        duration_seconds=record.duration_seconds,
        score=score,
        created_at=record.created_at,
    )


@router.get("/records/my", response_model=list[TypingRecordOut])
def my_records(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_student),
):
    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .filter(TypingRecord.student_id == current_user.id)
        .order_by(TypingRecord.id.desc())
        .limit(limit)
        .all()
    )
    return [_record_to_out(r) for r in records]


@router.get("/records", response_model=list[TypingRecordOut])
def list_records(
    student_id: int | None = None,
    class_name: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    query = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student), joinedload(TypingRecord.text))
        .order_by(TypingRecord.id.desc())
    )
    if student_id:
        student = db.query(User).filter(User.id == student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
        ensure_class_access(current_user, student.class_name)
        query = query.filter(TypingRecord.student_id == student_id)
    elif class_name:
        query = query.join(User).filter(User.class_name == class_name)
    else:
        classes = get_assigned_classes(current_user)
        if classes is not None:
            query = query.join(User).filter(User.class_name.in_(classes))
    return [_record_to_out(r) for r in query.limit(limit).all()]


@router.get("/records/stats")
def class_stats(
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    q = db.query(User).filter(User.role == UserRole.student, User.is_active == True)
    classes = get_assigned_classes(current_user)
    if classes is not None:
        if class_name:
            q = q.filter(User.class_name == class_name)
        else:
            q = q.filter(User.class_name.in_(classes))
    elif class_name:
        q = q.filter(User.class_name == class_name)
    students = q.order_by(User.class_name, User.id).all()

    stats = []
    for s in students:
        records = (
            db.query(TypingRecord)
            .filter(TypingRecord.student_id == s.id)
            .order_by(TypingRecord.id.desc())
            .limit(20)
            .all()
        )
        if records:
            avg_wpm = round(sum(r.wpm for r in records) / len(records), 1)
            best_wpm = max(r.wpm for r in records)
            avg_acc = round(sum(r.accuracy for r in records) / len(records), 1)
            scores = [
                r.score if r.score else score_typing_question(r.wpm, r.accuracy, 100, DEFAULT_TYPING_CONFIG)[0]
                for r in records
            ]
            avg_score = round(sum(scores) / len(scores), 1)
            latest_level = records[0].level
            total_count = db.query(TypingRecord).filter(TypingRecord.student_id == s.id).count()
        else:
            avg_wpm = best_wpm = avg_acc = avg_score = 0
            latest_level = "—"
            total_count = 0
        stats.append({
            "student_id": s.id,
            "student_name": s.name,
            "class_name": s.class_name,
            "practice_count": total_count,
            "avg_wpm": avg_wpm,
            "best_wpm": best_wpm,
            "avg_accuracy": avg_acc,
            "avg_score": avg_score,
            "latest_level": latest_level,
        })
    return stats
