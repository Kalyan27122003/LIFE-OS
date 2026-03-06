# ================================================================
#  agents/orchestrator.py — Routes ALL Telegram commands
# ================================================================

import logging
from datetime import datetime, timedelta
from typing import Optional
from config.groq_brain import ask_groq, ask_groq_json
from agents.email_agent import EmailAgent
from agents.briefer_agent import BrieferAgent
from agents.finance_health_agent import FinanceAgent, HealthAgent
from tools.notion_tool import NotionTool
from tools.calendar_tool import CalendarTool
from tools.alarm_manager import alarm_manager
from memory.vector_memory import VectorMemory
from database.db import Database
from config.settings import settings
import pytz
TZ = pytz.timezone(settings.timezone)

log = logging.getLogger("Orchestrator")


class OrchestratorAgent:
    def __init__(self):
        self.email_agent = EmailAgent()
        self.briefer = BrieferAgent()
        self.finance = FinanceAgent()
        self.health = HealthAgent()
        self.notion = NotionTool()
        self.calendar = CalendarTool()
        self.memory = VectorMemory()
        self.db = Database()

    async def handle_command(self, text: str, chat_id: str = None) -> str:
        text = text.strip()
        chat_id = chat_id or settings.telegram_chat_id

        # ── Button callbacks ───────────────────────────────────
        if text.startswith("callback:"):
            return await self._handle_callback(text[9:])

        # ── Direct slash commands ──────────────────────────────
        cmd = text.lower().lstrip("/")

        direct = {
            "brief": self.briefer.get_current_status,
            "status": self.briefer.get_current_status,
            "tasks": self._cmd_tasks,
            "task": self._cmd_tasks,
            "calendar": self._cmd_calendar,
            "schedule": self._cmd_calendar,
            "emails": self.email_agent.summarize_inbox,
            "inbox": self.email_agent.summarize_inbox,
            "stats": self._cmd_stats,
            "undo": self._cmd_undo,
            "finance": self.finance.get_spending_summary,
            "money": self.finance.get_spending_summary,
            "health": self.health.get_habits_summary,
            "habits": self.health.get_habits_summary,
            "goals": self._cmd_goals,
            "week": self._cmd_week,
            "water": lambda: self.health.log_habit("water"),
            "alarms": lambda: self._cmd_alarms(chat_id),
            "reminders": lambda: self._cmd_alarms(chat_id),
        }
        if cmd in direct:
            return await direct[cmd]()

        # ── Natural language — detect intent ───────────────────
        intent = await self._detect_intent(text)
        log.info(f"Intent: {intent} | Input: {text[:50]}")

        handlers = {
            "create_task":   lambda: self._handle_create_task(text),
            "check_calendar":lambda: self._cmd_calendar(),
            "check_tasks":   lambda: self._cmd_tasks(),
            "check_emails":  lambda: self.email_agent.summarize_inbox(),
            "get_brief":     lambda: self.briefer.get_current_status(),
            "book_meeting":  lambda: self._handle_book_meeting(text),
            "check_finance": lambda: self.finance.get_spending_summary(),
            "log_habit":     lambda: self._handle_log_habit(text),
            "remember_this": lambda: self._handle_remember(text),
            "week_view":     lambda: self._cmd_week(),
            "ask_ai":        lambda: self._handle_general(text),
            "set_alarm":     lambda: self._handle_set_alarm(text, chat_id),
            "cancel_alarm":  lambda: self._handle_cancel_alarm(text, chat_id),
            "list_alarms":   lambda: self._cmd_alarms(chat_id),
        }
        fn = handlers.get(intent, lambda: self._handle_general(text))
        return await fn()

    # ── INTENT DETECTION ──────────────────────────────────────

    async def _detect_intent(self, text: str) -> str:
        result = await ask_groq(
            """Classify this message as ONE label:
create_task | check_calendar | check_tasks | check_emails |
get_brief | book_meeting | check_finance | log_habit |
remember_this | week_view | ask_ai

Examples:
"add task call dentist friday" → create_task
"what's on my calendar tomorrow" → check_calendar
"my tasks" → check_tasks
"unread emails" → check_emails
"how am I doing" → get_brief
"book meeting with Ravi at 3pm tomorrow" → book_meeting
"how much did I spend" → check_finance
"I exercised" → log_habit
"remember I prefer calls in morning" → remember_this
"this week schedule" → week_view
"what is python" → ask_ai
"set alarm at 5pm" → set_alarm
"remind me to call John at 3pm" → set_alarm
"remind me in 30 minutes" → set_alarm
"cancel alarm 1" → cancel_alarm
"show my alarms" → list_alarms""",
            text, fast=True,
        )
        valid = ["create_task","check_calendar","check_tasks","check_emails",
                 "get_brief","book_meeting","check_finance","log_habit",
                 "remember_this","week_view","ask_ai",
                 "set_alarm","cancel_alarm","list_alarms"]
        r = result.strip().lower()
        return r if r in valid else "ask_ai"

    # ── COMMAND HANDLERS ──────────────────────────────────────

    async def _cmd_tasks(self) -> str:
        tasks = await self.notion.get_todays_tasks()
        overdue = await self.notion.get_overdue_tasks()
        out = f"✅ <b>Tasks ({len(tasks)} today)</b>\n\n{self.notion.format_for_brief(tasks)}"
        if overdue:
            out += f"\n\n⚠️ <b>Overdue ({len(overdue)})</b>\n"
            out += "\n".join([f"• {t['name']}" for t in overdue[:3]])
        return out

    async def _cmd_calendar(self) -> str:
        today = self.calendar.get_todays_events()
        tomorrow = self.calendar.get_tomorrows_events()
        return (
            f"📅 <b>Today ({len(today)} events)</b>\n{self.calendar.format_for_brief(today)}\n\n"
            f"📅 <b>Tomorrow ({len(tomorrow)} events)</b>\n{self.calendar.format_for_brief(tomorrow)}"
        )

    async def _cmd_stats(self) -> str:
        stats = await self.db.get_todays_stats()
        actions = await self.db.get_recent_actions(limit=5)
        action_list = "\n".join([
            f"• {a['action_type']}: {a['description'][:40]}" for a in actions
        ]) or "• No actions yet today"
        return (
            f"📊 <b>Agent Activity Today</b>\n\n"
            f"📧 Emails processed: {stats.get('emails_processed',0)}\n"
            f"✅ Tasks created: {stats.get('tasks_created',0)}\n"
            f"📅 Meetings booked: {stats.get('meetings_booked',0)}\n"
            f"💬 Replies sent: {stats.get('replies_sent',0)}\n\n"
            f"<b>Recent:</b>\n{action_list}"
        )

    async def _cmd_undo(self) -> str:
        actions = await self.db.get_recent_actions(limit=5)
        reversible = [a for a in actions if a.get("reversible") and not a.get("reversed")]
        if not reversible:
            return "⏪ Nothing to undo."
        last = reversible[0]
        await self.db.mark_reversed(last["id"])
        return f"⏪ <b>Marked as reversed:</b>\n<i>{last['description']}</i>"

    async def _cmd_goals(self) -> str:
        goals = await self.notion.get_active_goals()
        if not goals:
            return "🎯 <b>Goals</b>\n\nNo active goals in Notion.\nAdd goals to your Goals database."
        return "🎯 <b>Active Goals</b>\n\n" + "\n".join([f"• {g['name']}" for g in goals])

    async def _cmd_week(self) -> str:
        events = self.calendar.get_weeks_events()
        tasks = await self.notion.get_all_pending()
        return (
            f"📅 <b>This Week ({len(events)} events)</b>\n{self.calendar.format_for_brief(events[:8])}\n\n"
            f"✅ <b>Pending Tasks ({len(tasks)})</b>\n{self.notion.format_for_brief(tasks[:5])}"
        )

    # ── NATURAL LANGUAGE HANDLERS ─────────────────────────────

    async def _handle_create_task(self, text: str) -> str:
        data = await ask_groq_json(
            """Extract task details. Return JSON:
{"task_name":"clear name","priority":"High|Medium|Low","due_date":"YYYY-MM-DD or null","notes":"or null"}""",
            text,
        )
        if not data or not data.get("task_name"):
            return "❌ Try: <i>\"Add task: Call dentist by Friday\"</i>"
        task_id = await self.notion.create_task(
            name=data["task_name"], priority=data.get("priority","Medium"),
            due_date=data.get("due_date"), source="Telegram",
            notes=data.get("notes",""),
        )
        if task_id:
            await self.db.log_action("task_created", data["task_name"],
                                     {"notion_id": task_id}, reversible=True)
            await self.db.increment_stat("tasks_created")
            due = f" · due {data['due_date']}" if data.get("due_date") else ""
            return f"✅ <b>Task created!</b>\n{data['task_name']}{due}"
        return "❌ Failed. Check Notion connection in .env"

    async def _handle_book_meeting(self, text: str) -> str:
        today_str = datetime.now().strftime("%Y-%m-%d")
        data = await ask_groq_json(
            f"""Extract meeting details. Today is {today_str}. Return JSON:
{{"title":"title","date":"YYYY-MM-DD","time":"HH:MM","duration_mins":60,"attendee_email":"email or null","description":"or null"}}""",
            text,
        )
        if not data or not data.get("date"):
            return "❌ Try: <i>\"Book meeting with ravi@email.com tomorrow at 3pm\"</i>"

        event = self.calendar.create_event(
            title=data.get("title","Meeting"),
            date_str=data["date"],
            time_str=data.get("time","14:00"),
            duration_mins=data.get("duration_mins",60),
            attendees=[data["attendee_email"]] if data.get("attendee_email") else [],
            description=data.get("description",""),
        )
        if event:
            await self.db.log_action("meeting_booked", data.get("title","Meeting"),
                                     {"event_id": event["id"]}, reversible=True)
            await self.db.increment_stat("meetings_booked")
            return f"📅 <b>Meeting booked!</b>\n{event['title']}\n🕐 {event['time_str']} on {event['date']}"
        return "❌ Failed to book meeting."

    async def _handle_log_habit(self, text: str) -> str:
        habit = await ask_groq(
            "Extract the habit name being logged. Reply ONLY with the habit name. E.g. 'water', 'exercise', 'sleep 8h'",
            text, fast=True,
        )
        return await self.health.log_habit(habit.strip())

    async def _handle_remember(self, text: str) -> str:
        preference = await ask_groq(
            "Extract the user preference/fact to remember. Reply with a clear statement.",
            text, fast=True,
        )
        self.memory.remember_preference(preference)
        return f"🧠 <b>Remembered!</b>\n<i>{preference}</i>"

    async def _handle_general(self, text: str) -> str:
        facts = self.memory.recall_facts(text, n=2)
        ctx = f"Known about user: {'; '.join(facts)}" if facts else ""
        return await ask_groq(
            f"You are {settings.user_name}'s personal AI. "
            f"Answer concisely in Telegram HTML. Max 150 words. {ctx}",
            text,
        )

    async def _handle_callback(self, data: str) -> str:
        parts = data.split(":", 1)
        action, payload = parts[0], parts[1] if len(parts) > 1 else ""
        if action == "send":
            sent = await self.email_agent.send_pending_reply(payload)
            return "✅ Reply sent!" if sent else "❌ Reply not found (may have expired)."
        elif action == "skip":
            return "⏭ Skipped."
        return f"✅ Done: {action}"

    # ── ALARM COMMANDS ────────────────────────────────────────

    async def _cmd_alarms(self, chat_id: str = None) -> str:
        # chat_id passed from _relay via context; fallback to owner
        cid = chat_id or settings.telegram_chat_id
        return alarm_manager.format_alarms_list(cid)

    async def _handle_set_alarm(self, text: str, chat_id: str = None) -> str:
        cid = chat_id or settings.telegram_chat_id
        now = datetime.now(TZ)

        # Use Groq to parse the alarm details
        data = await ask_groq_json(
            f"""Extract alarm/reminder details from this message.
Today is {now.strftime('%Y-%m-%d')} and current time is {now.strftime('%H:%M')}.
Timezone: {settings.timezone}

Return JSON:
{{
  "message": "what to remind (e.g. 'Wake up!', 'Call John', 'Take medicine')",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "repeat": null or "daily" or "weekdays",
  "is_relative": true if "in X minutes/hours", false otherwise,
  "relative_minutes": number if is_relative, else null
}}

Examples:
"Set alarm at 6pm" → date=today, time=18:00, message="⏰ Alarm!"
"Remind me to call John at 5:30pm" → message="Call John"
"Wake me up at 7am tomorrow" → date=tomorrow
"Remind me in 30 minutes" → is_relative=true, relative_minutes=30
"Set daily alarm at 8am" → repeat="daily"
""",
            text,
        )

        if not data:
            return "❌ Couldn't understand the alarm. Try:\n<i>\"Set alarm at 6pm\"</i>\n<i>\"Remind me to call John at 5pm\"</i>"

        # Calculate fire time
        try:
            if data.get("is_relative") and data.get("relative_minutes"):
                fire_at = now + timedelta(minutes=int(data["relative_minutes"]))
            else:
                date_str = data.get("date") or now.strftime("%Y-%m-%d")
                time_str = data.get("time") or "09:00"
                fire_at = TZ.localize(
                    datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                )

            # Must be in the future
            if fire_at <= now:
                # If today's time passed, set for tomorrow
                fire_at = fire_at + timedelta(days=1)

            message = data.get("message") or "⏰ Reminder!"
            repeat = data.get("repeat")

            alarm = alarm_manager.add_alarm(
                chat_id=cid,
                message=message,
                fire_at=fire_at,
                repeat=repeat,
            )

            repeat_str = f"\n🔁 Repeats: {repeat}" if repeat else ""
            return (
                f"✅ <b>Alarm set!</b>\n"
                f"⏰ <b>{alarm['fire_at_str']}</b>{repeat_str}\n"
                f"📝 {message}\n\n"
                f"View all: /alarms\n"
                f"Cancel: /cancelalarm 1"
            )

        except Exception as e:
            log.error(f"Alarm set error: {e}")
            return "❌ Couldn't set alarm. Try: <i>\"Remind me at 5pm\"</i>"

    async def _handle_cancel_alarm(self, text: str, chat_id: str = None) -> str:
        cid = chat_id or settings.telegram_chat_id

        # Try to extract alarm number from text
        import re
        numbers = re.findall(r'\d+', text)
        if numbers:
            idx = int(numbers[0])
            cancelled = alarm_manager.cancel_alarm(cid, idx)
            if cancelled:
                return f"✅ <b>Alarm cancelled!</b>\n<i>{cancelled}</i>"
            return f"❌ No alarm #{idx} found. Use /alarms to see your list."

        # Cancel all if user says "cancel all"
        if "all" in text.lower():
            count = alarm_manager.cancel_all(cid)
            return f"✅ Cancelled all {count} alarm(s)."

        return "Which alarm to cancel?\nSend /alarms to see your list, then /cancelalarm 1"