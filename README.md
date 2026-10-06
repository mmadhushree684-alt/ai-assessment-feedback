# AI Powered Assessment and Feedback

Step 1: starting page, student and teacher registration, login, logout, role-based access and the full PostgreSQL schema.

## Folder structure

```
ai-assessment/
├── backend/                 Flask server (Python)
│   ├── app.py               Creates the app, serves the home page
│   ├── config.py            Reads settings from .env
│   ├── db.py                PostgreSQL connection + init-db / seed commands
│   ├── validators.py        Username, Gmail and password rules (server side)
│   ├── routes/auth.py       Register, login, logout, role protection, dashboards
│   ├── requirements.txt     Python packages
│   └── .env.example         Copy to .env and fill in
├── frontend/                Everything the browser shows
│   ├── templates/           HTML pages (base, home, register, login, dashboard)
│   └── static/
│       ├── css/style.css    Styling (navy, lavender, white, gray + amber)
│       └── js/validation.js Live form checks
└── database/
    └── schema.sql           All PostgreSQL tables
```

The backend serves the frontend files, so you still start just one server.

## Setup on Windows (VS Code)

1. Install Python 3.11+ (tick "Add Python to PATH") and PostgreSQL.
2. Open the `ai-assessment` folder in VS Code and open a terminal.
3. Go into the backend folder and create a virtual environment:
   ```
   cd backend
   python -m venv venv
   venv\Scripts\activate
   ```
   If PowerShell blocks it, run `Set-ExecutionPolicy -Scope Process Bypass` first.
4. Install packages:
   ```
   pip install -r requirements.txt
   ```
5. Create the database. Open **SQL Shell (psql)**, log in as `postgres`, run:
   ```
   CREATE DATABASE assessment_db;
   ```
6. Copy `.env.example` to `.env` (inside `backend`) and edit:
   ```
   SECRET_KEY=any-long-random-text
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/assessment_db
   TEACHER_VERIFICATION_PASSWORD=TEACHER@2026
   GEMINI_API_KEY=your-key
   ```
7. Create the tables and sample accounts (still inside `backend`):
   ```
   flask --app app init-db
   flask --app app seed
   ```
8. Run:
   ```
   python app.py
   ```
   Open http://127.0.0.1:5000

## Gemini API key
Create a key at https://aistudio.google.com/apikey and put it in `GEMINI_API_KEY` in `backend/.env`. It stays on the server and is never sent to the browser.

## Sample accounts (after `seed`)
- Student: `Samplestudent` / `Student@123`
- Teacher: `Sampleteacher` / `Teacher@123`

All teachers register with the same `TEACHER_VERIFICATION_PASSWORD` and share one dashboard.
