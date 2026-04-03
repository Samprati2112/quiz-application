import sqlite3
import hashlib
import random
import json
import os
from datetime import datetime
from urllib import request, parse, error

DB_PATH = "quiz_app.db"
API_URL = os.getenv("QUIZ_API_URL", "").rstrip("/")


def _api_enabled():
    return bool(API_URL)


def _api_json(method, path, payload=None, params=None):
    if not _api_enabled():
        raise RuntimeError("API mode is not enabled")

    url = f"{API_URL}{path}"
    if params:
        url += "?" + parse.urlencode(params)

    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, default=str).encode("utf-8")

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body or str(exc)
        raise RuntimeError(detail)


def _api_form(method, path, payload=None):
    if not _api_enabled():
        raise RuntimeError("API mode is not enabled")

    url = f"{API_URL}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = parse.urlencode(payload).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            detail = json.loads(body).get("detail", body)
        except Exception:
            detail = body or str(exc)
        raise RuntimeError(detail)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    if _api_enabled():
        _api_json("GET", "/health")
        return

    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT DEFAULT 'student',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS categories (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS questions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question    TEXT NOT NULL,
            category_id INTEGER REFERENCES categories(id),
            difficulty  TEXT CHECK(difficulty IN ('Easy','Medium','Hard')) DEFAULT 'Medium'
        );
        CREATE TABLE IF NOT EXISTS choices (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            choice_text TEXT NOT NULL,
            is_correct  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            quiz_id      INTEGER REFERENCES quizzes(id),
            score        INTEGER NOT NULL,
            total        INTEGER NOT NULL,
            category     TEXT,
            difficulty   TEXT,
            time_taken   INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quizzes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id   INTEGER NOT NULL REFERENCES users(id),
            name         TEXT NOT NULL,
            code         TEXT UNIQUE NOT NULL,
            duration_minutes INTEGER DEFAULT 10,
            start_at     TIMESTAMP,
            end_at       TIMESTAMP,
            max_attempts  INTEGER DEFAULT 1,
            is_locked    INTEGER DEFAULT 0,
            is_active    INTEGER DEFAULT 1,
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS quiz_questions (
            quiz_id      INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
            question_id  INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            PRIMARY KEY (quiz_id, question_id)
        );
    """)
    conn.commit()

    try:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'student'")
        conn.commit()
    except Exception:
        pass

    try:
        conn.execute("ALTER TABLE quiz_sessions ADD COLUMN quiz_id INTEGER REFERENCES quizzes(id)")
        conn.commit()
    except Exception:
        pass

    try:
        conn.execute("ALTER TABLE quizzes ADD COLUMN duration_minutes INTEGER DEFAULT 10")
        conn.commit()
    except Exception:
        pass

    try:
        conn.execute("ALTER TABLE quizzes ADD COLUMN start_at TIMESTAMP")
        conn.execute("ALTER TABLE quizzes ADD COLUMN end_at TIMESTAMP")
        conn.execute("ALTER TABLE quizzes ADD COLUMN max_attempts INTEGER DEFAULT 1")
        conn.execute("ALTER TABLE quizzes ADD COLUMN is_locked INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass

    conn.execute("UPDATE quizzes SET duration_minutes=10 WHERE duration_minutes IS NULL OR duration_minutes < 10")
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 0:
        _seed(conn)

    conn.close()


def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def register_user(username, password, role="student"):
    if _api_enabled():
        try:
            _api_json("POST", "/auth/register", {"username": username, "password": password, "role": role})
            return True, "Registered successfully"
        except RuntimeError as exc:
            return False, str(exc)

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, _hash(password), role),
        )
        conn.commit()
        return True, "Registered successfully"
    except sqlite3.IntegrityError:
        return False, "Username already taken"
    finally:
        conn.close()


def login_user(username, password):
    if _api_enabled():
        try:
            row = _api_json("POST", "/auth/login", {"username": username, "password": password})
            return True, row
        except RuntimeError as exc:
            return False, str(exc)

    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username, _hash(password)),
    ).fetchone()
    conn.close()
    return (True, dict(row)) if row else (False, "Invalid username or password")


def get_categories():
    if _api_enabled():
        return _api_json("GET", "/categories") or []

    conn = get_connection()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ensure_category(name):
    if _api_enabled():
        try:
            row = _api_form("POST", "/categories", {"name": name})
            return row["id"]
        except RuntimeError:
            cats = get_categories()
            match = next((c for c in cats if c["name"] == name.strip().title()), None)
            if match:
                return match["id"]
            raise

    name = name.strip().title()
    conn = get_connection()
    row = conn.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
    if row:
        conn.close()
        return row[0]
    cur = conn.cursor()
    cur.execute("INSERT INTO categories (name) VALUES (?)", (name,))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid


def get_questions(category_id=None, difficulty=None, limit=10):
    if _api_enabled():
        params = {"limit": limit}
        if category_id:
            params["category_id"] = category_id
        if difficulty:
            params["difficulty"] = difficulty
        return _api_json("GET", "/questions", params=params) or []

    conn = get_connection()
    where, params = [], []
    if category_id:
        where.append("q.category_id = ?"); params.append(category_id)
    if difficulty:
        where.append("q.difficulty = ?");  params.append(difficulty)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT q.id, q.question, q.difficulty, cat.name AS category
        FROM questions q
        JOIN categories cat ON q.category_id = cat.id
        {where_sql}
        ORDER BY RANDOM()
        LIMIT ?
    """, params + [limit]).fetchall()

    result = []
    for q in rows:
        q = dict(q)
        ch_rows = conn.execute(
            "SELECT choice_text, is_correct FROM choices WHERE question_id=?",
            (q["id"],),
        ).fetchall()
        answer = next(c["choice_text"] for c in ch_rows if c["is_correct"])
        texts  = [c["choice_text"] for c in ch_rows]
        random.shuffle(texts)
        q["choices"] = texts
        q["answer"]  = answer
        result.append(q)

    conn.close()
    return result


