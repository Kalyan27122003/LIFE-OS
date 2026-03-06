# ================================================================
#  tools/notion_tool.py — Notion tasks + goals (FREE)
#  No Google Cloud needed — just Notion integration token
# ================================================================

import logging
from datetime import date
from typing import List, Dict, Optional
from notion_client import AsyncClient
from config.settings import settings

log = logging.getLogger("NotionTool")


class NotionTool:
    def __init__(self):
        self.client = AsyncClient(auth=settings.notion_token)
        self.tasks_db = settings.notion_tasks_db_id
        self.goals_db = settings.notion_goals_db_id

    # ── CREATE ────────────────────────────────────────────────

    async def create_task(
        self,
        name: str,
        priority: str = "Medium",
        due_date: Optional[str] = None,
        source: str = "Life OS",
        notes: str = "",
    ) -> Optional[str]:
        try:
            props = {
                "Name": {"title": [{"text": {"content": name}}]},
                "Priority": {"select": {"name": priority}},
                "Status": {"select": {"name": "To Do"}},
                "Source": {"rich_text": [{"text": {"content": source}}]},
            }
            if due_date:
                props["Due Date"] = {"date": {"start": due_date}}
            if notes:
                props["Notes"] = {"rich_text": [{"text": {"content": notes[:2000]}}]}

            result = await self.client.pages.create(
                parent={"database_id": self.tasks_db},
                properties=props,
            )
            log.info(f"Notion task created: {name}")
            return result["id"]
        except Exception as e:
            log.error(f"Notion create task failed: {e}")
            return None

    # ── READ ──────────────────────────────────────────────────

    async def get_todays_tasks(self) -> List[Dict]:
        today = date.today().isoformat()
        try:
            result = await self.client.databases.query(
                database_id=self.tasks_db,
                filter={
                    "and": [
                        {"property": "Status", "select": {"does_not_equal": "Done"}},
                        {
                            "or": [
                                {"property": "Due Date", "date": {"equals": today}},
                                {"property": "Due Date", "date": {"before": today}},
                                {"property": "Due Date", "date": {"is_empty": True}},
                            ]
                        }
                    ]
                },
                sorts=[{"property": "Priority", "direction": "descending"}],
                page_size=10,
            )
            return self._parse(result.get("results", []))
        except Exception as e:
            log.error(f"Notion get tasks failed: {e}")
            return []

    async def get_all_pending(self) -> List[Dict]:
        try:
            result = await self.client.databases.query(
                database_id=self.tasks_db,
                filter={"property": "Status", "select": {"does_not_equal": "Done"}},
                sorts=[{"property": "Priority", "direction": "descending"}],
                page_size=20,
            )
            return self._parse(result.get("results", []))
        except Exception as e:
            log.error(f"Notion get pending failed: {e}")
            return []

    async def get_overdue_tasks(self) -> List[Dict]:
        today = date.today().isoformat()
        try:
            result = await self.client.databases.query(
                database_id=self.tasks_db,
                filter={
                    "and": [
                        {"property": "Status", "select": {"does_not_equal": "Done"}},
                        {"property": "Due Date", "date": {"before": today}},
                    ]
                },
            )
            return self._parse(result.get("results", []))
        except Exception as e:
            return []

    async def mark_done(self, task_id: str) -> bool:
        try:
            await self.client.pages.update(
                page_id=task_id,
                properties={"Status": {"select": {"name": "Done"}}}
            )
            return True
        except Exception as e:
            log.error(f"Mark done failed: {e}")
            return False

    async def get_active_goals(self) -> List[Dict]:
        if not self.goals_db:
            return []
        try:
            result = await self.client.databases.query(
                database_id=self.goals_db,
                filter={"property": "Status", "select": {"equals": "Active"}},
                page_size=5,
            )
            goals = []
            for page in result.get("results", []):
                props = page.get("properties", {})
                name = ""
                if props.get("Name", {}).get("title"):
                    name = props["Name"]["title"][0]["text"]["content"]
                goals.append({"id": page["id"], "name": name})
            return goals
        except Exception as e:
            return []

    def _parse(self, pages: List) -> List[Dict]:
        tasks = []
        for page in pages:
            p = page.get("properties", {})
            name = ""
            if p.get("Name", {}).get("title"):
                name = p["Name"]["title"][0]["text"]["content"]
            priority = (p.get("Priority", {}).get("select") or {}).get("name", "Medium")
            due = (p.get("Due Date", {}).get("date") or {}).get("start", "")
            status = (p.get("Status", {}).get("select") or {}).get("name", "To Do")
            tasks.append({"id": page["id"], "name": name,
                          "priority": priority, "due_date": due, "status": status})
        return tasks

    def format_for_brief(self, tasks: List[Dict]) -> str:
        if not tasks:
            return "• All clear! No pending tasks 🎉"
        icons = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        lines = []
        for t in tasks[:5]:
            icon = icons.get(t["priority"], "⚪")
            due = f" · due {t['due_date']}" if t["due_date"] else ""
            lines.append(f"{icon} {t['name']}{due}")
        if len(tasks) > 5:
            lines.append(f"  … +{len(tasks)-5} more in Notion")
        return "\n".join(lines)
