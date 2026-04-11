#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_HOOK = "/opt/paperless/ai_enrich.py"


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


def log(message: str) -> None:
    print(f"[paperless-ai-backfill] {message}", flush=True)


def fetch_json(url: str, token: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Token {token}",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def iter_documents(api_url: str, token: str, query: str | None) -> list[dict]:
    docs: list[dict] = []
    params = {"page_size": 100, "ordering": "id"}
    if query:
        params["query"] = query
    next_url = f"{api_url.rstrip('/')}/api/documents/?{urllib.parse.urlencode(params)}"
    while next_url:
        payload = fetch_json(next_url, token)
        if isinstance(payload, dict) and "results" in payload:
            docs.extend(payload["results"])
            next_url = payload.get("next")
        else:
            raise RuntimeError(f"Unexpected documents response: {payload}")
    return docs


def find_tag_id_by_name(api_url: str, token: str, tag_name: str) -> int | None:
    params = {"page_size": 100, "ordering": "id"}
    next_url = f"{api_url.rstrip('/')}/api/tags/?{urllib.parse.urlencode(params)}"
    wanted = tag_name.strip().lower()
    while next_url:
        payload = fetch_json(next_url, token)
        if not isinstance(payload, dict) or "results" not in payload:
            raise RuntimeError(f"Unexpected tags response: {payload}")
        for tag in payload["results"]:
            if str(tag.get("name", "")).strip().lower() == wanted:
                try:
                    return int(tag["id"])
                except Exception:
                    continue
        next_url = payload.get("next")
    return None


def should_include(
    doc: dict,
    args: argparse.Namespace,
    *,
    review_tag_id: int | None = None,
    skip_reviewed: bool = False,
) -> bool:
    doc_id = int(doc["id"])
    if args.document_id and doc_id not in args.document_id:
        return False
    if args.from_id is not None and doc_id < args.from_id:
        return False
    if args.to_id is not None and doc_id > args.to_id:
        return False
    if args.only_missing_metadata:
        if skip_reviewed and review_tag_id is not None:
            tag_ids = doc.get("tags") or []
            if isinstance(tag_ids, list) and review_tag_id in tag_ids:
                return False
        if doc.get("correspondent") and doc.get("document_type") and doc.get("tags"):
            return False
    return True


def run_hook(doc_id: int, hook_path: str, base_env: dict[str, str]) -> int:
    child_env = os.environ.copy()
    child_env.update(base_env)
    child_env["DOCUMENT_ID"] = str(doc_id)
    result = subprocess.run([hook_path], env=child_env, check=False)
    return result.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Paperless AI hook over existing documents.",
    )
    parser.add_argument("--document-id", type=int, action="append", default=[], help="Specific document ID to process. Can be repeated.")
    parser.add_argument("--from-id", type=int, help="Lower document ID bound.")
    parser.add_argument("--to-id", type=int, help="Upper document ID bound.")
    parser.add_argument("--query", help="Paperless search query.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of documents to process.")
    parser.add_argument("--only-missing-metadata", action="store_true", help="Only process documents without correspondent, document type or tags.")
    parser.add_argument("--dry-run", action="store_true", help="Only list matching documents.")
    parser.add_argument("--hook", default=DEFAULT_HOOK, help="Path to the Paperless AI hook.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_url = env("PAPERLESS_API_URL")
    token = env("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        print("PAPERLESS_API_URL and PAPERLESS_API_TOKEN are required.", file=sys.stderr)
        return 2

    hook_path = Path(args.hook)
    if not hook_path.is_file():
        print(f"Hook not found: {hook_path}", file=sys.stderr)
        return 2

    skip_reviewed_raw = env("PAPERLESS_AI_BACKFILL_SKIP_REVIEWED", "1") or "1"
    skip_reviewed = skip_reviewed_raw.strip().lower() not in {"0", "false", "no", "off"}
    review_tag_name = env("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen")
    review_tag_id: int | None = None
    if args.only_missing_metadata and skip_reviewed and review_tag_name:
        try:
            review_tag_id = find_tag_id_by_name(api_url, token, review_tag_name)
            if review_tag_id is None:
                log(f"Review tag '{review_tag_name}' not found; skip-reviewed guard disabled.")
            else:
                log(f"Skip-reviewed guard active for tag '{review_tag_name}' (id={review_tag_id}).")
        except Exception as exc:
            log(f"Could not resolve review tag '{review_tag_name}': {exc}")

    documents = iter_documents(api_url, token, args.query)
    selected = [
        doc
        for doc in documents
        if should_include(
            doc,
            args,
            review_tag_id=review_tag_id,
            skip_reviewed=skip_reviewed,
        )
    ]
    if args.limit and args.limit > 0:
        selected = selected[: args.limit]

    log(f"Selected {len(selected)} document(s)")
    for doc in selected:
        log(f"#{doc['id']} {doc.get('title', '')}")

    if args.dry_run or not selected:
        return 0

    base_env = {
        "PAPERLESS_API_URL": api_url,
        "PAPERLESS_API_TOKEN": token,
    }

    for key in (
        "PAPERLESS_AI_PROVIDER",
        "PAPERLESS_AI_OLLAMA_URL",
        "PAPERLESS_AI_OLLAMA_MODEL",
        "PAPERLESS_AI_PROMPT_FILE",
        "PAPERLESS_AI_CONTENT_CHARS",
        "PAPERLESS_AI_MIN_CONFIDENCE",
        "PAPERLESS_AI_DEFAULT_TAG_COLOR",
        "OPENAI_API_KEY",
        "PAPERLESS_AI_OPENAI_MODEL",
    ):
        value = env(key)
        if value:
            base_env[key] = value

    success = 0
    failed = 0
    for doc in selected:
        doc_id = int(doc["id"])
        log(f"Processing document {doc_id}")
        rc = run_hook(doc_id, str(hook_path), base_env)
        if rc == 0:
            success += 1
        else:
            failed += 1
            log(f"Document {doc_id} failed with exit code {rc}")

    log(f"Finished: success={success}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
