# ================================================================
#  tools/calendar_tool.py
#  Local JSON calendar — No Google Cloud needed!
#  Events stored in calendar.json (syncs to Telegram)
#  You can also manually edit calendar.json anytime
# ================================================================

import json
import os
import logging
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from config.settings import settings
import pytz

log = logging.getLogger("CalendarTool")

CALENDAR_FILE = "data/calendar.json"
TZ = pytz.timezone(settings.timezone)


class CalendarTool:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(CALENDAR_FILE):
            self._save([])

    # ── READ EVENTS ───────────────────────────────────────────

    def get_todays_events(self) -> List[Dict]:
        return self._get_events_for_date(date.today())

    def get_tomorrows_events(self) -> List[Dict]:
        return self._get_events_for_date(date.today() + timedelta(days=1))

    def get_weeks_events(self) -> List[Dict]:
        today = date.today()
        events = []
        for i in range(7):
            events.extend(self._get_events_for_date(today + timedelta(days=i)))
        return sorted(events, key=lambda e: e.get("start_datetime", ""))

    def _get_events_for_date(self, target_date: date) -> List[Dict]:
        all_events = self._load()
        date_str = target_date.isoformat()
        return [
            e for e in all_events
            if e.get("date") == date_str and not e.get("deleted", False)
        ]

    # ── CREATE EVENTS ─────────────────────────────────────────

    def create_event(
        self,
        title: str,
        date_str: str,        # "YYYY-MM-DD"
        time_str: str,        # "HH:MM"  e.g. "14:00"
        duration_mins: int = 60,
        attendees: List[str] = None,
        description: str = "",
        location: str = "",
    ) -> Optional[Dict]:
        """Create a new calendar event and save to JSON."""
        try:
            # Parse datetime
            start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            end_dt = start_dt + timedelta(minutes=duration_mins)

            event = {
                "id": f"evt_{datetime.now().timestamp():.0f}",
                "title": title,
                "date": date_str,
                "time": time_str,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "duration_mins": duration_mins,
                "attendees": attendees or [],
                "description": description,
                "location": location,
                "time_str": start_dt.strftime("%I:%M %p"),
                "created_at": datetime.now().isoformat(),
                "deleted": False,
            }

            events = self._load()
            events.append(event)
            self._save(events)
            log.info(f"Event created: {title} on {date_str} at {time_str}")
            return event
        except Exception as e:
            log.error(f"Create event error: {e}")
            return None

    def delete_event(self, event_id: str) -> bool:
        """Soft-delete an event."""
        try:
            events = self._load()
            for e in events:
                if e["id"] == event_id:
                    e["deleted"] = True
            self._save(events)
            return True
        except Exception as e:
            log.error(f"Delete event error: {e}")
            return False

    def find_free_slots(self, date_str: str, duration_mins: int = 60) -> List[str]:
        """Find free time slots on a given date."""
        existing = self._get_events_for_date(
            date.fromisoformat(date_str)
        )

        # Build busy list
        busy = []
        for e in existing:
            try:
                s = datetime.fromisoformat(e["start_datetime"])
                en = datetime.fromisoformat(e["end_datetime"])
                busy.append((s, en))
            except Exception:
                pass

        # Check 30-min slots from after deep work until 6pm
        target = date.fromisoformat(date_str)
        start_hour = settings.deep_work_end_hour
        slots = []
        current = datetime(target.year, target.month, target.day, start_hour, 0)
        end_of_day = datetime(target.year, target.month, target.day, 18, 0)
        delta = timedelta(minutes=duration_mins)

        while current + delta <= end_of_day and len(slots) < 4:
            slot_end = current + delta
            is_free = all(
                slot_end <= b[0] or current >= b[1]
                for b in busy
            )
            if is_free:
                slots.append(current.strftime("%I:%M %p"))
            current += timedelta(minutes=30)

        return slots

    # ── FORMAT ────────────────────────────────────────────────

    def format_for_brief(self, events: List[Dict]) -> str:
        if not events:
            return "• No events — free day! ✨"
        return "\n".join([f"• {e['time_str']} — {e['title']}" for e in events])

    # ── STORAGE ───────────────────────────────────────────────

    def _load(self) -> List[Dict]:
        try:
            with open(CALENDAR_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save(self, events: List[Dict]):
        with open(CALENDAR_FILE, "w") as f:
            json.dump(events, f, indent=2, default=str)
