# ================================================================
#  agents/email_agent.py — Smart email triage using IMAP/SMTP
# ================================================================

import logging
from typing import Dict, List, Optional
from tools.gmail_tool import GmailTool
from tools.notion_tool import NotionTool
from tools.telegram_tool import TelegramTool
from tools.calendar_tool import CalendarTool
from memory.vector_memory import VectorMemory
from database.db import Database
from config.groq_brain import ask_groq, ask_groq_json
from config.settings import settings

log = logging.getLogger("EmailAgent")


class EmailAgent:
    def __init__(self):
        self.gmail = GmailTool()
        self.notion = NotionTool()
        self.telegram = TelegramTool()
        self.calendar = CalendarTool()
        self.memory = VectorMemory()
        self.db = Database()
        # Store pending drafts for approval {email_id: {email, draft}}
        self._pending_replies: Dict = {}

    async def scan_and_triage(self):
        emails = self.gmail.get_unread_emails()
        if not emails:
            log.info("Inbox clear.")
            return

        log.info(f"Triaging {len(emails)} emails...")

        for email in emails:
            if await self.db.is_processed(email["id"]):
                continue
            ctx = self.memory.get_email_context(email["sender"], email["subject"])
            cls = await self._classify(email, ctx)
            await self._act(email, cls)
            await self.db.log_email(
                email["id"], email["subject"],
                email["sender"], cls.get("category","fyi"), cls.get("action","ignore")
            )
            await self.db.increment_stat("emails_processed")

    async def _classify(self, email: Dict, memory_ctx: str) -> Dict:
        return await ask_groq_json(
            system_prompt=f"""You are an AI email assistant for {settings.user_name}.
Classify this email with full context.

User context: {memory_ctx}

Return JSON:
{{
  "category": "urgent|action|meeting_request|fyi|spam|newsletter",
  "urgency": "high|medium|low",
  "summary": "one sentence summary",
  "action": "send_reply|create_task|book_meeting|ignore|unsubscribe",
  "draft_reply": "complete reply text if action=send_reply, else null",
  "task_name": "task name if action=create_task, else null",
  "task_priority": "High|Medium|Low",
  "due_date": "YYYY-MM-DD if deadline exists, else null",
  "meeting_date": "YYYY-MM-DD if meeting request, else null",
  "meeting_time": "HH:MM if found, else null",
  "sender_name": "first name of sender",
  "requires_approval": true
}}""",
            user_message=(
                f"From: {email['sender']}\n"
                f"Subject: {email['subject']}\n"
                f"Body:\n{email['body'][:1500]}"
            ),
        ) or {"category": "fyi", "action": "ignore", "urgency": "low",
              "summary": email["snippet"], "draft_reply": None,
              "task_name": None, "task_priority": "Medium", "due_date": None,
              "meeting_date": None, "meeting_time": None,
              "sender_name": "", "requires_approval": True}

    async def _act(self, email: Dict, cls: Dict):
        category = cls.get("category", "fyi")
        action = cls.get("action", "ignore")

        # Mark read
        self.gmail.mark_as_read(email.get("imap_id", ""))

        # ── URGENT ────────────────────────────────────────────
        if category == "urgent":
            await self.telegram.send_email_alert(
                subject=email["subject"], sender=email["sender"],
                summary=cls.get("summary",""), urgency="urgent",
                draft=cls.get("draft_reply"), email_id=email["id"],
            )
            if cls.get("draft_reply"):
                self._pending_replies[email["id"]] = {
                    "email": email, "draft": cls["draft_reply"]
                }

        # ── MEETING REQUEST ────────────────────────────────────
        elif category == "meeting_request" and cls.get("meeting_date"):
            await self._handle_meeting(email, cls)

        # ── ACTION ────────────────────────────────────────────
        elif category == "action" and action == "send_reply" and cls.get("draft_reply"):
            if settings.autonomy_level == "suggest":
                # Ask for approval via Telegram
                self._pending_replies[email["id"]] = {
                    "email": email, "draft": cls["draft_reply"]
                }
                await self.telegram.send_email_alert(
                    subject=email["subject"], sender=email["sender"],
                    summary=cls.get("summary",""), urgency="action",
                    draft=cls.get("draft_reply"), email_id=email["id"],
                )
            else:
                # Auto send
                sender_email = self.gmail.get_sender_email(email["sender"])
                if self.gmail.send_email(
                    to=sender_email,
                    subject=f"Re: {email['subject']}",
                    body=cls["draft_reply"],
                ):
                    await self.telegram.send(
                        f"✅ <b>Auto-replied</b> to {cls.get('sender_name', sender_email)}\n"
                        f"<i>{email['subject']}</i>"
                    )
                    await self.db.increment_stat("replies_sent")
                    self.memory.remember_decision(
                        f"Email from {email['sender']}", "Sent auto-reply"
                    )

        # ── CREATE TASK ────────────────────────────────────────
        if action == "create_task" and cls.get("task_name"):
            task_id = await self.notion.create_task(
                name=cls["task_name"],
                priority=cls.get("task_priority","Medium"),
                due_date=cls.get("due_date"),
                source=f"Email: {email['subject'][:50]}",
                notes=cls.get("summary",""),
            )
            if task_id:
                await self.telegram.send_task_created(
                    cls["task_name"], cls.get("due_date"),
                    cls.get("task_priority","Medium")
                )
                await self.db.log_action(
                    "task_created", cls["task_name"],
                    {"notion_id": task_id}, reversible=True
                )
                await self.db.increment_stat("tasks_created")

    async def _handle_meeting(self, email: Dict, cls: Dict):
        meeting_date = cls["meeting_date"]
        meeting_time = cls.get("meeting_time") or "14:00"
        sender_name = cls.get("sender_name", "contact")
        free_slots = self.calendar.find_free_slots(meeting_date)
        slots_str = "\n".join([f"• {s}" for s in free_slots]) if free_slots else "• Busy that day"

        if settings.autonomy_level in ("auto", "autopilot"):
            # Auto-book
            event = self.calendar.create_event(
                title=f"Meeting with {sender_name}",
                date_str=meeting_date,
                time_str=meeting_time,
                attendees=[self.gmail.get_sender_email(email["sender"])],
                description=f"From email: {email['subject']}",
            )
            if event:
                await self.telegram.send_event_created(
                    f"Meeting with {sender_name}", event["time_str"]
                )
                await self.db.increment_stat("meetings_booked")
                # Reply to confirm
                self.gmail.send_email(
                    to=self.gmail.get_sender_email(email["sender"]),
                    subject=f"Re: {email['subject']}",
                    body=(
                        f"Hi {sender_name},\n\n"
                        f"Confirmed! I've added our meeting on {meeting_date} at {meeting_time} to my calendar.\n"
                        f"Looking forward to it!\n\n{settings.user_name}"
                    ),
                )
        else:
            await self.telegram.send(
                f"📅 <b>Meeting Request</b>\n"
                f"<b>From:</b> {email['sender']}\n"
                f"<b>Requested:</b> {meeting_date} at {meeting_time}\n\n"
                f"<b>Your free slots that day:</b>\n{slots_str}\n\n"
                f"Reply: <i>\"Book meeting with {sender_name} on {meeting_date} at [time]\"</i>"
            )

    def get_pending_reply(self, email_id: str) -> Optional[Dict]:
        return self._pending_replies.get(email_id)

    async def send_pending_reply(self, email_id: str) -> bool:
        pending = self._pending_replies.pop(email_id, None)
        if not pending:
            return False
        email = pending["email"]
        draft = pending["draft"]
        sender_email = self.gmail.get_sender_email(email["sender"])
        sent = self.gmail.send_email(
            to=sender_email,
            subject=f"Re: {email['subject']}",
            body=draft,
        )
        if sent:
            await self.db.increment_stat("replies_sent")
        return sent

    async def summarize_inbox(self, count: int = 10) -> str:
        emails = self.gmail.get_unread_emails(max_results=count)
        if not emails:
            return "📧 <b>Inbox is clear!</b> No unread emails ✨"
        email_list = "\n".join([
            f"- [{e['sender'][:25]}] {e['subject'][:45]}"
            for e in emails
        ])
        summary = await ask_groq(
            "Summarize these emails briefly. Group by priority. Be concise.",
            f"{len(emails)} unread emails:\n{email_list}",
            fast=True,
        )
        return f"📧 <b>{len(emails)} Unread Emails</b>\n\n{summary}"
