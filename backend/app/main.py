import random
import tempfile
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from docx_parser import parse_docx

from .database import Base, engine, get_db
from .models import Category, Choice, Question, Quiz, QuizQuestion, QuizSession, User
from .schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    QuestionCreateRequest,
    QuestionCreateResponse,
    QuizCreateRequest,
    QuizResponse,
    RegisterRequest,
    SessionCreateRequest,
    SessionResponse,
)
from .security import hash_password

app = FastAPI(title="Quiz Application API", version="1.0.0")
Base.metadata.create_all(bind=engine)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@app.get("/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="ok")


@app.post("/auth/register", response_model=LoginResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> LoginResponse:
    exists = db.query(User).filter(User.username == payload.username.strip()).first()
    if exists:
        raise HTTPException(status_code=409, detail="Username already taken")

    role = payload.role if payload.role in {"student", "teacher"} else "student"
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return LoginResponse(id=user.id, username=user.username, role=user.role)


@app.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = (
        db.query(User)
        .filter(
            User.username == payload.username.strip(),
            User.password_hash == hash_password(payload.password),
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(id=user.id, username=user.username, role=user.role)


@app.post("/quizzes", response_model=QuizResponse)
def create_quiz(payload: QuizCreateRequest, db: Session = Depends(get_db)) -> QuizResponse:
    teacher = db.query(User).filter(User.id == payload.teacher_id, User.role == "teacher").first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    code = payload.code.strip().upper()
    if db.query(Quiz).filter(Quiz.code == code).first():
        raise HTTPException(status_code=409, detail="Code already exists")

    quiz = Quiz(
        teacher_id=payload.teacher_id,
        name=payload.name.strip(),
        code=code,
        duration_minutes=max(10, payload.duration_minutes),
        start_at=payload.start_at,
        end_at=payload.end_at,
        max_attempts=max(1, payload.max_attempts),
        is_locked=False,
        is_active=True,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz


@app.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    return [
        {"id": row.id, "name": row.name}
        for row in db.query(Category).order_by(Category.name).all()
    ]


@app.post("/categories")
def create_category(name: str = Form(...), db: Session = Depends(get_db)):
    key = name.strip().title()
    row = db.query(Category).filter(Category.name == key).first()
    if row:
        return {"id": row.id, "name": row.name}
    row = Category(name=key)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name}


@app.get("/questions")
def list_questions(
    category_id: int | None = None,
    difficulty: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Question)
    if category_id:
        query = query.filter(Question.category_id == category_id)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    rows = query.order_by(Question.id.desc()).all()
    result = []
    for q in rows:
        answer_row = (
            db.query(Choice.choice_text)
            .filter(Choice.question_id == q.id, Choice.is_correct.is_(True))
            .first()
        )
        result.append(
            {
                "id": q.id,
                "question": q.question,
                "difficulty": q.difficulty,
                "category": q.category.name if q.category else "",
                "answer": answer_row[0] if answer_row else "",
            }
        )
    return result


@app.get("/quizzes/teacher/{teacher_id}", response_model=list[QuizResponse])
def teacher_quizzes(teacher_id: int, db: Session = Depends(get_db)) -> list[QuizResponse]:
    return (
        db.query(Quiz)
        .filter(Quiz.teacher_id == teacher_id)
        .order_by(Quiz.created_at.desc())
        .all()
    )


@app.get("/quizzes/by-code/{code}", response_model=QuizResponse)
def quiz_by_code(code: str, db: Session = Depends(get_db)) -> QuizResponse:
    quiz = db.query(Quiz).filter(Quiz.code == code.strip().upper()).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Invalid code")
    if not quiz.is_active:
        raise HTTPException(status_code=400, detail="Quiz is not active")
    return quiz


def _ensure_category(db: Session, name: str) -> Category:
    key = name.strip().title()
    row = db.query(Category).filter(Category.name == key).first()
    if row:
        return row
    row = Category(name=key)
    db.add(row)
    db.flush()
    return row


def _create_question(
    db: Session,
    payload: QuestionCreateRequest,
    quiz_id: int | None = None,
) -> int:
    if len(payload.choices) < 2:
        raise HTTPException(status_code=400, detail="At least 2 choices are required")
    if payload.correct_index < 0 or payload.correct_index >= len(payload.choices):
        raise HTTPException(status_code=400, detail="Invalid correct_index")

    cat = _ensure_category(db, payload.category)
    q = Question(question=payload.question.strip(), category_id=cat.id, difficulty=payload.difficulty)
    db.add(q)
    db.flush()

    for i, ch in enumerate(payload.choices):
        db.add(Choice(question_id=q.id, choice_text=ch.strip(), is_correct=(i == payload.correct_index)))

    if quiz_id is not None:
        db.add(QuizQuestion(quiz_id=quiz_id, question_id=q.id))

    return q.id


@app.post("/questions", response_model=QuestionCreateResponse)
def create_question(payload: QuestionCreateRequest, db: Session = Depends(get_db)) -> QuestionCreateResponse:
    qid = _create_question(db, payload)
    db.commit()
    return {"message": "Question created", "id": qid}


@app.delete("/questions/{question_id}", response_model=MessageResponse)
def remove_question(question_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    row = db.query(Question).filter(Question.id == question_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(row)
    db.commit()
    return MessageResponse(message="Question deleted")


@app.post("/quizzes/{quiz_id}/attach-question/{question_id}", response_model=MessageResponse)
def attach_existing_question_to_quiz(quiz_id: int, question_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    question = db.query(Question).filter(Question.id == question_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    exists = (
        db.query(QuizQuestion)
        .filter(QuizQuestion.quiz_id == quiz_id, QuizQuestion.question_id == question_id)
        .first()
    )
    if not exists:
        db.add(QuizQuestion(quiz_id=quiz_id, question_id=question_id))
        db.commit()
    return MessageResponse(message="Question attached to quiz")


@app.post("/quizzes/{quiz_id}/questions", response_model=MessageResponse)
def add_question_to_quiz(
    quiz_id: int,
    payload: QuestionCreateRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    _create_question(db, payload, quiz_id=quiz_id)
    db.commit()
    return MessageResponse(message="Question created and attached to quiz")


@app.post("/quizzes/{quiz_id}/import-docx", response_model=MessageResponse)
def import_docx_to_quiz(
    quiz_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MessageResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as temp:
        temp.write(file.file.read())
        temp.flush()
        questions, errors = parse_docx(temp.name)

    if not questions and errors:
        raise HTTPException(status_code=400, detail="; ".join(errors[:3]))

    created = 0
    for q in questions:
        payload = QuestionCreateRequest(
            question=q["question"],
            category=q["category"],
            difficulty=q["difficulty"],
            choices=q["choices"],
            correct_index=q["correct_index"],
        )
        _create_question(db, payload, quiz_id=quiz_id)
        created += 1

    db.commit()
    msg = f"Imported {created} question(s)."
    if errors:
        msg += f" Skipped {len(errors)} malformed block(s)."
    return MessageResponse(message=msg)


@app.get("/quizzes/{quiz_id}/questions")
def quiz_questions(quiz_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    rows = (
        db.query(Question)
        .join(QuizQuestion, QuizQuestion.question_id == Question.id)
        .filter(QuizQuestion.quiz_id == quiz_id)
        .all()
    )

    result: list[dict[str, Any]] = []
    for q in rows:
        ch = db.query(Choice).filter(Choice.question_id == q.id).all()
        answer = next((c.choice_text for c in ch if c.is_correct), "")
        texts = [c.choice_text for c in ch]
        random.shuffle(texts)
        result.append(
            {
                "id": q.id,
                "question": q.question,
                "difficulty": q.difficulty,
                "choices": texts,
                "answer": answer,
            }
        )

    random.shuffle(result)
    return result


@app.get("/quizzes/by-code/{code}/student/{user_id}")
def quiz_for_student(code: str, user_id: int, db: Session = Depends(get_db)):
    quiz = db.query(Quiz).filter(Quiz.code == code.strip().upper()).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Invalid code")

    now = _now_utc()
    if not quiz.is_active:
        raise HTTPException(status_code=400, detail="Quiz is not active")
    if quiz.is_locked:
        raise HTTPException(status_code=400, detail="Quiz is locked")
    if quiz.start_at and now < quiz.start_at:
        raise HTTPException(status_code=400, detail="Quiz has not started yet")
    if quiz.end_at and now > quiz.end_at:
        raise HTTPException(status_code=400, detail="Quiz has ended")

    attempts = (
        db.query(func.count(QuizSession.id))
        .filter(QuizSession.user_id == user_id, QuizSession.quiz_id == quiz.id)
        .scalar()
        or 0
    )
    if attempts >= quiz.max_attempts:
        raise HTTPException(status_code=403, detail="Attempt limit reached")

    return {
        "id": quiz.id,
        "name": quiz.name,
        "code": quiz.code,
        "duration_minutes": quiz.duration_minutes,
        "is_active": quiz.is_active,
        "is_locked": quiz.is_locked,
        "start_at": quiz.start_at,
        "end_at": quiz.end_at,
        "max_attempts": quiz.max_attempts,
        "teacher": quiz.teacher.username if hasattr(quiz, "teacher") and quiz.teacher else None,
        "can_start": True,
        "attempts": attempts,
    }


@app.patch("/quizzes/{quiz_id}/lock", response_model=QuizResponse)
def lock_quiz(quiz_id: int, is_locked: bool = Form(...), db: Session = Depends(get_db)) -> QuizResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz.is_locked = is_locked
    db.commit()
    db.refresh(quiz)
    return quiz


@app.patch("/quizzes/{quiz_id}/window", response_model=QuizResponse)
def update_quiz_window(
    quiz_id: int,
    start_at: datetime | None = Form(None),
    end_at: datetime | None = Form(None),
    max_attempts: int = Form(1),
    db: Session = Depends(get_db),
) -> QuizResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if max_attempts < 1:
        raise HTTPException(status_code=400, detail="max_attempts must be >= 1")
    quiz.start_at = start_at
    quiz.end_at = end_at
    quiz.max_attempts = max_attempts
    db.commit()
    db.refresh(quiz)
    return quiz


@app.post("/quiz-sessions", response_model=SessionResponse)
def save_quiz_session(
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
) -> SessionResponse:
    row = QuizSession(
        user_id=payload.user_id,
        quiz_id=payload.quiz_id,
        score=payload.score,
        total=payload.total,
        category=payload.category,
        difficulty=payload.difficulty,
        time_taken=payload.time_taken,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/stats/teacher")
def teacher_stats(db: Session = Depends(get_db)):
    students = db.query(func.count(User.id)).filter(User.role == "student").scalar() or 0
    questions = db.query(func.count(Question.id)).scalar() or 0
    sessions = db.query(func.count(QuizSession.id)).scalar() or 0
    avg = db.query(func.avg((QuizSession.score * 100.0) / QuizSession.total)).scalar()
    return {"students": students, "questions": questions, "sessions": sessions, "avg_pct": round(float(avg or 0), 1)}


@app.get("/quiz-sessions/history/{user_id}")
def user_history(user_id: int, limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(QuizSession, Quiz.name, Quiz.code)
        .outerjoin(Quiz, Quiz.id == QuizSession.quiz_id)
        .filter(QuizSession.user_id == user_id)
        .order_by(QuizSession.completed_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "score": r[0].score,
            "total": r[0].total,
            "category": r[0].category,
            "difficulty": r[0].difficulty,
            "time_taken": r[0].time_taken,
            "completed_at": r[0].completed_at,
            "quiz_name": r[1],
            "quiz_code": r[2],
        }
        for r in rows
    ]


@app.get("/quiz-sessions/all")
def all_sessions(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(QuizSession, User.username, Quiz.name, Quiz.code)
        .join(User, User.id == QuizSession.user_id)
        .outerjoin(Quiz, Quiz.id == QuizSession.quiz_id)
        .filter(User.role == "student")
        .order_by(QuizSession.completed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "username": r[1],
            "score": r[0].score,
            "total": r[0].total,
            "pct": round((r[0].score * 100.0 / r[0].total), 1),
            "quiz_name": r[2],
            "quiz_code": r[3],
            "category": r[0].category,
            "difficulty": r[0].difficulty,
            "time_taken": r[0].time_taken,
            "completed_at": r[0].completed_at,
        }
        for r in rows
    ]


@app.get("/quiz-sessions/leaderboard")
def leaderboard(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(
            User.username,
            func.max((QuizSession.score * 100.0) / QuizSession.total).label("best_pct"),
            func.count(QuizSession.id).label("quizzes"),
            func.sum(QuizSession.score).label("total_correct"),
        )
        .join(QuizSession, QuizSession.user_id == User.id)
        .filter(User.role == "student")
        .group_by(User.id, User.username)
        .order_by(func.max((QuizSession.score * 100.0) / QuizSession.total).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "username": r[0],
            "best_pct": round(float(r[1] or 0), 1),
            "quizzes": int(r[2] or 0),
            "total_correct": int(r[3] or 0),
        }
        for r in rows
    ]


@app.patch("/quizzes/{quiz_id}/active", response_model=QuizResponse)
def set_quiz_active(
    quiz_id: int,
    is_active: bool = Form(...),
    db: Session = Depends(get_db),
) -> QuizResponse:
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    quiz.is_active = is_active
    db.commit()
    db.refresh(quiz)
    return quiz
