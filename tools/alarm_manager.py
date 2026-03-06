# ================================================================
#  tools/alarm_manager.py — Real Telegram Alarms & Reminders
#  Alarms fire AT the exact time and ping you on Telegram!
#
#  Supports:
#    "Set alarm at 3:12pm"
#    "Remind me to call John at 5pm"
#    "Remind me in 30 minutes"
#    "Set alarm tomorrow at 8am"
#    "Wake me up at 7am daily"
#    /alarms  → see all your alarms
#    /cancelalarm 3 → cancel alarm #3
# ================================================================

import json
import os
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import pytz
from config.settings import settings

log = logging.getLogger("AlarmManager")

ALARMS_FILE = "data/alarms.json"
TZ = pytz.timezone(settings.timezone)

# Global scheduler reference (set from main.py)
_scheduler = None

def set_scheduler(scheduler):
    """Called from main.py to give AlarmManager access to the scheduler."""
    global _scheduler
    _scheduler = scheduler


class AlarmManager:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.alarms: List[Dict] = self._load()

    # ── CREATE ALARM ──────────────────────────────────────────

    def add_alarm(
        self,
        chat_id: str,
        message: str,
        fire_at: datetime,
        repeat: str = None,   # None | "daily" | "weekdays"
        alarm_id: str = None,
    ) -> Dict:
        """Create a new alarm and schedule it."""
        aid = alarm_id or f"alarm_{chat_id}_{datetime.now().timestamp():.0f}"

        alarm = {
            "id": aid,
            "chat_id": chat_id,
            "message": message,
            "fire_at": fire_at.isoformat(),
            "fire_at_str": fire_at.strftime("%I:%M %p, %b %d"),
            "repeat": repeat,
            "active": True,
            "created_at": datetime.now(TZ).isoformat(),
        }

        self.alarms.append(alarm)
        self._save()
        self._schedule_alarm(alarm)
        log.info(f"Alarm set: '{message}' at {alarm['fire_at_str']} for chat {chat_id}")
        return alarm

    def _schedule_alarm(self, alarm: Dict):
        """Add alarm to APScheduler."""
        if _scheduler is None:
            log.error("Scheduler not set! Call set_scheduler() from main.py")
            return

        fire_dt = datetime.fromisoformat(alarm["fire_at"])
        now = datetime.now(TZ)

        # Skip if already in the past
        if fire_dt.tzinfo is None:
            fire_dt = TZ.localize(fire_dt)
        if fire_dt <= now:
            log.info(f"Alarm {alarm['id']} is in the past, skipping.")
            return

        job_id = alarm["id"]

        if alarm.get("repeat") == "daily":
            from apscheduler.triggers.cron import CronTrigger
            _scheduler.add_job(
                _fire_alarm,
                CronTrigger(hour=fire_dt.hour, minute=fire_dt.minute, timezone=TZ),
                args=[alarm["id"], alarm["chat_id"], alarm["message"]],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=60,
            )
        else:
            from apscheduler.triggers.date import DateTrigger
            _scheduler.add_job(
                _fire_alarm,
                DateTrigger(run_date=fire_dt, timezone=TZ),
                args=[alarm["id"], alarm["chat_id"], alarm["message"]],
                id=job_id,
                replace_existing=True,
                misfire_grace_time=60,
            )

    def restore_on_startup(self):
        """Re-schedule all active alarms on bot restart."""
        now = datetime.now(TZ)
        restored = 0
        for alarm in self.alarms:
            if not alarm.get("active"):
                continue
            fire_dt = datetime.fromisoformat(alarm["fire_at"])
            if fire_dt.tzinfo is None:
                fire_dt = TZ.localize(fire_dt)
            # Skip one-time past alarms; keep repeating ones
            if fire_dt <= now and not alarm.get("repeat"):
                continue
            self._schedule_alarm(alarm)
            restored += 1
        if restored:
            log.info(f"Restored {restored} alarm(s) from file.")

    # ── CANCEL / LIST ─────────────────────────────────────────

    def cancel_alarm(self, chat_id: str, alarm_index: int) -> Optional[str]:
        """Cancel alarm by its display index (1-based) for a chat."""
        user_alarms = self.get_user_alarms(chat_id)
        if alarm_index < 1 or alarm_index > len(user_alarms):
            return None
        alarm = user_alarms[alarm_index - 1]
        # Deactivate in storage
        for a in self.alarms:
            if a["id"] == alarm["id"]:
                a["active"] = False
        self._save()
        # Remove from scheduler
        if _scheduler:
            try:
                _scheduler.remove_job(alarm["id"])
            except Exception:
                pass
        return alarm["message"]

    def cancel_all(self, chat_id: str) -> int:
        count = 0
        for alarm in self.alarms:
            if alarm["chat_id"] == chat_id and alarm["active"]:
                alarm["active"] = False
                if _scheduler:
                    try:
                        _scheduler.remove_job(alarm["id"])
                    except Exception:
                        pass
                count += 1
        self._save()
        return count

    def get_user_alarms(self, chat_id: str) -> List[Dict]:
        return [a for a in self.alarms
                if a["chat_id"] == chat_id and a["active"]]

    def format_alarms_list(self, chat_id: str) -> str:
        alarms = self.get_user_alarms(chat_id)
        if not alarms:
            return "⏰ <b>No active alarms.</b>\n\nTry: <i>\"Set alarm at 6pm\"</i>"
        lines = []
        for i, a in enumerate(alarms, 1):
            repeat_str = f" 🔁 {a['repeat']}" if a.get("repeat") else ""
            lines.append(f"{i}. ⏰ <b>{a['fire_at_str']}</b>{repeat_str}\n   {a['message']}")
        return (
            f"⏰ <b>Your Alarms ({len(alarms)})</b>\n\n"
            + "\n\n".join(lines)
            + "\n\nTo cancel: /cancelalarm 1"
        )

    def mark_fired(self, alarm_id: str):
        """Mark one-time alarm as inactive after it fires."""
        for a in self.alarms:
            if a["id"] == alarm_id and not a.get("repeat"):
                a["active"] = False
        self._save()

    # ── STORAGE ───────────────────────────────────────────────

    def _load(self) -> List[Dict]:
        try:
            if os.path.exists(ALARMS_FILE):
                with open(ALARMS_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save(self):
        with open(ALARMS_FILE, "w") as f:
            json.dump(self.alarms, f, indent=2, default=str)


# ── Global instance (shared across agents) ────────────────────
alarm_manager = AlarmManager()


# ── Alarm fire function (called by scheduler) ─────────────────
def _fire_alarm(alarm_id: str, chat_id: str, message: str):
    """This runs when an alarm fires. Sends Telegram message."""
    async def _send():
        from tools.telegram_tool import TelegramTool
        telegram = TelegramTool()
        now_str = datetime.now(TZ).strftime("%I:%M %p")
        await telegram.bot.send_message(
            chat_id=chat_id,
            text=f"⏰ <b>ALARM!</b> {now_str}\n\n{message}",
            parse_mode="HTML",
        )
        log.info(f"Alarm fired: {message} → chat {chat_id}")

    # Mark one-time alarm as done
    alarm_manager.mark_fired(alarm_id)

    # Run async send in a new event loop (called from scheduler thread)
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_send())
    finally:
        loop.close()