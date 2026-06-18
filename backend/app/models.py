import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from .database import Base


class UserRole(str, enum.Enum):
    teacher = "teacher"
    student = "student"


class ExamStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    ended = "ended"


class QuestionType(str, enum.Enum):
    choice = "choice"
    judge = "judge"
    typing = "typing"


class TypingDifficulty(str, enum.Enum):
    beginner = "beginner"
    basic = "basic"
    standard = "standard"
    advanced = "advanced"


class SessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    submitted = "submitted"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.student)
    class_name = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)

    exam_sessions = relationship("ExamSession", back_populates="student")


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    duration_minutes = Column(Integer, default=60)
    status = Column(Enum(ExamStatus), default=ExamStatus.draft)
    pass_score = Column(Float, default=60.0)
    created_by = Column(Integer, ForeignKey("users.id"))
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    questions = relationship(
        "Question", back_populates="exam", cascade="all, delete-orphan", order_by="Question.order_num"
    )
    sessions = relationship("ExamSession", back_populates="exam", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    type = Column(Enum(QuestionType), nullable=False)
    content = Column(Text, nullable=False)
    options = Column(JSON, default=list)
    correct_answer = Column(String(10), nullable=False)
    score = Column(Float, default=5.0)
    order_num = Column(Integer, default=0)

    exam = relationship("Exam", back_populates="questions")
    answers = relationship("Answer", back_populates="question")


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(SessionStatus), default=SessionStatus.in_progress)
    start_time = Column(DateTime, default=datetime.utcnow)
    submit_time = Column(DateTime, nullable=True)
    total_score = Column(Float, default=0.0)
    max_score = Column(Float, default=0.0)

    exam = relationship("Exam", back_populates="sessions")
    student = relationship("User", back_populates="exam_sessions")
    answers = relationship("Answer", back_populates="session", cascade="all, delete-orphan")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    student_answer = Column(Text, default="")
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    answer_meta = Column(JSON, default=dict)

    session = relationship("ExamSession", back_populates="answers")
    question = relationship("Question", back_populates="answers")


class TypingText(Base):
    """打字练习素材库"""
    __tablename__ = "typing_texts"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    difficulty = Column(Enum(TypingDifficulty), default=TypingDifficulty.basic)
    char_count = Column(Integer, default=0)
    time_limit = Column(Integer, default=120)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TypingRecord(Base):
    """打字练习/测试记录"""
    __tablename__ = "typing_records"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text_id = Column(Integer, ForeignKey("typing_texts.id"), nullable=True)
    source = Column(String(20), default="practice")  # practice / exam
    reference_text = Column(Text, nullable=False)
    typed_text = Column(Text, default="")
    duration_seconds = Column(Float, default=0)
    wpm = Column(Float, default=0)
    accuracy = Column(Float, default=0)
    correct_chars = Column(Integer, default=0)
    level = Column(String(20), default="")
    score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    student = relationship("User")
    text = relationship("TypingText")
