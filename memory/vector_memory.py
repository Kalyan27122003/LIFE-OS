# ================================================================
#  memory/vector_memory.py — Long-term memory with ChromaDB (FREE)
# ================================================================

import logging
from datetime import datetime
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

log = logging.getLogger("Memory")


class VectorMemory:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path="./memory/chroma_db",
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.prefs = self.client.get_or_create_collection("preferences")
        self.decisions = self.client.get_or_create_collection("decisions")
        self.contacts = self.client.get_or_create_collection("contacts")
        self.facts = self.client.get_or_create_collection("facts")
        log.info("Memory initialized")

    def remember_preference(self, preference: str):
        self.prefs.add(
            documents=[preference],
            metadatas=[{"ts": datetime.now().isoformat()}],
            ids=[f"pref_{datetime.now().timestamp():.0f}"]
        )

    def remember_contact(self, email: str, name: str, notes: str):
        doc_id = f"c_{email.replace('@','_at_').replace('.','_')}"
        try:
            self.contacts.upsert(
                documents=[f"{name}: {notes}"],
                metadatas=[{"email": email, "name": name}],
                ids=[doc_id]
            )
        except Exception as e:
            log.error(f"Contact memory error: {e}")

    def remember_fact(self, fact: str, category: str = "general"):
        self.facts.add(
            documents=[fact],
            metadatas=[{"category": category, "ts": datetime.now().isoformat()}],
            ids=[f"fact_{category}_{datetime.now().timestamp():.0f}"]
        )

    def remember_decision(self, situation: str, decision: str):
        self.decisions.add(
            documents=[f"{situation} → {decision}"],
            metadatas=[{"ts": datetime.now().isoformat()}],
            ids=[f"dec_{datetime.now().timestamp():.0f}"]
        )

    def recall_preferences(self, query: str, n: int = 3) -> List[str]:
        try:
            count = self.prefs.count()
            if count == 0: return []
            r = self.prefs.query(query_texts=[query], n_results=min(n, count))
            return r["documents"][0] if r["documents"] else []
        except Exception:
            return []

    def recall_contact(self, email: str) -> Optional[str]:
        try:
            if self.contacts.count() == 0: return None
            r = self.contacts.query(query_texts=[email], n_results=1)
            return r["documents"][0][0] if r["documents"] and r["documents"][0] else None
        except Exception:
            return None

    def recall_facts(self, query: str, n: int = 3) -> List[str]:
        try:
            count = self.facts.count()
            if count == 0: return []
            r = self.facts.query(query_texts=[query], n_results=min(n, count))
            return r["documents"][0] if r["documents"] else []
        except Exception:
            return []

    def get_email_context(self, sender: str, subject: str) -> str:
        parts = []
        contact = self.recall_contact(sender)
        if contact:
            parts.append(f"Contact: {contact}")
        prefs = self.recall_preferences(f"email {subject}", n=2)
        if prefs:
            parts.append(f"Preferences: {'; '.join(prefs)}")
        return "\n".join(parts) or "No prior context."

    def learn_correction(self, original: str, correction: str):
        self.remember_preference(f"When {original}, prefer: {correction}")
        self.remember_decision(original, correction)
