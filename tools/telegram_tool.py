# ================================================================
#  tools/telegram_tool.py — Your mobile control center 📱
#  Password protected — users must enter password to access
# ================================================================

import logging
import json
import os
from datetime import datetime
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ParseMode
from config.settings import settings

log = logging.getLogger("TelegramTool")

# File to store approved users (persists across restarts)
APPROVED_USERS_FILE = "data/approved_users.json"


class TelegramTool:
    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.chat_id = settings.telegram_chat_id
        # In-memory set of approved chat IDs
        self._approved: set = self._load_approved()

    # ── APPROVED USERS STORAGE ────────────────────────────────

    def _load_approved(self) -> set:
        """Load approved users from file (survives restarts)."""
        os.makedirs("data", exist_ok=True)
        # Owner is always approved
        approved = {str(self.chat_id)}
        try:
            if os.path.exists(APPROVED_USERS_FILE):
                with open(APPROVED_USERS_FILE, "r") as f:
                    saved = json.load(f)
                    approved.update(str(uid) for uid in saved)
        except Exception:
            pass
        return approved

    def _save_approved(self):
        """Save approved users to file."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(APPROVED_USERS_FILE, "w") as f:
                json.dump(list(self._approved), f)
        except Exception as e:
            log.error(f"Save approved users error: {e}")

    def _is_approved(self, chat_id: str) -> bool:
        return str(chat_id) in self._approved

    def _approve_user(self, chat_id: str):
        self._approved.add(str(chat_id))
        self._save_approved()
        log.info(f"✅ New user approved: {chat_id}")

    def _remove_user(self, chat_id: str):
        self._approved.discard(str(chat_id))
        self._save_approved()
        log.info(f"❌ User removed: {chat_id}")

    async def send(self, message: str, buttons: list = None):
        try:
            markup = None
            if buttons:
                keyboard = [
                    [InlineKeyboardButton(b["text"], callback_data=b["data"]) for b in row]
                    for row in buttons
                ]
                markup = InlineKeyboardMarkup(keyboard)
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message[:4096],
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        except Exception as e:
            log.error(f"Telegram send failed: {e}")

    async def send_morning_brief(self, brief: dict):
        today = datetime.now().strftime("%A, %B %d")
        await self.send(
            f"☀️ <b>Good morning, {settings.user_name}!</b>\n"
            f"<i>{today}</i>\n\n"
            f"📅 <b>Today's Schedule</b>\n{brief.get('calendar','• Free day!')}\n\n"
            f"✅ <b>Top Priorities</b>\n{brief.get('tasks','• Nothing pending')}\n\n"
            f"📧 <b>Inbox</b>\n{brief.get('emails','• All clear')}\n\n"
            f"💡 <b>Focus Tip</b>\n<i>{brief.get('focus','Have a great day!')}</i>"
        )

    async def send_evening_summary(self, summary: dict):
        await self.send(
            f"🌙 <b>Evening Wrap-Up</b>\n\n"
            f"✅ <b>Completed today</b>\n{summary.get('completed','• Check Notion')}\n\n"
            f"⏭ <b>Rolling to Tomorrow</b>\n{summary.get('pending','• All done! 🎉')}\n\n"
            f"📊 <b>Today's Stats</b>\n"
            f"• 📧 Emails processed: {summary.get('emails', 0)}\n"
            f"• ✅ Tasks created: {summary.get('tasks', 0)}\n"
            f"• 📅 Meetings booked: {summary.get('meetings', 0)}\n"
            f"• 💬 Replies sent: {summary.get('replies', 0)}\n\n"
            f"📅 <b>Tomorrow</b>\n{summary.get('tomorrow','• Nothing scheduled')}"
        )

    async def send_email_alert(self, subject: str, sender: str, summary: str,
                                urgency: str, draft: str = None, email_id: str = None):
        emoji = "🔴" if urgency == "urgent" else "🟡"
        msg = (
            f"{emoji} <b>{urgency.upper()} EMAIL</b>\n"
            f"<b>From:</b> {sender[:50]}\n"
            f"<b>Subject:</b> {subject[:80]}\n\n"
            f"{summary}"
        )
        if draft:
            msg += f"\n\n<b>💬 Suggested reply:</b>\n<i>{draft[:300]}</i>"

        buttons = None
        if draft and email_id:
            safe_id = email_id[:20].replace(" ", "_")
            buttons = [[
                {"text": "✅ Send Reply", "data": f"send:{safe_id}"},
                {"text": "❌ Skip",        "data": f"skip:{safe_id}"},
            ]]
        await self.send(msg, buttons=buttons)

    async def send_task_created(self, name: str, due: str = None, priority: str = "Medium"):
        icons = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        icon = icons.get(priority, "✅")
        due_str = f" · due {due}" if due else ""
        await self.send(f"{icon} <b>Task created!</b>\n{name}{due_str}")

    async def send_event_created(self, title: str, time_str: str):
        await self.send(f"📅 <b>Meeting booked!</b>\n{title}\n🕐 {time_str}")

    async def send_finance_alert(self, amount: float, merchant: str, category: str):
        await self.send(
            f"💳 <b>Spend Alert</b>\n"
            f"₹{amount:,.0f} at {merchant}\n"
            f"Category: {category}"
        )

    async def send_health_nudge(self, nudge: str):
        await self.send(f"🏃 <b>Health Check</b>\n{nudge}")

    # ── LISTENER ──────────────────────────────────────────────

    async def start_listener(self, command_handler_fn):
        app = Application.builder().token(settings.telegram_bot_token).build()
        app.bot_data["handler"] = command_handler_fn
        app.bot_data["paused"] = False
        app.bot_data["tool"] = self  # reference to self for commands

        # /start — shows password prompt to new users
        app.add_handler(CommandHandler("start",  self._cmd_start))
        app.add_handler(CommandHandler("help",   self._cmd_help))
        app.add_handler(CommandHandler("pause",  self._cmd_pause))
        app.add_handler(CommandHandler("resume", self._cmd_resume))

        # Owner-only: remove a user
        app.add_handler(CommandHandler("removeuser", self._cmd_remove_user))
        # Owner-only: list all approved users
        app.add_handler(CommandHandler("users", self._cmd_list_users))

        for cmd in ["brief","tasks","calendar","emails","stats","undo",
                    "finance","health","goals","week","water","alarms","reminders"]:
            app.add_handler(CommandHandler(
                cmd, lambda u, c, _c=cmd: self._relay(u, c, _c)
            ))
        app.add_handler(CommandHandler("cancelalarm", self._cmd_cancelalarm))

        # All text messages — check password OR relay command
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self._handle_text
        ))
        app.add_handler(CallbackQueryHandler(self._handle_callback))

        log.info("📱 Telegram ready — password protected")
        log.info(f"   Password: {settings.bot_password}")
        await app.run_polling(drop_pending_updates=True)

    # ── COMMAND HANDLERS ──────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        user = update.effective_user
        name = user.first_name if user else "there"

        if self._is_approved(chat_id):
            await update.message.reply_html(
                f"👋 <b>Welcome back, {name}!</b>\n"
                f"Life OS is ready. Send /help to see commands."
            )
        else:
            await update.message.reply_html(
                f"👋 <b>Hi {name}!</b>\n\n"
                f"🔐 This is a <b>private AI assistant</b>.\n\n"
                f"Please enter the <b>access password</b> to continue:"
            )

    async def _cmd_help(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if not self._is_approved(chat_id):
            await update.message.reply_text("🔐 Please enter the password first.")
            return
        await update.message.reply_html(
            "<b>🤖 Life OS Commands</b>\n\n"
            "<b>📊 Status</b>\n"
            "/brief — Full status overview\n"
            "/tasks — Today's tasks\n"
            "/calendar — Today's schedule\n"
            "/emails — Inbox summary\n"
            "/stats — Agent activity today\n"
            "/week — This week overview\n\n"
            "<b>💼 Work</b>\n"
            "/finance — Finance monitoring\n"
            "/health — Habits tracker\n"
            "/goals — Active goals\n\n"
            "<b>⏰ Alarms & Reminders</b>\n"
            "/alarms — See all your alarms\n"
            "/cancelalarm 1 — Cancel alarm #1\n\n"
            "<b>⚙️ Control</b>\n"
            "/undo — Undo last action\n"
            "/pause — Pause agent\n"
            "/resume — Resume agent\n\n"
            "<b>💬 Just type anything!</b>\n"
            "<i>\"Set alarm at 6pm\"</i>\n"
            "<i>\"Remind me to call John at 5pm\"</i>\n"
            "<i>\"Remind me in 30 minutes\"</i>\n"
            "<i>\"Set daily alarm at 7am\"</i>\n"
            "<i>\"Add task: Call dentist by Friday\"</i>\n"
            "<i>\"Book meeting tomorrow at 3pm\"</i>"
        )

    async def _cmd_pause(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            await update.message.reply_text("⛔ Only the owner can pause the agent.")
            return
        ctx.application.bot_data["paused"] = True
        await update.message.reply_text("⏸ Agent paused. /resume to restart.")

    async def _cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not self._is_owner(update):
            await update.message.reply_text("⛔ Only the owner can resume the agent.")
            return
        ctx.application.bot_data["paused"] = False
        await update.message.reply_text("▶️ Agent resumed!")

    async def _cmd_remove_user(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Owner only: /removeuser <chat_id>"""
        if not self._is_owner(update):
            await update.message.reply_text("⛔ Owner only command.")
            return
        args = ctx.args
        if not args:
            await update.message.reply_text("Usage: /removeuser <chat_id>")
            return
        self._remove_user(args[0])
        await update.message.reply_text(f"✅ User {args[0]} removed.")

    async def _cmd_list_users(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Owner only: /users — list all approved users"""
        if not self._is_owner(update):
            await update.message.reply_text("⛔ Owner only command.")
            return
        users = list(self._approved)
        lines = "\n".join([
            f"• {uid} {'👑 (you)' if uid == str(self.chat_id) else ''}"
            for uid in users
        ])
        await update.message.reply_html(
            f"<b>👥 Approved Users ({len(users)})</b>\n\n{lines}\n\n"
            f"To remove: /removeuser &lt;chat_id&gt;"
        )

    # ── TEXT MESSAGE HANDLER ──────────────────────────────────

    async def _handle_text(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Handle all text — check password for new users, relay for approved."""
        chat_id = str(update.effective_chat.id)
        text = update.message.text.strip()
        user = update.effective_user
        name = user.first_name if user else "User"

        # ── Not approved yet — check if they entered password ──
        if not self._is_approved(chat_id):
            if text == settings.bot_password:
                # ✅ Correct password!
                self._approve_user(chat_id)
                await update.message.reply_html(
                    f"✅ <b>Access granted, {name}!</b>\n\n"
                    f"Welcome to Life OS 🤖\n"
                    f"Send /help to see all commands.\n\n"
                    f"<i>Just type anything to get started!</i>"
                )
                # Notify owner
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=f"🔔 New user joined Life OS!\n"
                         f"Name: {name}\n"
                         f"Chat ID: {chat_id}\n"
                         f"To remove: /removeuser {chat_id}",
                    parse_mode=ParseMode.HTML,
                )
                log.info(f"New user approved: {name} ({chat_id})")
            else:
                # ❌ Wrong password
                await update.message.reply_html(
                    "🔐 <b>Incorrect password.</b>\n\n"
                    "Please enter the correct access password to use Life OS."
                )
            return

        # ── Approved user — relay to orchestrator ─────────────
        await self._relay(update, ctx, text)

    async def _relay(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE, command: str):
        chat_id = str(update.effective_chat.id)
        if not self._is_approved(chat_id):
            await update.message.reply_text("🔐 Please enter the password first.")
            return
        if ctx.application.bot_data.get("paused") and not self._is_owner(update):
            await update.message.reply_text("⏸ Agent is currently paused.")
            return
        await update.message.reply_text("⏳ On it...")
        try:
            handler = ctx.application.bot_data["handler"]
            # Pass chat_id with command so alarm handlers know who's asking
            response = await handler(command, chat_id=chat_id)
            await update.message.reply_html(str(response)[:4096])
        except Exception as e:
            log.error(f"Relay error: {e}")
            await update.message.reply_text(f"❌ Error: {str(e)[:200]}")

    async def _cmd_cancelalarm(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = str(update.effective_chat.id)
        if not self._is_approved(chat_id):
            await update.message.reply_text("🔐 Please enter the password first.")
            return
        args = ctx.args
        text = f"cancel alarm {' '.join(args)}" if args else "cancel alarm"
        handler = ctx.application.bot_data["handler"]
        response = await handler(text, chat_id=chat_id)
        await update.message.reply_html(str(response)[:4096])

    async def _handle_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        chat_id = str(update.effective_chat.id)
        if not self._is_approved(chat_id):
            await query.edit_message_text("🔐 Access denied.")
            return
        handler = ctx.application.bot_data.get("handler")
        if handler:
            response = await handler(f"callback:{query.data}")
            await query.edit_message_text(str(response)[:4096], parse_mode=ParseMode.HTML)

    # ── SYNC ENTRY POINT (Windows / Python 3.12 fix) ─────────

    def run_polling(self, command_handler_fn):
        """
        Synchronous entry point — Telegram manages its own event loop.
        Fixes 'event loop already running' error on Windows + Python 3.12.
        Call this instead of await start_listener().
        """
        import asyncio
        from telegram.ext import Application

        app = Application.builder().token(settings.telegram_bot_token).build()
        app.bot_data["handler"] = command_handler_fn
        app.bot_data["paused"] = False
        app.bot_data["tool"] = self

        app.add_handler(CommandHandler("start",      self._cmd_start))
        app.add_handler(CommandHandler("help",       self._cmd_help))
        app.add_handler(CommandHandler("pause",      self._cmd_pause))
        app.add_handler(CommandHandler("resume",     self._cmd_resume))
        app.add_handler(CommandHandler("removeuser", self._cmd_remove_user))
        app.add_handler(CommandHandler("users",      self._cmd_list_users))

        for cmd in ["brief","tasks","calendar","emails","stats","undo",
                    "finance","health","goals","week","water","alarms","reminders"]:
            app.add_handler(CommandHandler(
                cmd, lambda u, c, _c=cmd: self._relay(u, c, _c)
            ))
        app.add_handler(CommandHandler("cancelalarm", self._cmd_cancelalarm))

        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self._handle_text
        ))
        app.add_handler(CallbackQueryHandler(self._handle_callback))

        log.info("📱 Telegram ready — password protected")
        log.info(f"   Password hint: set BOT_PASSWORD in .env")
        # run_polling() creates and manages its own event loop internally
        app.run_polling(drop_pending_updates=True)

    # ── AUTH HELPERS ──────────────────────────────────────────

    def _is_owner(self, update: Update) -> bool:
        """Only the original owner (your chat ID)."""
        return str(update.effective_chat.id) == str(self.chat_id)

    def _auth(self, update: Update) -> bool:
        """Legacy — kept for compatibility."""
        return self._is_approved(str(update.effective_chat.id))