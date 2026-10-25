# IncuBrix GrowthOS — AI-Powered Creator Lead Generation & Outreach Engine

**IncuBrix 2027 Graduate Hiring — Growth Engineer Role | Option 1: Multi-Channel Lead Generation and Outreach Engine**

IncuBrix GrowthOS is a complete, deployable, full-stack web application and three-agent acquisition engine that discovers content creators, verifies their qualification with working source evidence, computes explainable 100-point lead scores, selects primary and backup business contact channels, drafts 3-step multi-channel outreach sequences protected by an AI Hallucination Guard, runs independent quality and geographic audits, executes allowlisted Owned-Account Seed Tests, and generates CRM-ready submission deliverables.

---

## 1. Plain-English Architecture Overview

IncuBrix GrowthOS consists of **one integrated application** with:
1. **Frontend (`frontend/`)**: A responsive SaaS web interface built with HTML5, CSS3, Vanilla ES Modules, and Chart.js across 11 operational pages (dark navy sidebar + clean light workspace).
2. **Backend (`backend/app/`)**: FastAPI REST server with Pydantic v2 validation, authentication, OpenAPI `/docs`, and 26 SQLAlchemy relational tables (`output/growthos.db` locally or PostgreSQL in production).
3. **Three Coordinated Logical Agents (`backend/app/agents/`)**:
   - **Agent 1 — Creator Discovery & Verification**: Collects creator profiles and upload histories via the official YouTube Data API v3, Public Podcast RSS + Apple iTunes Search API, and verified public research bundles. Deduplicates candidates before verification and checks 8 strict qualification criteria backed by stored `Evidence` records.
   - **Agent 2 — Lead Intelligence & Outreach**: Scores qualified creators on a configurable 100-point model (`config/scoring.json`), classifies the top 25 as `Priority A`, selects verified primary and backup channels (`Contact Channel Explainer`), analyses creator workflows, and generates 3-step outreach sequences across Email, LinkedIn, and Instagram.
   - **Agent 3 — Quality Control & Delivery**: Independently re-audits creator qualification, geographic distribution (`>= 80%` from US, CA, UK, IE, AU, NZ, SG; `>= 3` countries; `<= 60%` max single country), runs a reproducible 20-lead **Random Audit Simulator**, manages the allowlisted **Seed Test Lab**, and exports the `submission/` package.

---

## 2. Quick Setup & One-Command Operation

### Install Dependencies & Initialise Database
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe scripts/init_database.py
```

### Run Database Migrations (Alembic)
```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

### One-Command Full Pipeline
```powershell
# Run full 3-Agent pipeline with clearly labelled synthetic demo fixtures (35 records -> 30 qualified, 25 Priority A):
.\.venv\Scripts\python.exe scripts/run_pipeline.py --demo

# Run full 3-Agent pipeline with LIVE Public Podcast RSS + Apple iTunes discovery (no API key required):
.\.venv\Scripts\python.exe scripts/run_pipeline.py --live-podcast --keyword "entrepreneur business podcast" --max-candidates 15

# Import existing verified public research records (Jay Clouse + 100 US Podcast Chart records):
.\.venv\Scripts\python.exe scripts/run_pipeline.py --import-public-research
```

### Run Individual Agents
```powershell
# Run Agent 1 (Discovery & Verification) only:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --agent agent1 --demo

# Run Agent 2 (Scoring, Channel Selection & Outreach) only:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --agent agent2

# Run Agent 3 (Independent Audit & Seed Lab) only:
.\.venv\Scripts\python.exe scripts/run_pipeline.py --agent agent3
```

### Run Smart Refresh & Export Deliverables
```powershell
# Run Smart Refresh (skips unchanged records, prevents duplicates, flags stale >30d evidence):
.\.venv\Scripts\python.exe scripts/run_refresh.py --keyword "video podcast" --source synthetic_demo

# Export complete submission/ folder & ZIP bundle:
.\.venv\Scripts\python.exe scripts/export_submission.py
```

### Start the Web Application & Background Worker
```powershell
# Start web application on http://127.0.0.1:8000 (or double-click start_local.cmd):
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# Start persistent background worker (optional separate terminal):
.\.venv\Scripts\python.exe worker/main.py
```
- **Frontend Dashboard URL**: `http://127.0.0.1:8000`
- **OpenAPI Documentation URL**: `http://127.0.0.1:8000/docs`

### Run Automated Tests
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

### Docker Compose Local Workflow
```bash
docker compose up --build -d
```

---

## 3. AI, Automation & Manual Review Disclosure

- **Automated Software**: Discovery, pre-verification deduplication, activity window calculation (`8 in 30d` or `2 long-form in 60d`), explainable scoring, channel selection, and independent audits are executed deterministically by IncuBrix GrowthOS.
- **Optional Shared LLM (`LLM_PROVIDER`)**: Supports `none` (default deterministic mode), `gemini`, `openai`, `claude`, and `ollama`. Every draft is verified by the deterministic **AI Hallucination Guard** (`backend/app/llm/validator.py`).
- **Human-in-the-Loop Verification**: Ambiguous commercial or workflow claims are routed to `NEEDS_REVIEW` in the **Verification Queue**, where human reviewers attach source URLs and notes.
- **Strict Outbound Safety**: Real creator outreach is never executed during the assessment. The **Seed Test Lab** enforces a strict allowlist of participant-owned test accounts (`DEFAULT=DRY_RUN`).
