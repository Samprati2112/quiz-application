# Quiz Application

A desktop quiz system built with CustomTkinter, SQLite, and a FastAPI + MySQL backend option for scaling to multiple students.

## Features

- Teacher and student login
- Teacher-created test codes
- DOCX question import
- Full-test exam timer with duration control
- Optional test start/end windows
- Maximum attempts and lock support
- Student quiz history and leaderboard
- Teacher dashboard for test management and results

## Project Structure

- `main.py` - desktop app entry point
- `teacher_dashboard.py` - teacher dashboard UI
- `database.py` - local SQLite data layer and API bridge
- `docx_parser.py` - Word document parser/template generator
- `backend/` - FastAPI + MySQL backend
- `requirements.txt` - Python dependencies

## Local Desktop Mode

By default, the app can run with the local SQLite database file `quiz_app.db`.

### Install

```bash
pip install -r requirements.txt
```

### Run

```bash
py -3.14 main.py
```

## Backend Mode

For multi-user use, run the FastAPI backend and point the desktop app at it.

### 1. Start MySQL

Create a database named `quiz_app`.

### 2. Set the backend URL

PowerShell:

```powershell
$env:QUIZ_API_URL = "http://127.0.0.1:8000"
```

Command Prompt:

```bat
set QUIZ_API_URL=http://127.0.0.1:8000
```

### 3. Run the FastAPI backend

```bash
uvicorn backend.app.main:app --reload
```

### 4. Run the desktop app

```bash
py -3.14 main.py
```

## Teacher Workflow

1. Log in as a teacher.
2. Open **Test Setup**.
3. Create a test name and code.
4. Set duration, optional start/end time, max attempts, and lock state.
5. Upload questions from a `.docx` file and assign them to that test.
6. Share the test code with students.

## Student Workflow

1. Log in as a student.
2. Enter the test code provided by the teacher.
3. Start the test and answer all questions within the total time limit.
4. Submit automatically when time expires.

## DOCX Format

Each question block should look like this:

```text
Q: What is the capital of France?
A) Paris
B) London
C) Berlin
D) Madrid
Correct: A
Category: Geography
Difficulty: Easy
```

## Notes

- Minimum test duration is 10 minutes.
- The full quiz timer runs across the entire test, not per question.
- Multiple students can take the same test code at the same time.
- The backend mode is the recommended setup for college use.

## Requirements

- Python 3.14+
- CustomTkinter
- python-docx
- FastAPI
- MySQL
- SQLAlchemy
- PyMySQL
