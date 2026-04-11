import sqlite3
import subprocess
import sys
import time
import os
import json
from pathlib import Path


DB_PATH = Path("/app/backend/data/webui.db")
MODEL_SCRIPT = Path("/opt/paperless-open-webui/install_model_profiles.py")
TOOL_SCRIPT = Path("/opt/paperless-open-webui/install_workspace_agent_tools.py")
ACTION_SCRIPT = Path("/opt/paperless-open-webui/install_image_actions.py")
PROJECT_ACTION_SCRIPT = Path("/opt/paperless-open-webui/install_project_path_actions.py")


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


def normalize_runtime_config() -> None:
    ollama_url = os.getenv("OPEN_WEBUI_OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
    default_model = os.getenv("OPEN_WEBUI_DEFAULT_MODEL_ID", "local-task-router").strip()
    default_pinned = os.getenv(
        "OPEN_WEBUI_DEFAULT_PINNED_MODELS",
        ",".join(
            [
                "local-task-router",
                "local-code-fast",
                "local-code-deep",
                "local-code-review",
                "local-legal-research",
                "local-paperless-tagger",
                "local-ocr-vision",
                "local-photo-assistant",
            ]
        ),
    ).strip()
    # Open WebUI chunks are character-based, not token-based.
    # ~2k-3k tokens correspond roughly to ~8k-12k chars depending on language/text mix.
    web_chunk_size = int(os.getenv("OPEN_WEBUI_WEB_CHUNK_SIZE", "9000"))
    web_chunk_overlap = int(os.getenv("OPEN_WEBUI_WEB_CHUNK_OVERLAP", "700"))
    web_top_k = int(os.getenv("OPEN_WEBUI_WEB_TOP_K", "8"))
    web_result_count = int(os.getenv("OPEN_WEBUI_WEB_RESULT_COUNT", "8"))
    changed = False
    weather_only_domains = {
        "kachelmannwetter.com",
        "wetter.de",
        "agrartwetter.de",
    }
    weather_blocklist = {
        "!wetterprognose-wettervorhersage.de",
        "!focus.de",
        "!merkur.de",
    }

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT data FROM config WHERE id = 1").fetchone()
        if not row or not row[0]:
            return
        try:
            config = json.loads(row[0])
        except json.JSONDecodeError:
            return

        serialized = json.dumps(config, ensure_ascii=False)
        if "paperless-ollama-rocm:11434" in serialized:
            serialized = serialized.replace("http://paperless-ollama-rocm:11434", ollama_url)
            serialized = serialized.replace("paperless-ollama-rocm:11434", ollama_url.replace("http://", "").replace("https://", ""))
            config = json.loads(serialized)
            changed = True

        ollama_cfg = config.setdefault("ollama", {})
        base_urls = ollama_cfg.get("base_urls") or []
        if base_urls != [ollama_url]:
            ollama_cfg["base_urls"] = [ollama_url]
            changed = True

        rag_cfg = config.setdefault("rag", {})
        rag_ollama = rag_cfg.get("ollama_base_url")
        if rag_ollama != ollama_url:
            rag_cfg["ollama_base_url"] = ollama_url
            changed = True

        # Ensure web search loads source content and evaluates retrieved chunks
        # instead of relying only on search snippets.
        if rag_cfg.get("bypass_embedding_and_retrieval") is not False:
            rag_cfg["bypass_embedding_and_retrieval"] = False
            changed = True
        if rag_cfg.get("top_k") != web_top_k:
            rag_cfg["top_k"] = web_top_k
            changed = True
        if rag_cfg.get("chunk_size") != web_chunk_size:
            rag_cfg["chunk_size"] = web_chunk_size
            changed = True
        if rag_cfg.get("chunk_overlap") != web_chunk_overlap:
            rag_cfg["chunk_overlap"] = web_chunk_overlap
            changed = True

        # If web search was accidentally constrained to weather-only domains,
        # reset to neutral so general research profiles can return results.
        web_search_cfg = rag_cfg.setdefault("web", {}).setdefault("search", {})
        domain_cfg = web_search_cfg.setdefault("domain", {})
        domain_filter_list = domain_cfg.get("filter_list")
        if isinstance(domain_filter_list, list):
            normalized = {str(item).strip().lower() for item in domain_filter_list if str(item).strip()}
            if normalized and normalized.issubset(
                {d.lower() for d in (weather_only_domains | weather_blocklist)}
            ):
                domain_cfg["filter_list"] = []
                changed = True
        if web_search_cfg.get("bypass_embedding_and_retrieval") is not False:
            web_search_cfg["bypass_embedding_and_retrieval"] = False
            changed = True
        if web_search_cfg.get("bypass_web_loader") is not False:
            web_search_cfg["bypass_web_loader"] = False
            changed = True
        if web_search_cfg.get("result_count") != web_result_count:
            web_search_cfg["result_count"] = web_result_count
            changed = True

        ui_cfg = config.setdefault("ui", {})
        if default_model and ui_cfg.get("default_models") != default_model:
            ui_cfg["default_models"] = default_model
            changed = True
        if default_pinned and ui_cfg.get("default_pinned_models") != default_pinned:
            ui_cfg["default_pinned_models"] = default_pinned
            changed = True

        if changed:
            cur.execute("UPDATE config SET data = ? WHERE id = 1", (json.dumps(config, ensure_ascii=False),))
            conn.commit()
            print("normalized open-webui runtime config")


def main() -> None:
    wait_for_db()
    normalize_runtime_config()
    run_script(MODEL_SCRIPT)
    run_script(TOOL_SCRIPT)
    run_script(ACTION_SCRIPT)
    run_script(PROJECT_ACTION_SCRIPT)


if __name__ == "__main__":
    main()
