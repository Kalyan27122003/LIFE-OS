import streamlit as st
import asyncio
from database.db import Database

st.set_page_config(page_title="Life OS Dashboard")

st.title("🤖 Life OS Dashboard")

db = Database()

# run async function properly
stats = asyncio.run(db.get_todays_stats())
actions = asyncio.run(db.get_recent_actions())

st.subheader("📊 Today's Stats")

if stats:
    st.json(stats)
else:
    st.info("No stats yet")

st.subheader("⚡ Recent Actions")

if actions:
    for a in actions:
        st.write(f"• {a['description']}")
else:
    st.info("No actions logged")