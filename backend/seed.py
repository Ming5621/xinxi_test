"""初始化数据库种子数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.auth import get_password_hash
from app.database import Base, SessionLocal, engine
from app.models import Exam, Question, QuestionType, User, UserRole

Base.metadata.create_all(bind=engine)
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

db.close()
print("\n数据库初始化完成！")
