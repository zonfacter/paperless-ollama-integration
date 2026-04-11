from open_webui.models.tools import ToolForm, ToolMeta, Tools
from open_webui.utils.plugin import load_tool_module_by_id
from open_webui.utils.tools import get_tool_specs


USER_ID = "3d67f125-03f5-4b4f-81e9-a7dfdb993890"
TOOL_ID = "workspace_agent_tools"

CONTENT = r'''"""
title: Workspace Agent Tools
author: Codex
version: 1.0
"""

import json
import mimetypes
import os
import shlex
import sqlite3
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


class Tools:
    DATA_ROOT = Path("/app/backend/data").resolve()
    DB_PATH = DATA_ROOT / "webui.db"
    WORKSPACE_ROOT = Path(os.getenv("OPEN_WEBUI_WORKSPACE_ROOT", "/workspace/project")).resolve()
    PROJECT_CONTEXT_TABLE = "workspace_project_context"

    def _db(self):
        return sqlite3.connect(self.DB_PATH)

    def _ensure_project_context_table(self) -> None:
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

    def _user_id(self, __user__=None) -> str:
        if isinstance(__user__, dict):
            uid = __user__.get("id")
            if uid:
                return str(uid)
        return "global"

    def _safe_under_base(self, base: Path, relative_path: str) -> Path:
        target = (base / (relative_path or ".")).resolve()
        if base not in target.parents and target != base:
            raise ValueError("Path must stay inside the selected project path")
        return target

    def _json_get(self, url: str) -> dict:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _safe_workspace_path(self, relative_path: str) -> Path:
        target = (self.WORKSPACE_ROOT / relative_path).resolve()
        if self.WORKSPACE_ROOT not in target.parents and target != self.WORKSPACE_ROOT:
            raise ValueError("Path must stay inside the workspace root")
        return target

    def _set_project_path_for_user(self, user_id: str, project_path: str) -> dict:
        self._ensure_project_context_table()
        requested = (project_path or ".").strip()
        target = self._safe_workspace_path(requested)
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"{requested} is not an existing directory in workspace")
        relative = "." if target == self.WORKSPACE_ROOT else str(target.relative_to(self.WORKSPACE_ROOT))
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
                (user_id, relative, now),
            )
            conn.commit()
        return {
            "user_id": user_id,
            "project_path": relative,
            "abs_path": str(target),
            "updated_at": now,
        }

    def _get_project_path_for_user(self, user_id: str) -> dict:
        self._ensure_project_context_table()
        with self._db() as conn:
            row = conn.execute(
                f"SELECT project_path, updated_at FROM {self.PROJECT_CONTEXT_TABLE} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            base = self.WORKSPACE_ROOT
            return {
                "user_id": user_id,
                "project_path": ".",
                "abs_path": str(base),
                "updated_at": None,
                "source": "default_workspace_root",
            }
        rel, updated_at = row
        base = self._safe_workspace_path(rel)
        return {
            "user_id": user_id,
            "project_path": rel,
            "abs_path": str(base),
            "updated_at": updated_at,
            "source": "saved_project_path",
        }

    def _project_base_for_user(self, __user__=None) -> Path:
        info = self._get_project_path_for_user(self._user_id(__user__))
        return self._safe_workspace_path(info["project_path"])

    def _safe_project_path(self, relative_path: str, __user__=None) -> Path:
        base = self._project_base_for_user(__user__)
        return self._safe_under_base(base, relative_path)

    def _run_workspace(self, argv: list[str]) -> str:
        result = subprocess.run(
            argv,
            cwd=str(self.WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        payload = {
            "argv": argv,
            "returncode": result.returncode,
            "stdout": result.stdout[-12000:],
            "stderr": result.stderr[-12000:],
        }
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def _ensure_parent_dir(self, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)

    def _extract_text_with_tika(self, target: Path, max_chars: int = 16000) -> dict:
        safe_limit = max(500, min(max_chars, 50000))
        suffix = (target.suffix or "").lower()
        text_suffixes = {
            ".txt",
            ".md",
            ".markdown",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".log",
            ".csv",
            ".ini",
            ".conf",
            ".py",
            ".js",
            ".ts",
            ".html",
            ".htm",
        }
        if suffix in text_suffixes:
            raw = target.read_bytes()[: safe_limit * 2]
            text = raw.decode("utf-8", errors="replace")[:safe_limit]
            return {
                "path": str(target),
                "extractor": "utf8",
                "chars": len(text),
                "truncated": len(raw.decode("utf-8", errors="replace")) > safe_limit,
                "text": text,
            }

        tika_url = os.getenv("OPEN_WEBUI_TIKA_SERVER_URL", "http://tika-ocr-proxy:9998").rstrip("/")
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        raw_bytes = target.read_bytes()
        req = Request(
            f"{tika_url}/tika",
            data=raw_bytes,
            headers={
                "Accept": "text/plain",
                "Content-Type": content_type,
            },
            method="PUT",
        )
        try:
            with urlopen(req, timeout=120) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            extractor = "tika"
            error = None
        except Exception as exc:
            text = raw_bytes.decode("utf-8", errors="replace")
            extractor = "utf8-fallback"
            error = str(exc)
        return {
            "path": str(target),
            "extractor": extractor,
            "tika_url": tika_url,
            "content_type": content_type,
            "error": error,
            "chars": min(len(text), safe_limit),
            "truncated": len(text) > safe_limit,
            "text": text[:safe_limit],
        }

    def set_project_path(self, project_path: str = ".", __user__=None) -> str:
        """Set a per-user default project path below the workspace root.

        :param project_path: Directory path inside workspace root, e.g. project/ebay.
        """
        payload = self._set_project_path_for_user(self._user_id(__user__), project_path)
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def init_project_context(self, project_path: str, limit: int = 100, __user__=None) -> str:
        """Set project path and immediately list root entries in one call.

        :param project_path: Directory path inside workspace root, e.g. project/ebay.
        :param limit: Maximum number of entries returned from project root.
        """
        info = self._set_project_path_for_user(self._user_id(__user__), project_path)
        base = self._safe_workspace_path(info["project_path"])
        items = []
        for entry in sorted(base.iterdir())[: max(1, min(limit, 200))]:
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(base)),
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return json.dumps(
            {
                "project_path": info["project_path"],
                "abs_path": info["abs_path"],
                "items": items,
            },
            indent=2,
            ensure_ascii=True,
        )

    def get_project_path(self, __user__=None) -> str:
        """Get the current per-user default project path."""
        payload = self._get_project_path_for_user(self._user_id(__user__))
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def get_system_metrics(self) -> str:
        """Read current NAS and GPU diagnostics from the Paperless AI system metrics API."""
        data = self._json_get("http://paperless-ai-web:3000/api/system/metrics")
        return json.dumps(data, indent=2, ensure_ascii=True)

    def get_ollama_status(self) -> str:
        """Read installed and active Ollama models."""
        tags = self._json_get("http://ollama:11434/api/tags")
        try:
            ps = self._json_get("http://ollama:11434/api/ps")
        except Exception:
            ps = {"models": []}
        data = {"installed": tags.get("models", []), "active": ps.get("models", [])}
        return json.dumps(data, indent=2, ensure_ascii=True)

    def list_webui_profiles(self, tag: str = "") -> str:
        """List available Open WebUI custom model profiles.

        :param tag: Optional tag filter like LOCAL, CLOUD, CODING or UNCENSORED.
        """
        conn = sqlite3.connect(self.DB_PATH)
        cur = conn.cursor()
        rows = cur.execute("select id,name,base_model_id,meta from model order by name").fetchall()
        profiles = []
        wanted = tag.strip().upper()
        for mid, name, base, meta_raw in rows:
            meta = json.loads(meta_raw) if meta_raw else {}
            tags = [t.get("name", "") for t in meta.get("tags", []) if isinstance(t, dict)]
            if wanted and wanted not in [t.upper() for t in tags]:
                continue
            profiles.append(
                {
                    "id": mid,
                    "name": name,
                    "base_model_id": base,
                    "tags": tags,
                    "description": meta.get("description"),
                }
            )
        defaults = json.loads(cur.execute("select data from config where id=1").fetchone()[0]).get("ui", {})
        conn.close()
        return json.dumps({"profiles": profiles, "ui_defaults": defaults}, indent=2, ensure_ascii=True)

    def list_workspace_files(self, relative_path: str = ".", limit: int = 100) -> str:
        """List files inside the mounted workspace.

        :param relative_path: Folder below the mounted workspace root.
        :param limit: Maximum number of entries to return.
        """
        base = self._safe_workspace_path(relative_path)
        if not base.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not base.is_dir():
            raise NotADirectoryError(f"{relative_path} is not a directory")
        items = []
        for entry in sorted(base.iterdir())[: max(1, min(limit, 200))]:
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(self.WORKSPACE_ROOT)),
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return json.dumps(items, indent=2, ensure_ascii=True)

    def list_project_files(self, relative_path: str = ".", limit: int = 100, __user__=None) -> str:
        """List files inside the currently selected project path.

        :param relative_path: Folder below the selected project path.
        :param limit: Maximum number of entries to return.
        """
        base = self._safe_project_path(relative_path, __user__)
        project_base = self._project_base_for_user(__user__)
        if not base.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not base.is_dir():
            raise NotADirectoryError(f"{relative_path} is not a directory")
        items = []
        for entry in sorted(base.iterdir())[: max(1, min(limit, 200))]:
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(project_base)),
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                }
            )
        return json.dumps(items, indent=2, ensure_ascii=True)

    def read_workspace_file(self, relative_path: str, max_bytes: int = 4000) -> str:
        """Read a small UTF-8 text file from the mounted workspace.

        :param relative_path: File path below the workspace root.
        :param max_bytes: Maximum bytes to read, capped to 20000.
        """
        target = self._safe_workspace_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        safe_limit = max(1, min(max_bytes, 20000))
        raw = target.read_bytes()[:safe_limit]
        return raw.decode("utf-8", errors="replace")

    def read_project_file(self, relative_path: str, max_bytes: int = 4000, __user__=None) -> str:
        """Read a small UTF-8 text file from the selected project path.

        :param relative_path: File path below the selected project path.
        :param max_bytes: Maximum bytes to read, capped to 20000.
        """
        target = self._safe_project_path(relative_path, __user__)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        safe_limit = max(1, min(max_bytes, 20000))
        raw = target.read_bytes()[:safe_limit]
        return raw.decode("utf-8", errors="replace")

    def extract_workspace_document(self, relative_path: str, max_chars: int = 16000) -> str:
        """Extract text from a workspace document (txt/md/pdf/doc/docx/ppt/pptx/etc.).

        :param relative_path: File path below the workspace root.
        :param max_chars: Maximum extracted characters, capped to 50000.
        """
        target = self._safe_workspace_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        payload = self._extract_text_with_tika(target, max_chars=max_chars)
        payload["path"] = str(target.relative_to(self.WORKSPACE_ROOT))
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def extract_project_document(self, relative_path: str, max_chars: int = 16000, __user__=None) -> str:
        """Extract text from a document below the selected project path.

        :param relative_path: File path below the selected project path.
        :param max_chars: Maximum extracted characters, capped to 50000.
        """
        target = self._safe_project_path(relative_path, __user__)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        payload = self._extract_text_with_tika(target, max_chars=max_chars)
        payload["path"] = str(target.relative_to(self._project_base_for_user(__user__)))
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def write_workspace_file(self, relative_path: str, content: str, append: bool = False) -> str:
        """Write a UTF-8 text file inside the mounted workspace.

        :param relative_path: File path below the workspace root.
        :param content: New file content. Limited to 200000 chars.
        :param append: When true, append instead of overwrite.
        """
        if len(content or "") > 200000:
            raise ValueError("Content too large")
        target = self._safe_workspace_path(relative_path)
        self._ensure_parent_dir(target)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return json.dumps(
            {
                "path": str(target.relative_to(self.WORKSPACE_ROOT)),
                "bytes": target.stat().st_size,
                "append": append,
            },
            indent=2,
            ensure_ascii=True,
        )

    def write_project_file(self, relative_path: str, content: str, append: bool = False, __user__=None) -> str:
        """Write a UTF-8 text file inside the selected project path.

        :param relative_path: File path below the selected project path.
        :param content: New file content. Limited to 200000 chars.
        :param append: When true, append instead of overwrite.
        """
        if len(content or "") > 200000:
            raise ValueError("Content too large")
        target = self._safe_project_path(relative_path, __user__)
        self._ensure_parent_dir(target)
        mode = "a" if append else "w"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return json.dumps(
            {
                "path": str(target.relative_to(self._project_base_for_user(__user__))),
                "bytes": target.stat().st_size,
                "append": append,
            },
            indent=2,
            ensure_ascii=True,
        )

    def replace_workspace_text(self, relative_path: str, old_text: str, new_text: str, count: int = 1) -> str:
        """Replace text in a workspace file.

        :param relative_path: File path below the workspace root.
        :param old_text: Existing text to replace.
        :param new_text: Replacement text.
        :param count: Maximum replacements, capped to 50. Use 0 for replace all.
        """
        target = self._safe_workspace_path(relative_path)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        raw = target.read_text(encoding="utf-8", errors="replace")
        if old_text not in raw:
            raise ValueError("old_text not found in file")
        safe_count = min(max(int(count), 0), 50)
        updated = raw.replace(old_text, new_text, safe_count or -1)
        target.write_text(updated, encoding="utf-8")
        replacements = raw.count(old_text) if safe_count == 0 else min(raw.count(old_text), safe_count)
        return json.dumps(
            {
                "path": str(target.relative_to(self.WORKSPACE_ROOT)),
                "replacements": replacements,
                "bytes": target.stat().st_size,
            },
            indent=2,
            ensure_ascii=True,
        )

    def replace_project_text(self, relative_path: str, old_text: str, new_text: str, count: int = 1, __user__=None) -> str:
        """Replace text in a file below the selected project path.

        :param relative_path: File path below the selected project path.
        :param old_text: Existing text to replace.
        :param new_text: Replacement text.
        :param count: Maximum replacements, capped to 50. Use 0 for replace all.
        """
        target = self._safe_project_path(relative_path, __user__)
        if not target.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        if not target.is_file():
            raise IsADirectoryError(f"{relative_path} is not a file")
        raw = target.read_text(encoding="utf-8", errors="replace")
        if old_text not in raw:
            raise ValueError("old_text not found in file")
        safe_count = min(max(int(count), 0), 50)
        updated = raw.replace(old_text, new_text, safe_count or -1)
        target.write_text(updated, encoding="utf-8")
        replacements = raw.count(old_text) if safe_count == 0 else min(raw.count(old_text), safe_count)
        return json.dumps(
            {
                "path": str(target.relative_to(self._project_base_for_user(__user__))),
                "replacements": replacements,
                "bytes": target.stat().st_size,
            },
            indent=2,
            ensure_ascii=True,
        )

    def search_workspace_text(self, pattern: str = "", query: str = "", relative_path: str = ".", limit: int = 50) -> str:
        """Search text inside the mounted workspace.

        :param pattern: Plain text pattern to search for.
        :param query: Alias for pattern used by some models.
        :param relative_path: Directory below the workspace root.
        :param limit: Maximum number of matches to return.
        """
        needle = (pattern or query or "").strip()
        if not needle:
            raise ValueError("pattern or query is required")
        base = self._safe_workspace_path(relative_path)
        if not base.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        matches = []
        safe_limit = max(1, min(limit, 200))
        for path in sorted(base.rglob("*")):
            if len(matches) >= safe_limit:
                break
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for lineno, line in enumerate(handle, start=1):
                        if needle in line:
                            matches.append(
                                {
                                    "path": str(path.relative_to(self.WORKSPACE_ROOT)),
                                    "line": lineno,
                                    "text": line.rstrip(),
                                }
                            )
                            if len(matches) >= safe_limit:
                                break
            except Exception:
                continue
        return json.dumps(matches, indent=2, ensure_ascii=True)

    def search_project_text(self, pattern: str = "", query: str = "", relative_path: str = ".", limit: int = 50, __user__=None) -> str:
        """Search text inside the selected project path.

        :param pattern: Plain text pattern to search for.
        :param query: Alias for pattern used by some models.
        :param relative_path: Directory below the selected project path.
        :param limit: Maximum number of matches to return.
        """
        needle = (pattern or query or "").strip()
        if not needle:
            raise ValueError("pattern or query is required")
        base = self._safe_project_path(relative_path, __user__)
        project_base = self._project_base_for_user(__user__)
        if not base.exists():
            raise FileNotFoundError(f"{relative_path} does not exist")
        matches = []
        safe_limit = max(1, min(limit, 200))
        for path in sorted(base.rglob("*")):
            if len(matches) >= safe_limit:
                break
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for lineno, line in enumerate(handle, start=1):
                        if needle in line:
                            matches.append(
                                {
                                    "path": str(path.relative_to(project_base)),
                                    "line": lineno,
                                    "text": line.rstrip(),
                                }
                            )
                            if len(matches) >= safe_limit:
                                break
            except Exception:
                continue
        return json.dumps(matches, indent=2, ensure_ascii=True)

    def analyze_project_logs(self, pattern: str = "", query: str = "", log_dir: str = "logs", limit: int = 100, __user__=None) -> str:
        """Search common error patterns in project logs, optionally with a custom pattern.

        :param pattern: Optional custom pattern.
        :param query: Alias for pattern.
        :param log_dir: Log directory relative to selected project path.
        :param limit: Max matches per pattern.
        """
        custom = (pattern or query or "").strip()
        patterns = [custom] if custom else [
            "ERROR",
            "Exception",
            "Traceback",
            "Invalid request",
            "eBay-Fehler",
            "Could not serialize field",
        ]
        result = {"log_dir": log_dir, "patterns": {}}
        for p in patterns:
            raw = self.search_project_text(pattern=p, relative_path=log_dir, limit=limit, __user__=__user__)
            try:
                result["patterns"][p] = json.loads(raw)
            except Exception:
                result["patterns"][p] = {"raw": raw}
        return json.dumps(result, indent=2, ensure_ascii=True)

    def git_workspace_status(self) -> str:
        """Show git status and branch information for the mounted workspace."""
        payload = {
            "branch": json.loads(self._run_workspace(["git", "branch", "--show-current"])),
            "status": json.loads(self._run_workspace(["git", "status", "--short"])),
            "diff_stat": json.loads(self._run_workspace(["git", "diff", "--stat"])),
        }
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def read_workspace_diff(self, relative_path: str = "") -> str:
        """Read git diff for the workspace or a single file.

        :param relative_path: Optional file path below the workspace root.
        """
        argv = ["git", "diff", "--"]
        if relative_path.strip():
            target = self._safe_workspace_path(relative_path)
            argv.append(str(target.relative_to(self.WORKSPACE_ROOT)))
        return self._run_workspace(argv)

    def apply_workspace_patch(self, patch_text: str) -> str:
        """Apply a unified diff patch inside the mounted workspace.

        :param patch_text: Unified diff text with paths relative to the workspace root.
        """
        if len(patch_text or "") > 250000:
            raise ValueError("Patch too large")
        if not patch_text.strip():
            raise ValueError("Patch must not be empty")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".patch") as handle:
            handle.write(patch_text)
            patch_path = handle.name
        try:
            check = subprocess.run(
                ["git", "apply", "--check", "--whitespace=nowarn", patch_path],
                cwd=str(self.WORKSPACE_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if check.returncode != 0:
                return json.dumps(
                    {
                        "applied": False,
                        "returncode": check.returncode,
                        "stdout": check.stdout[-12000:],
                        "stderr": check.stderr[-12000:],
                    },
                    indent=2,
                    ensure_ascii=True,
                )
            result = subprocess.run(
                ["git", "apply", "--whitespace=nowarn", patch_path],
                cwd=str(self.WORKSPACE_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return json.dumps(
                {
                    "applied": result.returncode == 0,
                    "returncode": result.returncode,
                    "stdout": result.stdout[-12000:],
                    "stderr": result.stderr[-12000:],
                },
                indent=2,
                ensure_ascii=True,
            )
        finally:
            try:
                os.unlink(patch_path)
            except FileNotFoundError:
                pass

    def run_workspace_command(self, command: str) -> str:
        """Run a restricted workspace command.

        :param command: Allowed commands: git status --short, git diff --stat, git diff -- <path>, git branch --show-current, git log --oneline -n N, git add <path>, ls [path], pytest -q <path>, python3 -m py_compile <path>.
        """
        argv = shlex.split(command)
        if not argv:
            raise ValueError("Command must not be empty")

        if argv[:3] == ["git", "status", "--short"] and len(argv) == 3:
            return self._run_workspace(argv)
        if argv[:3] == ["git", "diff", "--stat"] and len(argv) == 3:
            return self._run_workspace(argv)
        if len(argv) == 4 and argv[:3] == ["git", "diff", "--"]:
            target = self._safe_workspace_path(argv[3])
            return self._run_workspace(["git", "diff", "--", str(target.relative_to(self.WORKSPACE_ROOT))])
        if argv[:3] == ["git", "branch", "--show-current"] and len(argv) == 3:
            return self._run_workspace(argv)
        if len(argv) == 5 and argv[:3] == ["git", "log", "--oneline"] and argv[3] == "-n" and argv[4].isdigit():
            return self._run_workspace(argv)
        if argv[:2] == ["git", "add"] and len(argv) == 3:
            target = self._safe_workspace_path(argv[2])
            return self._run_workspace(["git", "add", str(target.relative_to(self.WORKSPACE_ROOT))])
        if argv[0] == "ls" and len(argv) <= 2:
            if len(argv) == 2:
                target = self._safe_workspace_path(argv[1])
                return self._run_workspace(["ls", str(target)])
            return self._run_workspace(["ls", str(self.WORKSPACE_ROOT)])
        if argv[:2] == ["pytest", "-q"] and len(argv) == 3:
            target = self._safe_workspace_path(argv[2])
            return self._run_workspace(["pytest", "-q", str(target.relative_to(self.WORKSPACE_ROOT))])
        if argv[:3] == ["python3", "-m", "py_compile"] and len(argv) == 4:
            target = self._safe_workspace_path(argv[3])
            return self._run_workspace(["python3", "-m", "py_compile", str(target.relative_to(self.WORKSPACE_ROOT))])

        raise ValueError("Command is not in the allowed command set")
'''

tool_module, frontmatter = load_tool_module_by_id(TOOL_ID, content=CONTENT)
specs = get_tool_specs(tool_module)
form = ToolForm(
    id=TOOL_ID,
    name="Workspace Agent Tools",
    content=CONTENT,
    meta=ToolMeta(
        description="Safe workspace-aware tools for NAS diagnostics, Open WebUI profile inspection and bounded repository access including write operations.",
        manifest=frontmatter,
    ),
    access_grants=[],
)

existing = Tools.get_tool_by_id(TOOL_ID)
payload = {
    "name": form.name,
    "content": form.content,
    "meta": form.meta.model_dump(),
    "specs": specs,
    "user_id": USER_ID,
    "valves": {},
}
if existing:
    Tools.update_tool_by_id(TOOL_ID, payload)
    print("updated", TOOL_ID)
else:
    Tools.insert_new_tool(USER_ID, form, specs)
    print("created", TOOL_ID)
print("specs", [spec["name"] for spec in specs])
