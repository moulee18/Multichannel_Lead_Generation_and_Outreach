from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    app_name: str = "IncuBrix GrowthOS — AI-Powered Creator Lead Generation & Outreach Engine"
    version: str = "1.0.0"
    base_dir: Path = BASE_DIR
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'output' / 'growthos.db').as_posix()}"
        )
    )
    youtube_api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", "").strip())
    podcast_index_api_key: str = field(default_factory=lambda: os.getenv("PODCAST_INDEX_API_KEY", "").strip())
    podcast_index_api_secret: str = field(default_factory=lambda: os.getenv("PODCAST_INDEX_API_SECRET", "").strip())
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "none").strip().lower() or "none")
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "").strip())
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", "").strip())
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "").strip())
    ollama_base_url: str = field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
    )
    app_secret_key: str = field(
        default_factory=lambda: os.getenv("APP_SECRET_KEY", "incubrix-growthos-local-secret-key-2026")
    )
    admin_username: str = field(default_factory=lambda: os.getenv("ADMIN_USERNAME", "admin"))
    admin_password: str = field(default_factory=lambda: os.getenv("ADMIN_PASSWORD", "incubrix-local-admin"))
    outbound_test_mode: str = field(
        default_factory=lambda: os.getenv("OUTBOUND_TEST_MODE", "dry_run").strip().lower() or "dry_run"
    )
    workbook_template_path: str = field(
        default_factory=lambda: os.getenv(
            "WORKBOOK_TEMPLATE_PATH",
            str(BASE_DIR / "config" / "incubrix_option1_workbook_template.xlsx"),
        ).strip()
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:3000,http://localhost:3000",
            ).split(",")
            if origin.strip()
        ]
    )
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    sender_name: str = field(default_factory=lambda: os.getenv("SENDER_NAME", "Arjun Mehta (Growth Engineering Candidate)"))
    sender_role: str = field(default_factory=lambda: os.getenv("SENDER_ROLE", "Independent Growth Assessment Participant (evaluating IncuBrix workflows)"))
    sender_email: str = field(default_factory=lambda: os.getenv("SENDER_EMAIL", "seedtest.participant@example.org"))

    def load_json_config(self, filename: str) -> dict[str, Any]:
        config_path = self.base_dir / "config" / filename
        if not config_path.exists():
            return {}
        return json.loads(config_path.read_text(encoding="utf-8"))


def get_settings() -> Settings:
    return Settings()
