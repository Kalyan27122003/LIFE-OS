# ================================================================
#  agents/briefer_agent.py
# ================================================================

import logging
from datetime import datetime
from tools.telegram_tool import TelegramTool
from tools.calendar_tool import CalendarTool
from tools.notion_tool import NotionTool
from tools.gmail_tool import GmailTool
from memory.vector_memory import VectorMemory
from database.db import Database
from config.groq_brain import ask_groq
from config.settings import settings

log = logging.getLogger("BrieferAgent")


class BrieferAgent:
    def __init__(self):
        self.telegram = TelegramTool()
        self.calendar = CalendarTool()
        self.notion = NotionTool()
        self.gmail = GmailTool()
        self.memory = VectorMemory()
        self.db = Database()

    async def send_morning_brief(self):
        log.info("Compiling morning brief...")
        events = self.calendar.get_todays_events()
        tasks = await self.notion.get_todays_tasks()
        overdue = await self.notion.get_overdue_tasks()
        emails = self.gmail.get_unread_emails(max_results=5)

        email_text = f"• {len(emails)} unread" if emails else "• Inbox clear ✨"
        if overdue:
            email_text += f"\n• ⚠️ {len(overdue)} overdue task(s)!"

        context = (
            f"Day: {datetime.now().strftime('%A')}, "
            f"meetings: {len(events)}, tasks due: {len(tasks)}, "
            f"overdue: {len(overdue)}, emails: {len(emails)}"
        )
        prefs = self.memory.recall_preferences("morning routine focus", n=2)
        if prefs:
            context += f". User prefs: {'; '.join(prefs)}"

        focus = await ask_groq(
            f"You are {settings.user_name}'s coach. Write a sharp 1-2 sentence focus tip. No fluff.",
            context, fast=True,
        )

        await self.telegram.send_morning_brief({
            "calendar": self.calendar.format_for_brief(events),
            "tasks": self.notion.format_for_brief(tasks),
            "emails": email_text,
            "focus": focus,
        })
        log.info("Morning brief sent!")

    async def send_evening_summary(self):
        log.info("Compiling evening summary...")
        pending = await self.notion.get_all_pending()
        tomorrow = self.calendar.get_tomorrows_events()
        stats = await self.db.get_todays_stats()

        await self.telegram.send_evening_summary({
            "completed": "• See Notion for completed tasks ✅",
            "pending": self.notion.format_for_brief(pending) if pending else "• All done! 🎉",
            "emails": stats.get("emails_processed", 0),
            "tasks": stats.get("tasks_created", 0),
            "meetings": stats.get("meetings_booked", 0),
            "replies": stats.get("replies_sent", 0),
            "tomorrow": self.calendar.format_for_brief(tomorrow),
        })
        log.info("Evening summary sent!")

    async def get_current_status(self) -> str:
        events = self.calendar.get_todays_events()
        tasks = await self.notion.get_todays_tasks()
        emails = self.gmail.get_unread_emails(max_results=5)
        stats = await self.db.get_todays_stats()
        now = datetime.now().strftime("%I:%M %p")
        return (
            f"📊 <b>Status at {now}</b>\n\n"
            f"📅 <b>Today ({len(events)} events)</b>\n{self.calendar.format_for_brief(events)}\n\n"
            f"✅ <b>Tasks ({len(tasks)} pending)</b>\n{self.notion.format_for_brief(tasks)}\n\n"
            f"📧 <b>Inbox:</b> {len(emails)} unread\n\n"
            f"🤖 <b>Agent today:</b> "
            f"{stats.get('emails_processed',0)} emails · "
            f"{stats.get('tasks_created',0)} tasks · "
            f"{stats.get('replies_sent',0)} replies"
        )
