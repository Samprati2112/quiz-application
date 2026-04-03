# FastAPI + MySQL Backend

This backend provides a scalable API for the quiz application using FastAPI and MySQL.

## 1) Create MySQL database

```sql
CREATE DATABASE quiz_app;
```

## 2) Configure environment

Copy `.env.example` to `.env` and update your connection string.

## 3) Install dependencies

From project root:

```bash
pip install -r requirements.txt
```

## 4) Run API

From project root:

```bash
uvicorn backend.app.main:app --reload
```

## 5) Open API docs

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## 6) Connect the desktop app to the API

Set the environment variable below before launching the desktop UI:

```bash
set QUIZ_API_URL=http://127.0.0.1:8000
```

On PowerShell:

```powershell
$env:QUIZ_API_URL = "http://127.0.0.1:8000"
```

The desktop app will then use MySQL/FastAPI instead of local SQLite.

## Exam controls

- Teacher creates a test with code, duration, optional start/end window, max attempts, and lock flag.
- Students can enter the code only within the allowed window and attempt limit.
- Tests can be locked to block new starts.

## Notes

- Existing desktop UI can be incrementally migrated to call these endpoints.
- This service supports teacher quiz creation, code-based test access, DOCX import, and session tracking.
