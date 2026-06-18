"""初始化数据库种子数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import inspect, text

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import Exam, ExamStatus, Question, QuestionType, TypingDifficulty, TypingText, User, UserRole

Base.metadata.create_all(bind=engine)

# 兼容旧数据库：补充新增字段
inspector = inspect(engine)
if "answers" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("answers")}
    with engine.begin() as conn:
        if "answer_meta" not in cols:
            conn.execute(text("ALTER TABLE answers ADD COLUMN answer_meta JSON DEFAULT '{}'"))
        if "student_answer" in cols:
            # SQLite 无法直接改类型，新库会直接用 Text
            pass

if "users" in inspector.get_table_names():
    user_cols = {c["name"] for c in inspector.get_columns("users")}
    with engine.begin() as conn:
        if "last_seen_at" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_seen_at DATETIME"))

db = SessionLocal()

if db.query(User).filter(User.username == "teacher").first() is None:
    teacher = User(
        username="teacher",
        password_hash=get_password_hash("teacher123"),
        name="张老师",
        role=UserRole.teacher,
    )
    db.add(teacher)
    db.commit()
    print("✓ 创建教师账号: teacher / teacher123")

students_data = [
    ("student01", "李明", "微机1班"),
    ("student02", "王芳", "微机1班"),
    ("student03", "赵强", "微机1班"),
    ("student04", "刘洋", "微机2班"),
    ("student05", "陈静", "微机2班"),
]

for username, name, class_name in students_data:
    if db.query(User).filter(User.username == username).first() is None:
        db.add(
            User(
                username=username,
                password_hash=get_password_hash("123456"),
                name=name,
                role=UserRole.student,
                class_name=class_name,
            )
        )
        print(f"✓ 创建学生账号: {username} / 123456 ({name})")

db.commit()

# 打字练习素材
if db.query(TypingText).count() == 0:
    typing_texts = [
        TypingText(
            title="入门练习 — 键盘指法",
            content="aaaa ssss dddd ffff jjjj kkkk llll ;;;; 中中中中 国国国国 人人人人",
            difficulty=TypingDifficulty.beginner,
            time_limit=60,
        ),
        TypingText(
            title="基础练习 — 信息技术词汇",
            content="计算机 键盘 鼠标 显示器 主机 软件 硬件 网络 浏览器 文件夹 复制 粘贴 删除 保存 打印",
            difficulty=TypingDifficulty.basic,
            time_limit=90,
        ),
        TypingText(
            title="达标练习 — 中考模拟",
            content="信息技术是一门研究信息获取、存储、传输和处理的学科。计算机由硬件系统和软件系统组成。操作系统是管理计算机硬件与软件资源的系统软件。",
            difficulty=TypingDifficulty.standard,
            time_limit=120,
        ),
        TypingText(
            title="进阶练习 — 课文段落",
            content="科学技术的飞速发展，使计算机网络成为人们生活中不可缺少的工具。通过网络，我们可以获取丰富的学习资源，与世界各地的人进行交流。作为新时代的中学生，我们应该掌握基本的信息技术技能，培养良好的信息素养。",
            difficulty=TypingDifficulty.advanced,
            time_limit=180,
        ),
    ]
    for t in typing_texts:
        t.char_count = len(t.content)
        db.add(t)
    db.commit()
    print("✓ 创建打字练习素材 4 篇")

if db.query(Exam).count() == 0:
    teacher = db.query(User).filter(User.username == "teacher").first()
    exam = Exam(
        title="计算机基础知识测验",
        description="本次考试涵盖计算机硬件、操作系统及网络基础知识，包含选择题和判断题。",
        duration_minutes=45,
        pass_score=60,
        created_by=teacher.id,
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
    print("✓ 创建示例考试: 计算机基础知识测验（草稿状态）")

# 打字测试专项考试
if db.query(Exam).filter(Exam.title == "初中信息技术打字测试").first() is None:
    teacher = db.query(User).filter(User.username == "teacher").first()
    typing_exam = Exam(
        title="初中信息技术打字测试",
        description="参考中考信息技术及义务教育信息科技课标。达标：10字/分；良好：20字/分；优秀：30字/分；卓越：40字/分。准确率需≥95%。",
        duration_minutes=15,
        pass_score=60,
        created_by=teacher.id,
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
    print("✓ 创建打字测试考试: 初中信息技术打字测试（草稿状态）")

db.close()
print("\n数据库初始化完成！")
