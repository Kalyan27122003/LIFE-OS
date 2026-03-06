# ================================================================
#  agents/finance_agent.py
# ================================================================

import logging
from typing import Dict
from tools.gmail_tool import GmailTool
from tools.telegram_tool import TelegramTool
from database.db import Database
from config.groq_brain import ask_groq_json
from config.settings import settings

log = logging.getLogger("FinanceAgent")


class FinanceAgent:
    def __init__(self):
        self.gmail = GmailTool()
        self.telegram = TelegramTool()
        self.db = Database()

    async def check_finance_emails(self):
        log.info("Scanning finance emails...")
        # Search for bank / transaction emails
        finance_emails = self.gmail.search_emails(
            'SUBJECT "transaction" OR SUBJECT "debit" OR SUBJECT "credited" OR SUBJECT "payment"',
            max_results=10,
        )
        for email in finance_emails:
            if await self.db.is_processed(f"fin_{email['id']}"):
                continue
            await self._process(email)
            await self.db.log_email(
                f"fin_{email['id']}", email["subject"],
                email["sender"], "finance", "processed"
            )

    async def _process(self, email: Dict):
        data = await ask_groq_json(
            """Extract financial data from this email. Return JSON:
{
  "is_transaction": true or false,
  "type": "debit|credit|invoice|other",
  "amount": number or null,
  "merchant": "name or null",
  "category": "food|transport|shopping|bills|salary|transfer|other",
  "is_unusual": true or false,
  "summary": "one line"
}""",
            f"Subject: {email['subject']}\nBody: {email['body'][:600]}",
        )
        if not data or not data.get("is_transaction"):
            return
        amount = data.get("amount") or 0
        merchant = data.get("merchant", "Unknown")
        category = data.get("category", "other")

        if data.get("type") == "debit" and (
            amount > settings.unusual_spend_threshold or data.get("is_unusual")
        ):
            await self.telegram.send_finance_alert(amount, merchant, category)
            await self.db.log_action(
                "finance_alert", f"₹{amount} at {merchant}",
                {"amount": amount, "merchant": merchant, "category": category}
            )

    async def get_spending_summary(self) -> str:
        return (
            f"💰 <b>Finance Monitor</b>\n\n"
            f"✅ Active — scanning bank emails every 6 hours\n"
            f"🔔 Alert threshold: ₹{settings.unusual_spend_threshold:,.0f} per transaction\n\n"
            f"<i>Make sure bank alert emails land in your Gmail inbox.</i>"
        )


# ================================================================
#  agents/health_agent.py
# ================================================================

import logging
from datetime import datetime
from tools.telegram_tool import TelegramTool
from database.db import Database
from config.groq_brain import ask_groq
from config.settings import settings

log = logging.getLogger("HealthAgent")


class HealthAgent:
    def __init__(self):
        self.telegram = TelegramTool()
        self.db = Database()

    async def send_midday_nudge(self):
        nudge = await ask_groq(
            f"You are {settings.user_name}'s health coach. "
            f"Short midday health nudge. 2-3 lines max. "
            f"Goals: {settings.daily_water_glasses} glasses water, "
            f"{settings.sleep_target_hours}h sleep.",
            f"It's noon on {datetime.now().strftime('%A')}. Give a nudge.",
            fast=True,
        )
        await self.telegram.send_health_nudge(nudge)
        await self.telegram.send(
            f"💧 <b>Hydration Reminder</b>\n"
            f"Goal: {settings.daily_water_glasses} glasses today\n"
            f"Type /water to log a glass ✅"
        )

    async def log_habit(self, habit: str) -> str:
        ok = await self.db.log_habit(habit)
        return f"✅ Logged: <b>{habit}</b>" if ok else f"❌ Failed to log: {habit}"

    async def get_habits_summary(self) -> str:
        habits = await self.db.get_todays_habits()
        if not habits:
            return (
                "🏃 <b>Health Tracker</b>\n\n"
                "No habits logged yet today.\n\n"
                "Try typing:\n"
                "• <i>\"Log water\"</i>\n"
                "• <i>\"Log exercise\"</i>\n"
                "• <i>\"Log sleep 8h\"</i>"
            )
        done = [h for h in habits if h["completed"]]
        lines = "\n".join([
            f"{'✅' if h['completed'] else '❌'} {h['habit']}" for h in habits
        ])
        return f"🏃 <b>Habits Today ({len(done)}/{len(habits)})</b>\n\n{lines}"
