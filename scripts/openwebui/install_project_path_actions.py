import json
import time

from open_webui.models.functions import FunctionForm, FunctionMeta, Functions
from open_webui.utils.plugin import load_function_module_by_id


USER_ID = "3d67f125-03f5-4b4f-81e9-a7dfdb993890"
ACTION_ID = "workspace_project_actions"

CONTENT = r'''"""
title: Workspace Project Actions
author: Codex
version: 1.0
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMGRhNWQ5IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTMgNmgxOGExIDEgMCAwIDEgMSAxdjExYTEgMSAwIDAgMS0xIDFIM2ExIDEgMCAwIDEtMS0xVjdhMSAxIDAgMCAxIDEtMXoiLz48cGF0aCBkPSJNMiA5aDIwIi8+PHBhdGggZD0iTTcgM3Y2Ii8+PC9zdmc+
"""

import json
import os
import re
import sqlite3
import time
from pathlib import Path

from pydantic import BaseModel


actions = [
    {"id": "set", "name": "Set Path From Message"},
    {"id": "show", "name": "Show Current Path"},
    {"id": "clear", "name": "Clear Current Path"},
]


class Action:
    class Valves(BaseModel):
        workspace_root: str = os.getenv("OPEN_WEBUI_WORKSPACE_ROOT", "/workspace/project")
        fallback_path: str = "."

    PROJECT_CONTEXT_TABLE = "workspace_project_context"

    def __init__(self):
        self.valves = self.Valves()
        self.workspace_root = Path(self.valves.workspace_root).resolve()
        self.db_path = Path("/app/backend/data/webui.db")

    def _db(self):
        return sqlite3.connect(str(self.db_path))

    def _ensure_context_table(self):
        with self._db() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.PROJECT_CONTEXT_TABLE} (
                    user_id TEXT PRIMARY KEY,
                    project_path TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            conn.commit()

    def _safe_workspace_path(self, relative_path: str) -> Path:
        target = (self.workspace_root / (relative_path or ".")).resolve()
        if self.workspace_root not in target.parents and target != self.workspace_root:
            raise ValueError("Path must stay inside workspace root")
        return target

    def _extract_last_user_text(self, body: dict) -> str:
        for item in reversed((body or {}).get("messages", [])):
            if item.get("role") != "user":
                continue
            content = item.get("content", "")
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                texts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                merged = "\n".join([t for t in texts if t]).strip()
                if merged:
                    return merged
        return ""

    def _extract_path_candidate(self, text: str) -> str:
        patterns = [
            r'(/workspace/project/[^\s"`\\]+)',
            r'(/workspace/[^\s"`\\]+)',
            r'((?:project|workspace)/[^\s"`\\]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).rstrip(".,;:")
        cleaned = text.strip().strip('`"\'').rstrip(".,;:")
        return cleaned

    def _set_path(self, user_id: str, project_path: str) -> dict:
        self._ensure_context_table()
        target = self._safe_workspace_path(project_path)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"{project_path} is not an existing directory in workspace")
        rel = "." if target == self.workspace_root else str(target.relative_to(self.workspace_root))
        now = int(time.time())
        with self._db() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.PROJECT_CONTEXT_TABLE} (user_id, project_path, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    project_path=excluded.project_path,
                    updated_at=excluded.updated_at
                """,
                (user_id, rel, now),
            )
            conn.commit()
        return {"project_path": rel, "abs_path": str(target), "updated_at": now}

    def _get_path(self, user_id: str) -> dict:
        self._ensure_context_table()
        with self._db() as conn:
            row = conn.execute(
                f"SELECT project_path, updated_at FROM {self.PROJECT_CONTEXT_TABLE} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            target = self._safe_workspace_path(self.valves.fallback_path)
            return {
                "project_path": ".",
                "abs_path": str(target),
                "updated_at": None,
                "source": "default_workspace_root",
            }
        rel, updated_at = row
        target = self._safe_workspace_path(rel)
        return {
            "project_path": rel,
            "abs_path": str(target),
            "updated_at": updated_at,
            "source": "saved_project_path",
        }

    def _clear_path(self, user_id: str) -> dict:
        self._ensure_context_table()
        with self._db() as conn:
            conn.execute(f"DELETE FROM {self.PROJECT_CONTEXT_TABLE} WHERE user_id = ?", (user_id,))
            conn.commit()
        return {"cleared": True, "project_path": ".", "abs_path": str(self.workspace_root)}

    async def action(self, body: dict, __user__=None, __event_emitter__=None, __id__=None):
        user_id = ((__user__ or {}).get("id") or "global")

        if __id__ == "show":
            info = self._get_path(user_id)
            return {"content": f"Aktueller Projektpfad: `{info['project_path']}` ({info['abs_path']})"}

        if __id__ == "clear":
            info = self._clear_path(user_id)
            return {"content": f"Projektpfad zurueckgesetzt auf `{info['project_path']}` ({info['abs_path']})."}

        text = self._extract_last_user_text(body)
        if not text:
            return {"content": "Kein Text gefunden. Schreibe z.B. `project/ebay` und nutze dann `Set Path From Message`."}
        candidate = self._extract_path_candidate(text)
        if not candidate:
            return {"content": "Kein Pfad erkannt. Schreibe z.B. `project/ebay`."}
        try:
            info = self._set_path(user_id, candidate)
        except Exception as exc:
            return {"content": f"Pfad konnte nicht gesetzt werden: {exc}"}
        return {"content": f"Projektpfad gesetzt: `{info['project_path']}` ({info['abs_path']})"}
'''


def upsert_action() -> str:
    form = FunctionForm(
        id=ACTION_ID,
        name="Workspace Project Actions",
        content=CONTENT,
        meta=FunctionMeta(
            description="Setzt/zeigt/loescht den aktiven Projektpfad fuer Workspace-Agenten pro Benutzer.",
        ),
    )
    function_module, function_type, frontmatter = load_function_module_by_id(ACTION_ID, content=CONTENT)
    form.meta.manifest = frontmatter

    existing = Functions.get_function_by_id(ACTION_ID)
    now = int(time.time())
    if existing is None:
        created = Functions.insert_new_function(USER_ID, function_type, form)
        Functions.update_function_by_id(
            ACTION_ID,
            {
                "is_active": True,
                "is_global": True,
                "updated_at": now,
            },
        )
        return "created" if created else "failed"

    Functions.update_function_by_id(
        ACTION_ID,
        {
            "name": form.name,
            "content": CONTENT,
            "meta": form.meta.model_dump(),
            "type": function_type,
            "is_active": True,
            "is_global": True,
            "updated_at": now,
        },
    )
    return "updated"


if __name__ == "__main__":
    print(json.dumps({"workspace_project_actions": upsert_action()}, ensure_ascii=False))
