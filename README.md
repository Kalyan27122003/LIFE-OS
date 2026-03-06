# 🤖 Personal Life OS — No Google Cloud Edition
### ⚡ Groq · 📱 Telegram · 📧 Gmail IMAP · ✅ Notion · 💰 Finance · 🏃 Health
### 💰 $0/month | ☁️ Runs 24/7 free | ✅ No Google Cloud needed!

---

## ✅ What Changed (vs Google Cloud version)

| Feature | Old | New |
|---------|-----|-----|
| Email read | Gmail API (needs Cloud Console) | **Gmail IMAP** (just App Password) |
| Email send | Gmail API | **Gmail SMTP** (built into Python) |
| Calendar | Google Calendar API | **Local JSON file** (no setup) |
| Auth | OAuth2 (complex) | **App Password** (2 min) |

Everything else is identical — same Groq AI, same Telegram, same Notion.

---

## 🚀 Setup (No Google Cloud — 20 minutes total)

### Step 1 — Gmail App Password (2 min)
```
1. Go to myaccount.google.com
2. Security → 2-Step Verification → Turn ON (if not already)
3. Security → App Passwords
4. App name: type "Life OS" → Generate
5. Copy the 16-character password
```
Paste it in `.env` as `GMAIL_APP_PASSWORD`. That's it — no Google Cloud!

### Step 2 — Groq API Key (2 min)
```
1. Go to console.groq.com
2. Sign up → API Keys → Create key
3. Paste in .env as GROQ_API_KEY
```

### Step 3 — Telegram Bot (3 min)
```
1. Open Telegram → search @BotFather
2. Send /newbot → follow prompts → copy token
3. Paste in .env as TELEGRAM_BOT_TOKEN
4. Get your Chat ID:
   Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   Send a message to bot first, then visit the URL
   Find "chat":{"id": YOUR_ID}
```

### Step 4 — Notion (5 min)
```
1. Go to notion.so/my-integrations → New integration
2. Copy Internal Integration Token → paste in .env
3. In Notion: create a database with these properties:
   • Name (title)
   • Priority (select: High / Medium / Low)
   • Status (select: To Do / In Progress / Done)
   • Due Date (date)
   • Source (text)
   • Notes (text)
4. Open the database → ... menu → Add connections → your integration
5. Copy database ID from URL → paste in .env
```

### Step 5 — Supabase (5 min)
```
1. Go to supabase.com → New project (free)
2. Settings → API → copy Project URL and anon key
3. SQL Editor → New Query → paste database/schema.sql → Run
```

### Step 6 — Run it!
```bash
# Install
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env → fill in all your keys

# Start
python main.py
```

Open Telegram → find your bot → send `/start` 🎉

---

## 📱 Telegram Commands

```
/brief     → Full status: calendar + tasks + emails
/tasks     → Today's tasks from Notion
/calendar  → Today + tomorrow schedule
/emails    → Inbox summary
/stats     → Agent activity today
/finance   → Finance monitoring status
/health    → Habits tracker
/goals     → Active goals from Notion
/week      → This week overview
/undo      → Undo last action
/pause     → Pause the agent
/resume    → Resume the agent
/water     → Log a glass of water
/help      → All commands

💬 Natural language (just type!):
"Add task: Call dentist by Friday"
"Book meeting tomorrow at 3pm"
"Summarize my last 10 emails"
"Log exercise"
"Remember I prefer meetings after 2pm"
"What should I focus on today?"
```

---

## 📁 Project Structure

```
life-os/
├── main.py                   ← Start here
├── requirements.txt
├── .env.example             ← Copy to .env
│
├── config/
│   ├── settings.py          ← All config
│   └── groq_brain.py        ← Groq AI (shared)
│
├── agents/
│   ├── orchestrator.py      ← Routes Telegram commands
│   ├── email_agent.py       ← IMAP triage + SMTP replies
│   ├── briefer_agent.py     ← Morning + evening briefs
│   ├── finance_agent.py     ← Bank email monitoring
│   └── health_agent.py      ← Nudges + habit tracking
│
├── tools/
│   ├── telegram_tool.py     ← 📱 Mobile control center
│   ├── gmail_tool.py        ← IMAP read + SMTP send
│   ├── calendar_tool.py     ← Local JSON calendar
│   └── notion_tool.py       ← Tasks + goals
│
├── memory/
│   └── vector_memory.py     ← ChromaDB long-term memory
│
├── database/
│   ├── db.py                ← Supabase operations
│   └── schema.sql           ← Run once in Supabase
│
├── data/
│   └── calendar.json        ← Auto-created (your events)
│
└── utils/
    └── logger.py
```

---

## 💰 Monthly Cost: $0

| Service | Free Limit | Usage |
|---------|-----------|-------|
| Groq | 14,400 req/day | ~100-300/day |
| Gmail IMAP/SMTP | Unlimited | ✅ |
| Telegram Bot | Free forever | ✅ |
| Notion API | Unlimited | ✅ |
| Supabase | 500 MB | ~5 MB/mo |
| ChromaDB | Local, unlimited | ✅ |
| Railway | 750 hr/mo | ✅ |

---

## 🔧 Troubleshooting

**Gmail IMAP connection fails?**
- Check 2-Step Verification is ON
- Re-generate App Password
- Make sure IMAP is enabled: Gmail → Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP

**Notion tasks not showing?**
- Make sure you shared the database with your integration
- Check column names match exactly (Name, Priority, Status, Due Date)

**Telegram bot not responding?**
- Make sure TELEGRAM_CHAT_ID is YOUR chat ID (not the bot's)
- Send /start to the bot first
# LIFE-OS
