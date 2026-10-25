# API & Environment Configuration

Configure environment variables in `.env` (never commit `.env` to version control):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./output/growthos.db` | SQLite locally or `postgresql+psycopg://...` in production |
| `YOUTUBE_API_KEY` | *(empty)* | Official YouTube Data API v3 key for live channel & playlist discovery |
| `LLM_PROVIDER` | `none` | Shared LLM mode: `none`, `gemini`, `openai`, `claude`, or `ollama` |
| `GEMINI_API_KEY` | *(empty)* | Optional Google Gemini API key |
| `OPENAI_API_KEY` | *(empty)* | Optional OpenAI API key |
| `ANTHROPIC_API_KEY` | *(empty)* | Optional Anthropic Claude API key |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama endpoint |
| `OUTBOUND_TEST_MODE` | `dry_run` | Enforces `DRY_RUN` default in Seed Test Lab |
| `WORKBOOK_TEMPLATE_PATH` | *(empty)* | Path to official IncuBrix `.xlsx` submission workbook template |
