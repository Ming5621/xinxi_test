import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session, joinedload

from ..auth import require_teacher
from ..database import get_db
from ..models import (
    Exam,
    ExamSession,
    SessionStatus,
    TypingClassSession,
    TypingClassSessionStatus,
    TypingRecord,
    User,
    UserRole,
)
from ..permissions import apply_student_scope, ensure_class_access, filter_class_name, get_assigned_classes
from ..timeutil import format_local
from ..typing_utils import DEFAULT_TYPING_CONFIG, get_typing_level, score_typing_question

router = APIRouter(prefix="/api/export", tags=["数据导出"])


def _workbook_response(wb: Workbook, filename: str) -> StreamingResponse:
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    ascii_name = "export.xlsx"
    encoded = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={ascii_name}; filename*=UTF-8''{encoded}",
        },
    )


def _sheet_title(wb: Workbook, title: str):
    sheet = wb.active
    sheet.title = title[:31]
    return sheet


@router.get("/students")
def export_students(
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    query = db.query(User)
    query = apply_student_scope(query, current_user, class_name)
    students = query.order_by(User.class_name, User.id).all()

    wb = Workbook()
    ws = _sheet_title(wb, "学生名单")
    ws.append(["用户名", "姓名", "班级", "状态", "创建时间"])
    for s in students:
        ws.append([
            s.username,
            s.name,
            s.class_name,
            "正常" if s.is_active else "禁用",
            format_local(s.created_at),
        ])
    suffix = class_name or "全部"
    return _workbook_response(wb, f"学生名单_{suffix}.xlsx")


@router.get("/exams/{exam_id}/results")
def export_exam_results(
    exam_id: int,
    class_name: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    class_name = filter_class_name(current_user, class_name)
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="考试不存在")

    sessions = (
        db.query(ExamSession)
        .options(joinedload(ExamSession.student))
        .filter(ExamSession.exam_id == exam_id)
        .all()
    )
    classes = get_assigned_classes(current_user)
    rows = []
    for s in sessions:
        stu = s.student
        if not stu:
            continue
        if classes is not None and stu.class_name not in classes:
            continue
        if class_name and stu.class_name != class_name:
            continue
        rows.append(s)

    wb = Workbook()
    ws = _sheet_title(wb, "考试成绩")
    ws.append(["考试名称", exam.title])
    ws.append(["姓名", "班级", "状态", "得分", "满分", "及格", "开始时间", "提交时间"])
    for s in rows:
        stu = s.student
        passed = s.total_score >= exam.pass_score if s.status == SessionStatus.submitted else False
        ws.append([
            stu.name,
            stu.class_name,
            "已提交" if s.status == SessionStatus.submitted else "答题中",
            s.total_score if s.status == SessionStatus.submitted else "",
            s.max_score,
            "是" if passed else ("否" if s.status == SessionStatus.submitted else ""),
            format_local(s.start_time),
            format_local(s.submit_time),
        ])
    return _workbook_response(wb, f"考试成绩_{exam.title}.xlsx")


@router.get("/typing/records")
def export_typing_records(
    class_name: str | None = None,
    student_id: int | None = None,
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
        student = db.query(User).filter(User.id == student_id, User.role == UserRole.student).first()
        if not student:
            raise HTTPException(status_code=404, detail="学生不存在")
        ensure_class_access(current_user, student.class_name)
        query = query.filter(TypingRecord.student_id == student_id)
    else:
        classes = get_assigned_classes(current_user)
        if classes is not None:
            if class_name:
                query = query.join(User).filter(User.class_name == class_name)
            else:
                query = query.join(User).filter(User.class_name.in_(classes))
        elif class_name:
            query = query.join(User).filter(User.class_name == class_name)

    records = query.limit(2000).all()
    wb = Workbook()
    summary = _sheet_title(wb, "成绩汇总")
    summary.append(["姓名", "班级", "练习次数", "平均评分", "平均速度(字/分)", "最佳速度(字/分)", "平均准确率(%)", "最近等级"])
    for row in _typing_summary_rows(db, current_user, class_name):
        summary.append([
            row["student_name"],
            row["class_name"],
            row["practice_count"],
            row["avg_score"],
            row["avg_wpm"],
            row["best_wpm"],
            row["avg_accuracy"],
            row["latest_level"],
        ])

    detail = wb.create_sheet("打字明细")
    detail.append(["姓名", "班级", "文章", "模式", "评分", "速度", "准确率", "等级", "时间"])
    source_map = {"practice": "自由练习", "test": "5分钟测试", "class_test": "课堂测试", "exam": "考试"}
    for r in records:
        stu = r.student
        detail.append([
            stu.name if stu else "",
            stu.class_name if stu else "",
            r.text.title if r.text else "自定义",
            source_map.get(r.source, r.source),
            r.score,
            r.wpm,
            r.accuracy,
            get_typing_level(r.wpm, r.accuracy, DEFAULT_TYPING_CONFIG["min_accuracy"])["level"],
            format_local(r.created_at),
        ])
    suffix = class_name or "全部"
    return _workbook_response(wb, f"打字成绩_{suffix}.xlsx")


_SESSION_STATUS = {
    TypingClassSessionStatus.pending: "待开始",
    TypingClassSessionStatus.active: "进行中",
    TypingClassSessionStatus.ended: "已结束",
}


def _typing_summary_rows(db: Session, current_user: User, class_name: str | None) -> list[dict]:
    """与打字统计页同一口径：按学生汇总最近练习。"""
    query = db.query(User).filter(User.role == UserRole.student, User.is_active == True)
    classes = get_assigned_classes(current_user)
    if classes is not None:
        if class_name:
            query = query.filter(User.class_name == class_name)
        else:
            query = query.filter(User.class_name.in_(classes))
    elif class_name:
        query = query.filter(User.class_name == class_name)
    students = query.order_by(User.class_name, User.id).all()

    rows = []
    min_accuracy = DEFAULT_TYPING_CONFIG["min_accuracy"]
    for student in students:
        recent = (
            db.query(TypingRecord)
            .filter(TypingRecord.student_id == student.id)
            .order_by(TypingRecord.id.desc())
            .limit(20)
            .all()
        )
        total_count = db.query(TypingRecord).filter(TypingRecord.student_id == student.id).count()
        if recent:
            scores = [
                record.score
                if record.score
                else score_typing_question(record.wpm, record.accuracy, 100, DEFAULT_TYPING_CONFIG)[0]
                for record in recent
            ]
            latest = recent[0]
            latest_level = get_typing_level(latest.wpm, latest.accuracy, min_accuracy)["level"]
            avg_wpm = round(sum(record.wpm for record in recent) / len(recent), 1)
            best_wpm = max(record.wpm for record in recent)
            avg_acc = round(sum(record.accuracy for record in recent) / len(recent), 1)
            avg_score = round(sum(scores) / len(scores), 1)
        else:
            avg_wpm = best_wpm = avg_acc = avg_score = 0
            latest_level = "—"
        rows.append({
            "student_name": student.name,
            "class_name": student.class_name,
            "practice_count": total_count,
            "avg_score": avg_score,
            "avg_wpm": avg_wpm,
            "best_wpm": best_wpm,
            "avg_accuracy": avg_acc,
            "latest_level": latest_level,
        })
    return rows


@router.get("/typing/sessions/{session_id}")
def export_typing_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_teacher),
):
    """导出一场课堂打字测试的全班成绩，含未提交学生。"""
    session = (
        db.query(TypingClassSession)
        .options(joinedload(TypingClassSession.text))
        .filter(TypingClassSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="测试不存在")
    ensure_class_access(current_user, session.class_name)

    records = (
        db.query(TypingRecord)
        .options(joinedload(TypingRecord.student))
        .filter(TypingRecord.typing_session_id == session.id)
        .all()
    )
    by_student = {record.student_id: record for record in records}
    students = (
        db.query(User)
        .filter(
            User.role == UserRole.student,
            User.is_active == True,
            User.class_name == session.class_name,
        )
        .order_by(User.name, User.id)
        .all()
    )
    known_ids = {student.id for student in students}
    extras = [record.student for record in records if record.student and record.student_id not in known_ids]

    title = session.title or "课堂打字测试"
    wb = Workbook()
    ws = _sheet_title(wb, "课堂测试成绩")
    ws.append(["测试名称", title])
    ws.append(["班级", session.class_name])
    ws.append(["文章", session.text.title if session.text else ""])
    ws.append(["时长(分钟)", round(session.duration_seconds / 60, 1)])
    ws.append(["状态", _SESSION_STATUS.get(session.status, str(session.status))])
    ws.append(["开始时间", format_local(session.started_at)])
    ws.append(["结束时间", format_local(session.ended_at)])
    ws.append([])
    ws.append(["姓名", "班级", "提交情况", "评分", "速度(字/分)", "准确率(%)", "等级", "用时(秒)", "正确字数", "提交时间"])

    submitted = []
    missing = []
    for student in list(students) + extras:
        record = by_student.get(student.id)
        if not record:
            missing.append([student.name, student.class_name, "未提交", "", "", "", "", "", "", ""])
            continue
        submitted.append([
            student.name,
            student.class_name,
            "已提交",
            record.score,
            record.wpm,
            record.accuracy,
            record.level or get_typing_level(record.wpm, record.accuracy, DEFAULT_TYPING_CONFIG["min_accuracy"])["level"],
            record.duration_seconds,
            record.correct_chars,
            format_local(record.created_at),
        ])
    submitted.sort(key=lambda row: (-float(row[3] or 0), row[0]))
    for row in submitted + missing:
        ws.append(row)

    safe_title = "".join(ch for ch in title if ch not in '\\/:*?"<>|').strip() or "课堂测试"
    return _workbook_response(wb, f"课堂打字成绩_{safe_title}.xlsx")
