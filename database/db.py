# ================================================================
#  database/db.py — Supabase (FREE 500MB)
# ================================================================

import logging
from datetime import datetime
from typing import Dict, List, Optional
from supabase import create_client, Client
from config.settings import settings

log = logging.getLogger("Database")


class Database:
    def __init__(self):
        self.client: Client = create_client(settings.supabase_url, settings.supabase_key)

    async def init(self):
        log.info("Supabase connection ready")

    async def log_action(self, action_type: str, description: str,
                          metadata: dict = None, reversible: bool = False) -> Optional[int]:
        try:
            r = self.client.table("action_log").insert({
                "action_type": action_type,
                "description": description,
                "metadata": metadata or {},
                "reversible": reversible,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            return r.data[0]["id"] if r.data else None
        except Exception as e:
            log.error(f"Log action error: {e}")
            return None

    async def get_recent_actions(self, limit: int = 5) -> List[Dict]:
        try:
            r = self.client.table("action_log").select("*")\
                .order("created_at", desc=True).limit(limit).execute()
            return r.data or []
        except Exception:
            return []

    async def mark_reversed(self, action_id: int):
        try:
            self.client.table("action_log").update({"reversed": True})\
                .eq("id", action_id).execute()
        except Exception as e:
            log.error(f"Mark reversed error: {e}")

    async def log_email(self, email_id: str, subject: str, sender: str,
                         category: str, action: str):
        try:
            self.client.table("email_log").upsert({
                "email_id": email_id[:200], "subject": subject[:200],
                "sender": sender[:200], "category": category, "action_taken": action,
            }).execute()
        except Exception as e:
            log.error(f"Log email error: {e}")

    async def is_processed(self, email_id: str) -> bool:
        try:
            r = self.client.table("email_log").select("id")\
                .eq("email_id", email_id[:200]).execute()
            return len(r.data) > 0
        except Exception:
            return False

    async def increment_stat(self, field: str):
        today = datetime.now().date().isoformat()
        try:
            self.client.table("daily_stats").upsert({"date": today}, on_conflict="date").execute()
            r = self.client.table("daily_stats").select(field).eq("date", today).execute()
            current = r.data[0].get(field, 0) if r.data else 0
            self.client.table("daily_stats").update(
                {field: current + 1, "updated_at": datetime.utcnow().isoformat()}
            ).eq("date", today).execute()
        except Exception as e:
            log.error(f"Increment stat error: {e}")

    async def get_todays_stats(self) -> Dict:
        today = datetime.now().date().isoformat()
        try:
            r = self.client.table("daily_stats").select("*").eq("date", today).execute()
            return r.data[0] if r.data else {}
        except Exception:
            return {}

    async def log_habit(self, habit: str, completed: bool = True) -> bool:
        try:
            self.client.table("habits").insert({
                "date": datetime.now().date().isoformat(),
                "habit": habit, "completed": completed,
            }).execute()
            return True
        except Exception as e:
            log.error(f"Log habit error: {e}")
            return False

    async def get_todays_habits(self) -> List[Dict]:
        today = datetime.now().date().isoformat()
        try:
            r = self.client.table("habits").select("*").eq("date", today).execute()
            return r.data or []
        except Exception:
            return []
