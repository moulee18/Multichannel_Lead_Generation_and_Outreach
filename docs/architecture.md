# IncuBrix GrowthOS — Architecture Overview

## 1. System Architecture
IncuBrix GrowthOS is an integrated, three-agent creator lead generation and multi-channel outreach engine built with:
- **Frontend**: Vanilla ES Modules (`frontend/js/`), HTML5 (`frontend/index.html`), CSS3 (`frontend/css/`), and Chart.js.
- **Backend**: Python 3.11+ / FastAPI (`backend/app/main.py`), Pydantic v2 (`backend/app/schemas/`), and HTTPX.
- **Database**: SQLAlchemy 2.0 ORM (`backend/app/database/models.py`) with 26 relational tables + Alembic migrations (`backend/app/database/migrations/`), supporting SQLite locally and PostgreSQL in cloud deployments.
- **Shared AI Interface**: Optional shared LLM layer (`backend/app/llm/provider.py`) supporting `none`, `gemini`, `openai`, `claude`, and `ollama`, protected by the deterministic **AI Hallucination Guard** (`backend/app/llm/validator.py`).

## 2. Three Coordinated Agents
1. **Agent 1 — Creator Discovery & Verification (`backend/app/agents/agent1/`)**:
   - Collects candidates from official YouTube Data API v3, Public Podcast RSS + Apple iTunes Search API, and verified public research bundles.
   - Deduplicates candidates before verification and runs 8 deterministic qualification checks backed by stored `Evidence` records.
2. **Agent 2 — Lead Intelligence & Outreach (`backend/app/agents/agent2/`)**:
   - Computes explainable 100-point lead scores (`config/scoring.json`), ranks leads, selects top 25 Priority A creators, picks primary & backup channels (`Contact Channel Explainer`), generates creator intelligence, and drafts 3-step sequences across Email, LinkedIn, and Instagram.
3. **Agent 3 — Quality Control & Delivery (`backend/app/agents/agent3/`)**:
   - Independently re-audits qualifications, geographic distribution (>=80% from 7 markets, >=3 countries, <=60% single country), runs the reproducible 20-lead Random Audit Simulator, enforces allowlisted Owned-Account Seed Tests, and exports the complete `submission/` package.
