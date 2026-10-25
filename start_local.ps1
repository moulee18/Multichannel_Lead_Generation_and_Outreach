$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "Initialising IncuBrix GrowthOS database..."
.\.venv\Scripts\python.exe scripts/init_database.py

Write-Host "Starting IncuBrix GrowthOS on http://127.0.0.1:8000 ..."
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
