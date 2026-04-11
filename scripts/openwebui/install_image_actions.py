import json
import time

from open_webui.models.functions import FunctionForm, FunctionMeta, Functions
from open_webui.utils.plugin import load_function_module_by_id


USER_ID = "3d67f125-03f5-4b4f-81e9-a7dfdb993890"
ACTION_ID = "image_post_actions"

CONTENT = r'''"""
title: Image Post Actions
author: Codex
version: 1.0
icon_url: data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjNGY0NmU1IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCI+PHBhdGggZD0iTTEyIDN2NiIvPjxwYXRoIGQ9Ik0xNSAxMmgtNiIvPjxwYXRoIGQ9Ik0xOSAxMWE3IDcgMCAxIDEtMTQtMCA3IDcgMCAwIDEgMTQgMCIvPjwvc3ZnPg==
"""

import base64
import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel


actions = [
    {
        "id": "dat4x",
        "name": "Upscale DAT x4",
    },
    {
        "id": "fast",
        "name": "Upscale Fast",
    },
]


class Action:
    class Valves(BaseModel):
        a1111_base_url: str = os.getenv("AUTOMATIC1111_BASE_URL", "http://automatic1111-amd:7860/").rstrip("/")
        upscale_factor: float = 2.0
        output_dir: str = "/app/backend/data/uploads"
        fallback_to_latest: bool = True

    def __init__(self):
        self.valves = self.Valves()
        self.db_path = Path("/app/backend/data/webui.db")

    def _db(self):
        return sqlite3.connect(str(self.db_path))

    def _iter_dicts(self, value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from self._iter_dicts(item)
        elif isinstance(value, list):
            for item in value:
                yield from self._iter_dicts(item)

    def _extract_file_id_from_url(self, url: str):
        if not url:
            return None
        match = re.search(r"/api/v1/files/([a-f0-9-]+)", url)
        return match.group(1) if match else None

    def _lookup_file_by_id(self, file_id: str):
        with self._db() as conn:
            row = conn.execute(
                "select id, filename, meta, path from file where id = ?",
                (file_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "filename": row[1],
            "meta": json.loads(row[2]) if row[2] else {},
            "path": row[3],
        }

    def _latest_image_for_user(self, user_id: str):
        with self._db() as conn:
            row = conn.execute(
                """
                select id, filename, meta, path
                from file
                where user_id = ?
                order by created_at desc
                limit 1
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "filename": row[1],
            "meta": json.loads(row[2]) if row[2] else {},
            "path": row[3],
        }

    def _resolve_source_file(self, body: dict, user_id: str):
        for item in self._iter_dicts(body):
            file_type = str(item.get("type", "")).lower()
            file_id = item.get("id") or self._extract_file_id_from_url(item.get("url", ""))
            file_path = item.get("path")
            if file_path and Path(file_path).exists():
                return {
                    "id": file_id or "",
                    "filename": item.get("name") or Path(file_path).name,
                    "meta": item,
                    "path": file_path,
                }
            if file_id and file_type in {"image", ""}:
                hit = self._lookup_file_by_id(file_id)
                if hit and hit.get("path") and Path(hit["path"]).exists():
                    return hit
        if self.valves.fallback_to_latest:
            hit = self._latest_image_for_user(user_id)
            if hit and hit.get("path") and Path(hit["path"]).exists():
                return hit
        return None

    def _post_json(self, url: str, payload: dict) -> dict:
        req = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=300) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {exc.code} from image backend: {body[:500]}")
        except URLError as exc:
            raise RuntimeError(f"Image backend unreachable: {exc}")

    def _upscale(self, source_path: str, upscaler_name: str) -> bytes:
        source_b64 = base64.b64encode(Path(source_path).read_bytes()).decode("ascii")
        payload = {
            "resize_mode": 0,
            "gfpgan_visibility": 0,
            "codeformer_visibility": 0,
            "codeformer_weight": 0,
            "upscaling_resize": self.valves.upscale_factor,
            "upscaler_1": upscaler_name,
            "upscaler_2": "None",
            "extras_upscaler_2_visibility": 0,
            "image": source_b64,
        }
        result = self._post_json(f"{self.valves.a1111_base_url}/sdapi/v1/extra-single-image", payload)
        image_b64 = result.get("image")
        if not image_b64:
            raise RuntimeError("Image backend returned no upscaled image")
        return base64.b64decode(image_b64)

    def _save_output(self, image_bytes: bytes, user_id: str, source_filename: str, upscaler_name: str):
        file_id = str(uuid.uuid4())
        suffix = Path(source_filename).suffix or ".png"
        filename = f"{Path(source_filename).stem}-{upscaler_name.lower().replace(' ', '-').replace('+', 'plus')}{suffix}"
        output_path = Path(self.valves.output_dir) / f"{file_id}_{filename}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)
        meta = {
            "name": filename,
            "content_type": "image/png",
            "size": len(image_bytes),
            "data": {
                "source_filename": source_filename,
                "upscaler": upscaler_name,
                "kind": "upscaled_image",
            },
        }
        now = int(__import__("time").time())
        with self._db() as conn:
            conn.execute(
                """
                insert into file (id, user_id, filename, meta, created_at, hash, data, updated_at, path)
                values (?, ?, ?, ?, ?, null, ?, ?, ?)
                """,
                (file_id, user_id, filename, json.dumps(meta), now, "{}", now, str(output_path)),
            )
            conn.commit()
        return {
            "id": file_id,
            "filename": filename,
            "path": str(output_path),
            "url": f"/api/v1/files/{file_id}/content",
            "size": len(image_bytes),
        }

    async def action(self, body: dict, __user__=None, __event_emitter__=None, __id__=None):
        user_id = (__user__ or {}).get("id")
        if not user_id:
            return {"content": "Kein Benutzerkontext verfuegbar."}

        upscaler_name = "DAT x4" if __id__ != "fast" else "R-ESRGAN 4x+"
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Suche Bild und skaliere mit {upscaler_name} hoch ...",
                        "done": False,
                    },
                }
            )

        source = self._resolve_source_file(body, user_id)
        if not source:
            return {"content": "Kein Bild in dieser Nachricht gefunden und kein letzter Bildlauf verfuegbar."}

        image_bytes = self._upscale(source["path"], upscaler_name)
        saved = self._save_output(image_bytes, user_id, source.get("filename", "generated-image.png"), upscaler_name)

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Upscale mit {upscaler_name} abgeschlossen.",
                        "done": True,
                    },
                }
            )

        return {
            "content": f"Upscale mit {upscaler_name} abgeschlossen.",
            "files": [
                {
                    "type": "image",
                    "url": saved["url"],
                    "name": saved["filename"],
                }
            ],
        }
'''


def upsert_action() -> str:
    form = FunctionForm(
        id=ACTION_ID,
        name="Image Post Actions",
        content=CONTENT,
        meta=FunctionMeta(
            description="Buttons fuer Upscale direkt an Bildnachrichten in Open WebUI.",
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
    print(json.dumps({"image_post_actions": upsert_action()}, ensure_ascii=False))