def get_quiz_questions(quiz_id):
    if _api_enabled():
        return _api_json("GET", f"/quizzes/{quiz_id}/questions") or []

    conn = get_connection()
    rows = conn.execute("""
        SELECT q.id, q.question, q.difficulty, cat.name AS category
        FROM quiz_questions qq
        JOIN questions q ON q.id = qq.question_id
        JOIN categories cat ON q.category_id = cat.id
        WHERE qq.quiz_id = ?
        ORDER BY RANDOM()
    """, (quiz_id,)).fetchall()

    result = []
    for q in rows:
        q = dict(q)
        ch_rows = conn.execute(
            "SELECT choice_text, is_correct FROM choices WHERE question_id=?",
            (q["id"],),
        ).fetchall()
        answer = next(c["choice_text"] for c in ch_rows if c["is_correct"])
        texts = [c["choice_text"] for c in ch_rows]
        random.shuffle(texts)
        q["choices"] = texts
        q["answer"] = answer
        result.append(q)

    conn.close()
    return result


def create_quiz(teacher_id, name, code, duration_minutes, attempts=1, start_at=None, end_at=None, is_locked=False):
    if _api_enabled():
        payload = {
            "teacher_id": teacher_id,
            "name": name,
            "code": code,
            "duration_minutes": duration_minutes,
            "max_attempts": attempts,
            "start_at": start_at,
            "end_at": end_at,
        }
        try:
            row = _api_json("POST", "/quizzes", payload)
            if is_locked:
                _api_form("PATCH", f"/quizzes/{row['id']}/lock", {"is_locked": "true"})
            return True, "Quiz created"
        except RuntimeError as exc:
            return False, str(exc)

    duration_minutes = max(10, int(duration_minutes))
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO quizzes
               (teacher_id, name, code, duration_minutes, start_at, end_at, max_attempts, is_locked)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                teacher_id,
                name.strip(),
                code.strip().upper(),
                duration_minutes,
                start_at,
                end_at,
                int(attempts),
                1 if is_locked else 0,
            ),
        )
        conn.commit()
        return True, "Quiz created"
    except sqlite3.IntegrityError:
        return False, "Code already exists. Use a unique code."
    finally:
        conn.close()


