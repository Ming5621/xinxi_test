from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .models import ExamStatus, QuestionType, SessionStatus, TypingDifficulty, UserRole


# Auth
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# User
class UserBase(BaseModel):
    username: str
    name: str
    role: UserRole = UserRole.student
    class_name: str = ""


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# Question
class QuestionBase(BaseModel):
    type: QuestionType
    content: str
    options: Any = []
    correct_answer: str = ""
    score: float = 5.0
    order_num: int = 0


class QuestionCreate(QuestionBase):
    pass


class QuestionOut(QuestionBase):
    id: int
    exam_id: int

    model_config = {"from_attributes": True}


class QuestionStudentOut(BaseModel):
    id: int
    type: QuestionType
    content: str
    options: Any = []
    score: float
    order_num: int
    typing_config: Optional[dict] = None

    model_config = {"from_attributes": True}


# Exam
class ExamBase(BaseModel):
    title: str
    description: str = ""
    duration_minutes: int = 60
    pass_score: float = 60.0


class ExamCreate(ExamBase):
    questions: list[QuestionCreate] = []


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    pass_score: Optional[float] = None
    status: Optional[ExamStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: Optional[list[QuestionCreate]] = None


class ExamOut(ExamBase):
    id: int
    status: ExamStatus
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    created_at: datetime
    question_count: int = 0
    total_score: float = 0.0

    model_config = {"from_attributes": True}


class ExamDetailOut(ExamOut):
    questions: list[QuestionOut] = []


# Session & Answer
class AnswerSubmit(BaseModel):
    question_id: int
    student_answer: str = ""
    answer_meta: Optional[dict] = None


class ExamSubmitRequest(BaseModel):
    answers: list[AnswerSubmit]


class AnswerOut(BaseModel):
    question_id: int
    student_answer: str
    is_correct: bool
    score: float
    correct_answer: Optional[str] = None
    question_content: Optional[str] = None
    answer_meta: Optional[dict] = None

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: int
    exam_id: int
    exam_title: str = ""
    student_id: int
    student_name: str = ""
    class_name: str = ""
    status: SessionStatus
    start_time: datetime
    submit_time: Optional[datetime]
    total_score: float
    max_score: float
    pass_score: float = 60.0
    is_passed: bool = False

    model_config = {"from_attributes": True}


class SessionDetailOut(SessionOut):
    answers: list[AnswerOut] = []


# Statistics
class QuestionStat(BaseModel):
    question_id: int
    content: str
    type: QuestionType
    correct_count: int
    total_count: int
    correct_rate: float


class ExamStatistics(BaseModel):
    exam_id: int
    exam_title: str
    total_students: int
    submitted_count: int
    average_score: float
    max_score: float
    min_score: float
    pass_count: int
    pass_rate: float
    total_possible_score: float
    question_stats: list[QuestionStat]
    score_distribution: dict[str, int]


class DashboardStats(BaseModel):
    total_students: int
    online_students: int
    total_exams: int
    active_exams: int
    completed_sessions: int


class StudentPresenceOut(BaseModel):
    id: int
    username: str
    name: str
    class_name: str
    is_active: bool
    is_online: bool
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PresenceSummary(BaseModel):
    total_students: int
    online_students: int
    offline_students: int
    online_threshold_seconds: int


# Import
class BatchImportRequest(BaseModel):
    text: str
    default_password: str = "123456"
    default_score: float = 10.0


class BatchImportResult(BaseModel):
    success_count: int
    fail_count: int
    errors: list[str] = []
    preview: list[dict] = []


class QuestionParseResult(BaseModel):
    questions: list[QuestionCreate]
    errors: list[str] = []


# Typing
class TypingTextOut(BaseModel):
    id: int
    title: str
    content: str
    difficulty: TypingDifficulty
    char_count: int
    time_limit: int
    is_active: bool

    model_config = {"from_attributes": True}


class TypingTextCreate(BaseModel):
    title: str
    content: str
    difficulty: TypingDifficulty = TypingDifficulty.basic
    time_limit: int = 120


class TypingSubmitRequest(BaseModel):
    text_id: Optional[int] = None
    reference_text: str
    typed_text: str
    duration_seconds: float
    source: str = "practice"


class TypingResultOut(BaseModel):
    wpm: float
    accuracy: float
    correct_chars: int
    error_chars: int
    total_chars: int
    level: str
    level_desc: str
    passed: bool
    score: Optional[float] = None
    remark: Optional[str] = None


class TypingRecordOut(BaseModel):
    id: int
    text_id: Optional[int]
    text_title: str = ""
    source: str
    wpm: float
    accuracy: float
    correct_chars: int
    level: str
    duration_seconds: float
    created_at: datetime

    model_config = {"from_attributes": True}


class TypingStandardsOut(BaseModel):
    levels: list[dict]
    min_accuracy: float
    description: str
