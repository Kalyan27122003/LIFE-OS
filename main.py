# ================================================================
#  PERSONAL LIFE OS v2 — Windows + Python 3.12 Final Fix
#  Root cause: asyncio.new_event_loop() + loop.close() before
#  Telegram's run_polling() causes "Event loop is closed" error.
#  Solution: Use nest_asyncio + single persistent event loop.
# ================================================================

import asyncio
import logging
import sys
import nest_asyncio                          # pip install nest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.orchestrator import OrchestratorAgent
from agents.email_agent import EmailAgent
from agents.briefer_agent import BrieferAgent
from agents.finance_health_agent import FinanceAgent, HealthAgent
from tools.telegram_tool import TelegramTool
from database.db import Database
from config.settings import settings
from utils.logger import setup_logger
from tools.alarm_manager import alarm_manager, set_scheduler

# ── KEY FIX: allow nested event loops on Windows ──────────────
nest_asyncio.apply()

log = setup_logger("LifeOS")


# ── Scheduled jobs ─────────────────────────────────────────────
async def job_morning_brief():
    await BrieferAgent().send_morning_brief()

async def job_email_scan():
    await EmailAgent().scan_and_triage()

async def job_finance_check():
    await FinanceAgent().check_finance_emails()

async def job_evening_summary():
    await BrieferAgent().send_evening_summary()

async def job_health_nudge():
    await HealthAgent().send_midday_nudge()


async def main():
    log.info("=" * 55)
    log.info("🤖  PERSONAL LIFE OS v2  —  Starting Up")
    log.info("=" * 55)

    # Init database
    await Database().init()
    log.info("✅ Database ready")

    # Startup Telegram notification
    telegram = TelegramTool()
    await telegram.send(
        f"🟢 <b>Life OS is Online!</b>\n"
        f"Hi {settings.user_name}! Send /help to get started."
    )
    log.info("✅ Telegram notified")

    # AsyncIOScheduler shares the SAME event loop — no conflicts!
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(job_morning_brief,   CronTrigger(hour=7,  minute=0), id="morning")
    scheduler.add_job(job_email_scan,      "interval", minutes=30,          id="email_scan")
    scheduler.add_job(job_finance_check,   "interval", hours=6,             id="finance")
    scheduler.add_job(job_health_nudge,    CronTrigger(hour=12, minute=0), id="health")
    scheduler.add_job(job_evening_summary, CronTrigger(hour=21, minute=0), id="evening")
    scheduler.start()
    set_scheduler(scheduler)          # give AlarmManager access to scheduler
    alarm_manager.restore_on_startup() # reload saved alarms after restart

    log.info("✅ Scheduler running")
    log.info("   ☀️  Morning brief  : 7:00 AM")
    log.info("   📧  Email scan     : every 30 min")
    log.info("   💰  Finance check  : every 6 hrs")
    log.info("   🏃  Health nudge   : 12:00 PM")
    log.info("   🌙  Evening brief  : 9:00 PM")

    # Telegram listener — runs inside the SAME event loop via nest_asyncio
    log.info("📱 Telegram listener starting...")
    orchestrator = OrchestratorAgent()
    await telegram.start_listener(orchestrator.handle_command)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped.")
        sys.exit(0)