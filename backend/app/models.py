from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False, default="student")
    created_at = Column(DateTime, server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    difficulty = Column(String(16), nullable=False, default="Medium")

    category = relationship("Category")
    choices = relationship("Choice", cascade="all, delete-orphan")


class Choice(Base):
    __tablename__ = "choices"

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    choice_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, nullable=False, default=False)


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(180), nullable=False)
    code = Column(String(40), unique=True, nullable=False, index=True)
    duration_minutes = Column(Integer, nullable=False, default=10)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    max_attempts = Column(Integer, nullable=False, default=1)
    is_locked = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

    teacher = relationship("User")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (UniqueConstraint("quiz_id", "question_id", name="uq_quiz_question"),)

    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"
    __table_args__ = (
        CheckConstraint("total > 0", name="ck_total_positive"),
        CheckConstraint("score >= 0", name="ck_score_non_negative"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=True)
    score = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    category = Column(String(180), nullable=True)
    difficulty = Column(String(50), nullable=True)
    time_taken = Column(Integer, nullable=True)
    completed_at = Column(DateTime, server_default=func.now())
