-- Run this in Supabase SQL Editor (one time setup)
-- supabase.com → Your Project → SQL Editor → New Query → Paste → Run

CREATE TABLE IF NOT EXISTS action_log (
    id          SERIAL PRIMARY KEY,
    action_type TEXT NOT NULL,
    description TEXT,
    metadata    JSONB DEFAULT '{}',
    reversible  BOOLEAN DEFAULT false,
    reversed    BOOLEAN DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_log (
    id           SERIAL PRIMARY KEY,
    email_id     TEXT UNIQUE NOT NULL,
    subject      TEXT,
    sender       TEXT,
    category     TEXT,
    action_taken TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_stats (
    id                SERIAL PRIMARY KEY,
    date              DATE UNIQUE DEFAULT CURRENT_DATE,
    emails_processed  INT DEFAULT 0,
    tasks_created     INT DEFAULT 0,
    meetings_booked   INT DEFAULT 0,
    replies_sent      INT DEFAULT 0,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS habits (
    id         SERIAL PRIMARY KEY,
    date       DATE DEFAULT CURRENT_DATE,
    habit      TEXT NOT NULL,
    completed  BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

SELECT 'All tables created!' as status;
