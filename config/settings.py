# ================================================================
#  config/settings.py
# ================================================================

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):

    # ── Groq AI (console.groq.com — FREE) ──────────────────
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"

    # ── Gmail via IMAP/SMTP — NO Google Cloud needed! ───────
    # Just enable 2FA + generate App Password (2 min setup)
    gmail_address: str                  # your@gmail.com
    gmail_app_password: str             # 16-char app password
    gmail_imap_host: str = "imap.gmail.com"
    gmail_imap_port: int = 993
    gmail_smtp_host: str = "smtp.gmail.com"
    gmail_smtp_port: int = 587

    # ── Telegram (FREE FOREVER) ─────────────────────────────
    telegram_bot_token: str
    telegram_chat_id: str

    # ── Notion (FREE — notion.so/my-integrations) ───────────
    notion_token: str
    notion_tasks_db_id: str
    notion_goals_db_id: Optional[str] = None

    # ── Supabase (FREE 500MB — supabase.com) ────────────────
    supabase_url: str
    supabase_key: str

    # ── Bot Password (users must enter this to access) ──────
    bot_password: str = "lifeos123"   # Change this in your .env!

    # ── User preferences ────────────────────────────────────
    user_name: str = "there"
    timezone: str = "Asia/Kolkata"

    # suggest  = asks before acting (recommended for beginners)
    # auto     = acts, then notifies you
    # autopilot= acts silently, alerts only for urgent items
    autonomy_level: str = "suggest"

    email_scan_limit: int = 20
    deep_work_start_hour: int = 9
    deep_work_end_hour: int = 11

    # Finance
    unusual_spend_threshold: float = 2000.0
    monthly_budget: Optional[float] = None

    # Health
    daily_water_glasses: int = 8
    sleep_target_hours: int = 8

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()