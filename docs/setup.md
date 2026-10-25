# Setup & Local Execution Guide

## 1. Prerequisites
- Python 3.11+
- Git
- Optional: Docker & Docker Compose

## 2. Local Setup Commands (Windows PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts/init_database.py
```

## 3. One-Command Full Pipeline Execution
```powershell
# Run full pipeline with clearly labelled synthetic demo fixtures:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --demo

# Run full pipeline with live Public Podcast RSS + Apple iTunes discovery:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --live-podcast --keyword "entrepreneur podcast" --max-candidates 15

# Import verified public research records:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --import-public-research
```

## 4. Starting the Web Application & Worker
```powershell
# Start FastAPI + Frontend web server on http://127.0.0.1:8000
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Optional separate background worker process:
.\.venv\Scripts\python.exe worker/main.py
```
