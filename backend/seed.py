"""初始化数据库种子数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import inspect, text

from app.database import Base, SessionLocal, engine
from app.models import Exam, Question, QuestionType, TypingDifficulty, TypingText, User, UserRole

SHARED_CLASS = "课堂"
TEACHER_ACCOUNTS = [
    ("teacher1", "张老师", "teacher123"),
    ("teacher2", "李老师", "teacher123"),
    ("teacher3", "王老师", "teacher123"),
    ("teacher4", "赵老师", "teacher123"),
]

# 预计算默认账号 bcrypt，避免每次冷启动现场哈希（约 1s+）拖慢服务就绪
_PRESET_PASSWORD_HASHES = {
    "admin123": "$2b$12$d1vTzB584EoAKE1.TridKeo5oeiogLewOzvEvgcJ2NurZHrAACgai",
    "teacher123": "$2b$12$JsI./nAuJBzSO7qIw.kS1eyaag9z67ri9MgDYqJi9baGzpNFm1MvK",
}


def _password_hash(password: str) -> str:
    preset = _PRESET_PASSWORD_HASHES.get(password)
    if preset:
        return preset
    from app.auth import get_password_hash

    return get_password_hash(password)


def _migrate_schema() -> None:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "answers" in tables:
        cols = {c["name"] for c in inspector.get_columns("answers")}
        with engine.begin() as conn:
            if "answer_meta" not in cols:
                conn.execute(text("ALTER TABLE answers ADD COLUMN answer_meta JSON DEFAULT '{}'"))

    if "users" in tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "last_seen_at" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_seen_at DATETIME"))
            if "assigned_classes" not in user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN assigned_classes JSON DEFAULT '[]'"))

    if "typing_records" in tables:
        typing_cols = {c["name"] for c in inspector.get_columns("typing_records")}
        with engine.begin() as conn:
            if "score" not in typing_cols:
                conn.execute(text("ALTER TABLE typing_records ADD COLUMN score FLOAT DEFAULT 0"))
            if "typing_session_id" not in typing_cols:
                conn.execute(text("ALTER TABLE typing_records ADD COLUMN typing_session_id INTEGER"))

    if "typing_texts" in tables:
        text_cols = {c["name"] for c in inspector.get_columns("typing_texts")}
        with engine.begin() as conn:
            if "teacher_id" not in text_cols:
                conn.execute(text("ALTER TABLE typing_texts ADD COLUMN teacher_id INTEGER"))


def run_seed(*, quiet: bool = False) -> None:
    """创建/迁移数据库并填充默认账号与示例数据。可重复调用，已初始化时几乎瞬时返回。"""
    Base.metadata.create_all(bind=engine)
    _migrate_schema()

    db = SessionLocal()
    changed = False

    try:
        if db.query(User).filter(User.username == "admin").first() is None:
            db.add(
                User(
                    username="admin",
                    password_hash=_password_hash("admin123"),
                    name="系统管理员",
                    role=UserRole.admin,
                    assigned_classes=[],
                )
            )
            db.commit()
            changed = True
            if not quiet:
                print("✓ 创建管理员账号: admin / admin123")

        for username, name, password in TEACHER_ACCOUNTS:
            existing = db.query(User).filter(User.username == username).first()
            if existing is None:
                db.add(
                    User(
                        username=username,
                        password_hash=_password_hash(password),
                        name=name,
                        role=UserRole.teacher,
                        assigned_classes=[SHARED_CLASS],
                    )
                )
                changed = True
                if not quiet:
                    print(f"✓ 创建教师账号: {username} / {password} ({name})")
            else:
                need = False
                if existing.role != UserRole.teacher:
                    existing.role = UserRole.teacher
                    need = True
                if existing.name != name:
                    existing.name = name
                    need = True
                if existing.assigned_classes != [SHARED_CLASS]:
                    existing.assigned_classes = [SHARED_CLASS]
                    need = True
                if not existing.is_active:
                    existing.is_active = True
                    need = True
                if need:
                    changed = True
                    if not quiet:
                        print(f"✓ 更新教师账号: {username} → 管理「{SHARED_CLASS}」")

        for old_name in ("teacher", "teacher2"):
            old = db.query(User).filter(User.username == old_name).first()
            if old and old.role == UserRole.teacher and old.assigned_classes != [SHARED_CLASS]:
                old.assigned_classes = [SHARED_CLASS]
                changed = True
                if not quiet:
                    print(f"✓ 兼容旧账号 {old_name}：班级改为「{SHARED_CLASS}」")

        if changed:
            db.commit()

        teachers = (
            db.query(User)
            .filter(User.role == UserRole.teacher, User.username.in_([t[0] for t in TEACHER_ACCOUNTS]))
            .order_by(User.username)
            .all()
        )
        primary_teacher = teachers[0] if teachers else db.query(User).filter(User.role == UserRole.teacher).first()

        orphans = db.query(TypingText).filter(TypingText.teacher_id.is_(None)).all()
        if orphans and primary_teacher:
            for t in orphans:
                t.teacher_id = primary_teacher.id
            db.commit()
            if not quiet:
                print(f"✓ 已将 {len(orphans)} 篇旧练习素材绑定到 {primary_teacher.username}")

        if db.query(TypingText).count() == 0 and teachers:
            samples = [
                ("入门练习 — 键盘指法", "aaaa ssss dddd ffff jjjj kkkk llll ;;;; 中中中中 国国国国 人人人人", TypingDifficulty.beginner, 60),
                ("基础练习 — 信息技术词汇", "计算机 键盘 鼠标 显示器 主机 软件 硬件 网络 浏览器 文件夹 复制 粘贴 删除 保存 打印", TypingDifficulty.basic, 90),
                ("达标练习 — 中考模拟", "信息技术是一门研究信息获取、存储、传输和处理的学科。计算机由硬件系统和软件系统组成。操作系统是管理计算机硬件与软件资源的系统软件。", TypingDifficulty.standard, 120),
                ("进阶练习 — 课文段落", "科学技术的飞速发展，使计算机网络成为人们生活中不可缺少的工具。通过网络，我们可以获取丰富的学习资源，与世界各地的人进行交流。作为新时代的中学生，我们应该掌握基本的信息技术技能，培养良好的信息素养。", TypingDifficulty.advanced, 180),
            ]
            for owner in teachers:
                for title, content, diff, limit in samples:
                    db.add(
                        TypingText(
                            teacher_id=owner.id,
                            title=title,
                            content=content,
                            difficulty=diff,
                            char_count=len(content),
                            time_limit=limit,
                        )
                    )
            db.commit()
            if not quiet:
                print(f"✓ 创建打字练习素材 {len(samples) * len(teachers)} 篇（已按教师账号绑定）")

        if db.query(Exam).count() == 0 and primary_teacher:
            exam = Exam(
                title="计算机基础知识测验",
                description="本次考试涵盖计算机硬件、操作系统及网络基础知识，包含选择题和判断题。",
                duration_minutes=45,
                pass_score=30,
                created_by=primary_teacher.id,
            )
            db.add(exam)
            db.flush()

            questions = [
                Question(
                    exam_id=exam.id,
                    type=QuestionType.choice,
                    content="以下哪个是计算机的中央处理器？",
                    options=["A. 内存", "B. CPU", "C. 硬盘", "D. 显卡"],
                    correct_answer="B",
                    score=10,
                    order_num=0,
                ),
                Question(
                    exam_id=exam.id,
                    type=QuestionType.choice,
                    content="操作系统的主要功能不包括以下哪项？",
                    options=["A. 进程管理", "B. 内存管理", "C. 文字排版", "D. 文件管理"],
                    correct_answer="C",
                    score=10,
                    order_num=1,
                ),
                Question(
                    exam_id=exam.id,
                    type=QuestionType.judge,
                    content="RAM（随机存取存储器）在断电后数据不会丢失。",
                    options=["正确", "错误"],
                    correct_answer="错误",
                    score=10,
                    order_num=2,
                ),
                Question(
                    exam_id=exam.id,
                    type=QuestionType.judge,
                    content="TCP/IP 是互联网通信的基础协议族。",
                    options=["正确", "错误"],
                    correct_answer="正确",
                    score=10,
                    order_num=3,
                ),
                Question(
                    exam_id=exam.id,
                    type=QuestionType.choice,
                    content="1GB 等于多少 MB？",
                    options=["A. 100", "B. 512", "C. 1024", "D. 2048"],
                    correct_answer="C",
                    score=10,
                    order_num=4,
                ),
            ]
            for q in questions:
                db.add(q)

            db.commit()
            if not quiet:
                print("✓ 创建示例考试: 计算机基础知识测验（草稿状态）")

        if db.query(Exam).filter(Exam.title == "初中信息技术打字测试").first() is None and primary_teacher:
            typing_exam = Exam(
                title="初中信息技术打字测试",
                description="参考中考信息技术及义务教育信息科技课标。达标：10字/分；良好：20字/分；优秀：30字/分；卓越：40字/分。准确率需≥95%。",
                duration_minutes=15,
                pass_score=11,
                created_by=primary_teacher.id,
            )
            db.add(typing_exam)
            db.flush()

            typing_content = "信息技术是一门基础学科。计算机由硬件和软件组成。操作系统管理计算机资源。学生应掌握打字技能，提高学习效率。"
            db.add(
                Question(
                    exam_id=typing_exam.id,
                    type=QuestionType.typing,
                    content=typing_content,
                    options={
                        "time_limit": 120,
                        "min_wpm": 10,
                        "pass_wpm": 20,
                        "excellent_wpm": 30,
                        "min_accuracy": 95,
                    },
                    correct_answer=typing_content,
                    score=18,
                    order_num=0,
                )
            )
            db.commit()
            if not quiet:
                print("✓ 创建打字测试考试: 初中信息技术打字测试（草稿状态）")

        if not quiet:
            print("\n数据库初始化完成！")
            print("教师账号: teacher1~teacher4 / teacher123")
            print("学生: 登录页输入姓名即可（无需预设账号）")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
