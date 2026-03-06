# ================================================================
#  config/groq_brain.py — Groq AI shared by all agents
# ================================================================

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from config.settings import settings
from typing import List, Dict, Optional
import asyncio
import json
import logging

log = logging.getLogger("GroqBrain")


def get_llm(fast: bool = False) -> ChatGroq:
    model = settings.groq_fast_model if fast else settings.groq_model
    return ChatGroq(
        model=model,
        api_key=settings.groq_api_key,
        temperature=0.1,
        max_tokens=2048,
        request_timeout=30,
    )


async def ask_groq(
    system_prompt: str,
    user_message: str,
    fast: bool = False,
    history: Optional[List[Dict]] = None,
) -> str:
    llm = get_llm(fast=fast)
    messages = [SystemMessage(content=system_prompt)]
    if history:
        for h in history[-6:]:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            else:
                messages.append(AIMessage(content=h["content"]))
    messages.append(HumanMessage(content=user_message))
    try:
        response = await llm.ainvoke(messages)
        return response.content.strip()
    except Exception as e:
        log.error(f"Groq error: {e}")
        if not fast:
            await asyncio.sleep(2)
            return await ask_groq(system_prompt, user_message, fast=True)
        raise


async def ask_groq_json(
    system_prompt: str,
    user_message: str,
    fast: bool = True,
) -> dict:
    full_sys = system_prompt + "\n\nReturn ONLY valid JSON. No markdown, no explanation."
    raw = await ask_groq(full_sys, user_message, fast=fast)
    clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(clean)
    except Exception as e:
        log.error(f"JSON parse error: {e} | Raw: {raw[:200]}")
        return {}
