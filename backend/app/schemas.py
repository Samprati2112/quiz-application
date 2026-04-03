from datetime import datetime
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=4, max_length=128)
    role: str = "student"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    id: int
    username: str
    role: str


class QuizCreateRequest(BaseModel):
    teacher_id: int
    name: str = Field(min_length=3, max_length=180)
    code: str = Field(min_length=4, max_length=40)
    duration_minutes: int = Field(default=10, ge=10)
    start_at: datetime | None = None
    end_at: datetime | None = None
    max_attempts: int = Field(default=1, ge=1)


class QuizResponse(BaseModel):
    id: int
    teacher_id: int
    name: str
    code: str
    duration_minutes: int
    start_at: datetime | None = None
    end_at: datetime | None = None
    max_attempts: int = 1
    is_locked: bool = False
    is_active: bool


class QuestionCreateRequest(BaseModel):
    question: str = Field(min_length=5)
    category: str = Field(min_length=2)
    difficulty: str = "Medium"
    choices: list[str]
    correct_index: int


class QuestionCreateResponse(BaseModel):
    id: int
    message: str


class SessionCreateRequest(BaseModel):
    user_id: int
    quiz_id: int | None = None
    score: int
    total: int
    category: str | None = None
    difficulty: str | None = None
    time_taken: int | None = None


class SessionResponse(BaseModel):
    id: int
    user_id: int
    quiz_id: int | None
    score: int
    total: int
    time_taken: int | None
    completed_at: datetime


class MessageResponse(BaseModel):
    message: str
