from datetime import datetime
import math
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .models import ExamStatus, QuestionType, SessionStatus, TypingClassSessionStatus, TypingDifficulty, UserRole
from .timeutil import UtcDateTime


# Auth
class LoginRequest(BaseModel):
    username: str
    password: str


class StudentLoginRequest(BaseModel):
    username: str
    password: str
    class_name: str = "课堂"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class StudentPasswordChallenge(BaseModel):
    password_change_token: str


class StudentPasswordChange(BaseModel):
    new_password: str


# User
class UserBase(BaseModel):
    username: str
    name: str
    role: UserRole = UserRole.student
    class_name: str = ""
    assigned_classes: list[str] = Field(default_factory=list)


class UserCreate(UserBase):
    username: str | None = None
    # 学生密码留空时使用统一的初始密码
    password: Optional[str] = None
    managed_by_teacher_id: int | None = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    name: Optional[str] = None
    role: Optional[UserRole] = None
    class_name: Optional[str] = None
    assigned_classes: Optional[list[str]] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    managed_by_teacher_id: int | None = None


class UserOut(UserBase):
    id: int
    is_active: bool
    created_at: UtcDateTime
    managed_by_teacher_id: int | None = None

    model_config = {"from_attributes": True}

    @field_validator("assigned_classes", mode="before")
    @classmethod
    def empty_class_list(cls, value):
        return [] if value is None else value


# Question
class QuestionBase(BaseModel):
    type: QuestionType
    content: str
    options: Any = []
    correct_answer: str = ""
    score: float = 5.0
    order_num: int = 0


class QuestionCreate(QuestionBase):
    score: float = Field(default=5.0, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_typing_config(self):
        if self.type == QuestionType.typing:
            from .typing_utils import parse_typing_config
            config = parse_typing_config(self.options)
            for key in ("time_limit", "min_wpm", "pass_wpm", "excellent_wpm", "min_accuracy"):
                try:
                    value = float(config[key])
                except (TypeError, ValueError, OverflowError):
                    raise ValueError(f"打字配置 {key} 必须是有效数字")
                if not math.isfinite(value) or value <= 0 or (key == "min_accuracy" and value > 100):
                    raise ValueError(f"打字配置 {key} 超出有效范围")
                config[key] = value
            self.options = config
        return self


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
    duration_minutes: int = Field(default=60, gt=0)
    pass_score: float = Field(default=60.0, ge=0, allow_inf_nan=False)
    questions: list[QuestionCreate] = []


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, gt=0)
    pass_score: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    status: Optional[ExamStatus] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: Optional[list[QuestionCreate]] = None


class ExamOut(ExamBase):
    id: int
    status: ExamStatus
    start_time: Optional[UtcDateTime]
    end_time: Optional[UtcDateTime]
    created_at: UtcDateTime
    question_count: int = 0
    total_score: float = 0.0
    has_sessions: bool = False

    model_config = {"from_attributes": True}


class ExamDetailOut(ExamOut):
    questions: list[QuestionOut] = []


# Session & Answer
class AnswerSubmit(BaseModel):
    question_id: int
    student_answer: str = ""
    answer_meta: Optional[dict] = None

    @field_validator("answer_meta")
    @classmethod
    def validate_duration(cls, meta):
        if meta is not None and meta.get("duration_seconds") is not None:
            try:
                duration = float(meta["duration_seconds"])
            except (TypeError, ValueError, OverflowError):
                raise ValueError("打字用时必须是有效数字")
            if not math.isfinite(duration) or duration < 0:
                raise ValueError("打字用时必须是非负有限数字")
        return meta


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
    start_time: UtcDateTime
    submit_time: Optional[UtcDateTime]
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
    class_stats: list["ClassExamStat"] = []


class ClassExamStat(BaseModel):
    class_name: str
    student_count: int
    submitted_count: int
    average_score: float
    pass_count: int
    pass_rate: float


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
    last_seen_at: Optional[UtcDateTime] = None

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
    update_existing: bool = False


class BatchImportResult(BaseModel):
    success_count: int
    fail_count: int
    updated_count: int = 0
    errors: list[str] = []
    preview: list[dict] = []


class QuestionParseResult(BaseModel):
    questions: list[QuestionCreate]
    errors: list[str] = []


# Typing
class TypingTextOut(BaseModel):
    id: int
    teacher_id: Optional[int] = None
    teacher_name: str = ""
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
    time_limit: int = Field(default=120, ge=30, le=600)


class TypingTextUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    difficulty: Optional[TypingDifficulty] = None
    time_limit: Optional[int] = Field(default=None, ge=30, le=600)


class TypingTextImportRequest(BaseModel):
    text: str
    title: str = ""
    difficulty: TypingDifficulty = TypingDifficulty.basic
    time_limit: int = 120


class TypingTextImportResult(BaseModel):
    success_count: int
    fail_count: int
    errors: list[str] = []
    texts: list[TypingTextOut] = []


class TypingSubmitRequest(BaseModel):
    text_id: Optional[int] = None
    typing_session_id: Optional[int] = None
    reference_text: str
    typed_text: str
    duration_seconds: float = Field(gt=0, allow_inf_nan=False)
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
    student_id: Optional[int] = None
    student_name: str = ""
    class_name: str = ""
    text_id: Optional[int]
    text_title: str = ""
    source: str
    wpm: float
    accuracy: float
    correct_chars: int
    level: str
    score: float = 0.0
    duration_seconds: float
    created_at: UtcDateTime

    model_config = {"from_attributes": True}


class TypingStandardsOut(BaseModel):
    levels: list[dict]
    min_accuracy: float
    description: str


class TypingClassSessionCreate(BaseModel):
    text_id: int
    class_name: str
    title: str = ""
    duration_seconds: int = Field(default=300, gt=0)


class TypingClassSessionOut(BaseModel):
    id: int
    teacher_id: int
    teacher_name: str = ""
    text_id: int
    text_title: str = ""
    class_name: str
    title: str
    status: TypingClassSessionStatus
    duration_seconds: int
    started_at: Optional[UtcDateTime] = None
    ended_at: Optional[UtcDateTime] = None
    created_at: UtcDateTime
    participant_count: int = 0
    submitted_count: int = 0

    model_config = {"from_attributes": True}


class TypingClassSessionDetail(TypingClassSessionOut):
    records: list[TypingRecordOut] = []