def get_teacher_quizzes(teacher_id):
    if _api_enabled():
        return _api_json("GET", f"/quizzes/teacher/{teacher_id}") or []

    conn = get_connection()
    rows = conn.execute("""
        SELECT q.id, q.name, q.code, q.duration_minutes, q.start_at, q.end_at,
               q.max_attempts, q.is_locked, q.is_active, q.created_at,
               COUNT(qq.question_id) AS question_count
        FROM quizzes q
        LEFT JOIN quiz_questions qq ON qq.quiz_id = q.id
        WHERE q.teacher_id = ?
        GROUP BY q.id
        ORDER BY q.created_at DESC
    """, (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_quiz_by_code(code):
    if _api_enabled():
        return _api_json("GET", f"/quizzes/by-code/{parse.quote(code.strip().upper())}")

    conn = get_connection()
    row = conn.execute("""
        SELECT q.id, q.name, q.code, q.duration_minutes, q.start_at, q.end_at,
               q.max_attempts, q.is_locked, q.is_active, u.username AS teacher
        FROM quizzes q
        JOIN users u ON u.id = q.teacher_id
        WHERE q.code = ?
    """, (code.strip().upper(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_quiz_for_student(code, user_id):
    if _api_enabled():
        try:
            return _api_json("GET", f"/quizzes/by-code/{parse.quote(code.strip().upper())}/student/{user_id}")
        except RuntimeError as exc:
            raise ValueError(str(exc))

    quiz = get_quiz_by_code(code)
    if not quiz:
        raise ValueError("Invalid code")
    if not quiz.get("is_active"):
        raise ValueError("This test is not active right now.")
    if quiz.get("is_locked"):
        raise ValueError("This test is locked.")
    if quiz.get("start_at"):
        start_at = datetime.fromisoformat(str(quiz["start_at"]))
        if datetime.now() < start_at:
            raise ValueError("Quiz has not started yet")
    if quiz.get("end_at"):
        end_at = datetime.fromisoformat(str(quiz["end_at"]))
        if datetime.now() > end_at:
            raise ValueError("Quiz has ended")

    conn = get_connection()
    attempts = conn.execute(
        "SELECT COUNT(*) FROM quiz_sessions WHERE user_id=? AND quiz_id=?",
        (user_id, quiz["id"]),
    ).fetchone()[0]
    conn.close()
    if attempts >= int(quiz.get("max_attempts") or 1):
        raise ValueError("Attempt limit reached")
    return quiz


def attach_question_to_quiz(quiz_id, question_id):
    if _api_enabled():
        _api_json("POST", f"/quizzes/{quiz_id}/attach-question/{question_id}")
        return

    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO quiz_questions (quiz_id, question_id) VALUES (?, ?)",
        (quiz_id, question_id),
    )
    conn.commit()
    conn.close()


def get_all_questions(category_id=None, difficulty=None):
    if _api_enabled():
        params = {}
        if category_id:
            params["category_id"] = category_id
        if difficulty:
            params["difficulty"] = difficulty
        return _api_json("GET", "/questions", params=params) or []

    conn = get_connection()
    where, params = [], []
    if category_id:
        where.append("q.category_id = ?"); params.append(category_id)
    if difficulty:
        where.append("q.difficulty = ?");  params.append(difficulty)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(f"""
        SELECT q.id, q.question, q.difficulty, cat.name AS category,
               (SELECT ch.choice_text FROM choices ch
                WHERE ch.question_id = q.id AND ch.is_correct = 1 LIMIT 1) AS answer
        FROM questions q
        JOIN categories cat ON q.category_id = cat.id
        {where_sql}
        ORDER BY q.id DESC
    """, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_question(question_text, category_id, difficulty, choices, correct_index):
    if _api_enabled():
        category_name = None
        try:
            category_name = next((c["name"] for c in get_categories() if c["id"] == category_id), None)
        except Exception:
            category_name = None
        payload = {
            "question": question_text,
            "category": category_name or str(category_id),
            "difficulty": difficulty,
            "choices": choices,
            "correct_index": correct_index,
        }
        try:
            row = _api_json("POST", "/questions", payload)
            return row.get("id") if isinstance(row, dict) else None
        except RuntimeError as exc:
            raise RuntimeError(str(exc))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO questions (question, category_id, difficulty) VALUES (?, ?, ?)",
        (question_text, category_id, difficulty),
    )
    qid = cur.lastrowid
    for i, ch in enumerate(choices):
        conn.execute(
            "INSERT INTO choices (question_id, choice_text, is_correct) VALUES (?, ?, ?)",
            (qid, ch, 1 if i == correct_index else 0),
        )
    conn.commit()
    conn.close()
    return qid


def delete_question(question_id):
    if _api_enabled():
        _api_json("DELETE", f"/questions/{question_id}")
        return

    conn = get_connection()
    conn.execute("DELETE FROM choices   WHERE question_id=?", (question_id,))
    conn.execute("DELETE FROM questions WHERE id=?",          (question_id,))
    conn.commit()
    conn.close()


def save_session(user_id, score, total, category, difficulty, time_taken, quiz_id=None):
    if _api_enabled():
        _api_json("POST", "/quiz-sessions", {
            "user_id": user_id,
            "quiz_id": quiz_id,
            "score": score,
            "total": total,
            "category": category,
            "difficulty": difficulty,
            "time_taken": time_taken,
        })
        return

    conn = get_connection()
    conn.execute(
        """INSERT INTO quiz_sessions
           (user_id, quiz_id, score, total, category, difficulty, time_taken)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (user_id, quiz_id, score, total, category, difficulty, time_taken),
    )
    conn.commit()
    conn.close()


def get_leaderboard(limit=10):
    if _api_enabled():
        return _api_json("GET", "/quiz-sessions/leaderboard", params={"limit": limit}) or []

    conn = get_connection()
    rows = conn.execute("""
        SELECT u.username,
               ROUND(MAX(qs.score * 100.0 / qs.total), 1) AS best_pct,
               COUNT(*)      AS quizzes,
               SUM(qs.score) AS total_correct
        FROM quiz_sessions qs
        JOIN users u ON qs.user_id = u.id
        WHERE u.role = 'student'
        GROUP BY qs.user_id
        ORDER BY best_pct DESC, total_correct DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_history(user_id, limit=15):
    if _api_enabled():
        return _api_json("GET", f"/quiz-sessions/history/{user_id}", params={"limit": limit}) or []

    conn = get_connection()
    rows = conn.execute("""
        SELECT qs.score, qs.total, qs.category, qs.difficulty,
               qs.time_taken, qs.completed_at, q.name AS quiz_name, q.code AS quiz_code
        FROM quiz_sessions
        qs LEFT JOIN quizzes q ON q.id = qs.quiz_id
        WHERE qs.user_id = ?
        ORDER BY qs.completed_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(limit=100):
    if _api_enabled():
        return _api_json("GET", "/quiz-sessions/all", params={"limit": limit}) or []

    conn = get_connection()
    rows = conn.execute("""
        SELECT u.username,
               qs.score, qs.total,
               ROUND(qs.score * 100.0 / qs.total, 1) AS pct,
             q.name AS quiz_name,
             q.code AS quiz_code,
               qs.category, qs.difficulty,
               qs.time_taken, qs.completed_at
        FROM quiz_sessions qs
        JOIN users u ON qs.user_id = u.id
         LEFT JOIN quizzes q ON q.id = qs.quiz_id
        WHERE u.role = 'student'
        ORDER BY qs.completed_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_student_stats():
    if _api_enabled():
        return _api_json("GET", "/stats/teacher") or {"students": 0, "questions": 0, "sessions": 0, "avg_pct": 0.0}

    conn = get_connection()
    s = {}
    s["students"]  = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    s["questions"] = conn.execute(
        "SELECT COUNT(*) FROM questions").fetchone()[0]
    s["sessions"]  = conn.execute(
        "SELECT COUNT(*) FROM quiz_sessions").fetchone()[0]
    avg = conn.execute(
        "SELECT AVG(score * 100.0 / total) FROM quiz_sessions").fetchone()[0]
    s["avg_pct"] = round(avg, 1) if avg else 0.0
    conn.close()
    return s


def _seed(conn):
    cats = ["Science", "Geography", "History", "Art & Literature", "General Knowledge"]
    for c in cats:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (c,))
    conn.commit()

    cid = {r[0]: r[1] for r in conn.execute("SELECT name, id FROM categories")}

    data = [
        ("What is the chemical symbol for gold?", "Science", "Easy",
         ["Go", "Au", "Ag", "Gd"], 1),
        ("What is the chemical symbol for water?", "Science", "Easy",
         ["O", "H2O", "Cl", "CO"], 1),
        ("What is the largest planet in our solar system?", "Science", "Easy",
         ["Jupiter", "Saturn", "Mars", "Earth"], 0),
        ("Which planet is known as the Red Planet?", "Science", "Easy",
         ["Venus", "Jupiter", "Mars", "Saturn"], 2),
        ("Who is known as the father of modern physics?", "Science", "Medium",
         ["Isaac Newton", "Albert Einstein", "Galileo Galilei", "Nikola Tesla"], 1),
        ("Who discovered penicillin?", "Science", "Medium",
         ["Alexander Fleming", "Louis Pasteur", "Jonas Salk", "Joseph Lister"], 0),
        ("What is the largest mammal in the world?", "Science", "Easy",
         ["Elephant", "Giraffe", "Blue Whale", "Lion"], 2),
        ("What force keeps planets in orbit around the Sun?", "Science", "Medium",
         ["Magnetism", "Gravity", "Nuclear Force", "Friction"], 1),
        ("What is the capital of France?", "Geography", "Easy",
         ["Paris", "London", "Berlin", "Madrid"], 0),
        ("Which country is known as the Land of the Rising Sun?", "Geography", "Easy",
         ["China", "Japan", "South Korea", "Thailand"], 1),
        ("What is the capital of Japan?", "Geography", "Easy",
         ["Beijing", "Seoul", "Tokyo", "Bangkok"], 2),
        ("Which country is famous for the Great Wall?", "Geography", "Easy",
         ["China", "India", "Egypt", "Greece"], 0),
        ("What is the largest ocean in the world?", "Geography", "Easy",
         ["Atlantic Ocean", "Indian Ocean", "Pacific Ocean", "Arctic Ocean"], 2),
        ("What is the tallest mountain in the world?", "Geography", "Easy",
         ["Mount Everest", "Mount Kilimanjaro", "Mount Fuji", "Mount McKinley"], 0),
        ("Which is the largest country by area?", "Geography", "Medium",
         ["USA", "China", "Canada", "Russia"], 3),
        ("Which year did the Titanic sink?", "History", "Medium",
         ["1912", "1906", "1920", "1935"], 0),
        ("Who was the first person to walk on the Moon?", "History", "Easy",
         ["Buzz Aldrin", "Neil Armstrong", "Yuri Gagarin", "John Glenn"], 1),
        ("In which year did World War II end?", "History", "Easy",
         ["1943", "1944", "1945", "1946"], 2),
        ("Who wrote Romeo and Juliet?", "Art & Literature", "Easy",
         ["William Shakespeare", "Jane Austen", "Charles Dickens", "Mark Twain"], 0),
        ("Who painted the Mona Lisa?", "Art & Literature", "Easy",
         ["Pablo Picasso", "Vincent van Gogh", "Leonardo da Vinci", "Michelangelo"], 2),
        ("Who painted the Starry Night?", "Art & Literature", "Easy",
         ["Vincent van Gogh", "Pablo Picasso", "Claude Monet", "Leonardo da Vinci"], 0),
        ("Who authored the Harry Potter series?", "Art & Literature", "Easy",
         ["J.R.R. Tolkien", "J.K. Rowling", "Stephen King", "George R.R. Martin"], 1),
        ("How many sides does a hexagon have?", "General Knowledge", "Easy",
         ["5", "6", "7", "8"], 1),
        ("What is the hardest natural substance on Earth?", "General Knowledge", "Easy",
         ["Gold", "Iron", "Diamond", "Quartz"], 2),
        ("How many continents are there on Earth?", "General Knowledge", "Easy",
         ["5", "6", "7", "8"], 2),
    ]

    for q_text, cat_name, diff, choices, correct_idx in data:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO questions (question, category_id, difficulty) VALUES (?, ?, ?)",
            (q_text, cid[cat_name], diff),
        )
        qid = cur.lastrowid
        for i, ch in enumerate(choices):
            conn.execute(
                "INSERT INTO choices (question_id, choice_text, is_correct) VALUES (?, ?, ?)",
                (qid, ch, 1 if i == correct_idx else 0),
            )
    conn.commit()
