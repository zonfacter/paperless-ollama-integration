import sqlite3
import subprocess
import sys
import time
import os
from pathlib import Path


DB_PATH = Path("/app/backend/data/webui.db")
MODEL_SCRIPT = Path("/opt/paperless-open-webui/install_model_profiles.py")
TOOL_SCRIPT = Path("/opt/paperless-open-webui/install_workspace_agent_tools.py")


def wait_for_db(timeout_seconds: int = 180) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if DB_PATH.exists():
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("select 1 from sqlite_master where type='table' and name='model'")
                model_ready = cur.fetchone() is not None
                cur.execute("select 1 from sqlite_master where type='table' and name='tool'")
                tool_ready = cur.fetchone() is not None
                conn.close()
                if model_ready and tool_ready:
                    return
            except sqlite3.Error:
                pass
        time.sleep(2)
    raise TimeoutError("Open WebUI database was not ready in time")


def run_script(path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "/app/backend" + (f":{env['PYTHONPATH']}" if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, str(path)],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"{path.name} failed with exit code {result.returncode}")


def main() -> None:
    wait_for_db()
    run_script(MODEL_SCRIPT)
    run_script(TOOL_SCRIPT)


if __name__ == "__main__":
    main()
