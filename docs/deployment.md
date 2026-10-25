# Deployment Guide (Local Docker & Cloud Hosting)

## 1. Local Docker Compose Deployment
```bash
docker compose up --build -d
```
- Web UI & FastAPI Backend: `http://127.0.0.1:8000`
- OpenAPI Documentation: `http://127.0.0.1:8000/docs`
- Background Worker: `incubrix-growthos-worker` container

## 2. Cloud Deployment (Render / Railway + Managed PostgreSQL + Vercel/Netlify)
1. **Managed PostgreSQL**: Provision a PostgreSQL instance and set `DATABASE_URL=postgresql://user:pass@host:5432/growthos`.
2. **Backend Web Service (Render / Railway)**:
   - Build Command: `pip install -r requirements.txt && python scripts/init_database.py`
   - Start Command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
3. **Background Worker Service**:
   - Start Command: `python worker/main.py`
4. **Environment Secrets**: Set `APP_SECRET_KEY`, `ADMIN_PASSWORD`, `YOUTUBE_API_KEY`, and `CORS_ORIGINS` in the hosting provider's secret manager.
