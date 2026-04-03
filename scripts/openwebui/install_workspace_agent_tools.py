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
import os
import shlex
import sqlite3
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen


class Tools:
    DATA_ROOT = Path("/app/backend/data").resolve()
    DB_PATH = DATA_ROOT / "webui.db"
    WORKSPACE_ROOT = Path(os.getenv("OPEN_WEBUI_WORKSPACE_ROOT", "/workspace/project")).resolve()

    def _json_get(self, url: str) -> dict:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _safe_workspace_path(self, relative_path: str) -> Path:
        target = (self.WORKSPACE_ROOT / relative_path).resolve()
        if self.WORKSPACE_ROOT not in target.parents and target != self.WORKSPACE_ROOT:
            raise ValueError("Path must stay inside the workspace root")
        return target

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

    def search_workspace_text(self, pattern: str, relative_path: str = ".", limit: int = 50) -> str:
        """Search text inside the mounted workspace.

        :param pattern: Plain text pattern to search for.
        :param relative_path: Directory below the workspace root.
        :param limit: Maximum number of matches to return.
        """
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
                        if pattern in line:
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

    def git_workspace_status(self) -> str:
        """Show git status and branch information for the mounted workspace."""
        payload = {
            "branch": json.loads(self._run_workspace(["git", "branch", "--show-current"])),
            "status": json.loads(self._run_workspace(["git", "status", "--short"])),
            "diff_stat": json.loads(self._run_workspace(["git", "diff", "--stat"])),
        }
        return json.dumps(payload, indent=2, ensure_ascii=True)

    def run_workspace_command(self, command: str) -> str:
        """Run a restricted workspace command.

        :param command: Allowed commands: git status --short, git diff --stat, git branch --show-current, git log --oneline -n N, git add <path>, ls [path], pytest -q <path>, python3 -m py_compile <path>.
        """
        argv = shlex.split(command)
        if not argv:
            raise ValueError("Command must not be empty")

        if argv[:3] == ["git", "status", "--short"] and len(argv) == 3:
            return self._run_workspace(argv)
        if argv[:3] == ["git", "diff", "--stat"] and len(argv) == 3:
            return self._run_workspace(argv)
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
