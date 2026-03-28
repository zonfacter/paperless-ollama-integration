#!/usr/bin/env python3
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_PROMPT_PATH = "/opt/paperless/ai_enrich_prompt.txt"
DEFAULT_PROMPT_TEMPLATE = """Du bist ein Assistent fuer die saubere Ablage in paperless-ngx.
Antworte nur als JSON-Objekt ohne Markdown.

Ziele:
- Erzeuge einen kurzen, klaren deutschen Titel.
- Erkenne die Korrespondenz bzw. den Absender/Empfaenger als `correspondent`.
- Waehle einen sinnvollen Dokumenttyp als `document_type`.
- Vergib wenige, gute Tags.

Regeln:
- Keine Halluzinationen. Wenn unklar, lieber leer lassen.
- Titel maximal 120 Zeichen, sachlich, ohne Dateiendung.
- Tags nur 1 bis 6 Stueck, kurz und wiederverwendbar.
- Nutze fuer Personen/Institutionen normale Namen, keine Aktenzeichen als Korrespondenz.
- Nutze keine reinen Empfaengernamen oder Privatpersonen als Tags, wenn sie nur im Briefkopf vorkommen.
- Bevorzuge thematische Tags statt Personennamen.
- Personennamen duerfen nur dann als Tag vorgeschlagen werden, wenn der Name exakt in der Liste `Vorhandene Personentags` steht und exakt so im OCR-Inhalt vorkommt.
- Erfinde niemals neue Personennamen als Tags und aendere existierende Namen nicht.
- Wenn das Dokument klar juristisch oder behoerdlich ist, nutze passende Begriffe wie Beschluss, Schreiben, Bescheid, Rechnung, Vertrag, Mahnung.

Rueckgabeformat:
{{
  "title": "string",
  "correspondent": "string oder leer",
  "document_type": "string oder leer",
  "tags": ["string"],
  "confidence": 0.0,
  "reason": "kurz"
}}

Vorhandene Metadaten:
- Aktueller Titel: {title}
- Originaldatei: {original}
- Korrespondenz: {correspondent}
- Dokumenttyp: {doc_type}
- Tags: {tags}
- Vorhandene Personentags: {existing_person_tags}

OCR-Inhalt:
{content}
"""


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


def log(message: str) -> None:
    print(f"[paperless-ai] {message}", flush=True)


def warn(message: str) -> None:
    print(f"[paperless-ai] WARN: {message}", file=sys.stderr, flush=True)


def positive_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class HttpClient:
    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, payload: dict | None = None, timeout: float | None = None) -> dict | list | str | None:
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{self.base_url}{path}"
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        request_timeout = timeout if timeout is not None else float(env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "300"))
        try:
            with urllib.request.urlopen(req, timeout=request_timeout) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
                if not raw:
                    return None
                text = raw.decode("utf-8")
                if "application/json" in content_type or text[:1] in ("{", "["):
                    return json.loads(text)
                return text
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed with {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"{method} {url} failed: {exc}") from exc

    def get(self, path: str, timeout: float | None = None) -> dict | list | str | None:
        return self._request("GET", path, timeout=timeout)

    def post(self, path: str, payload: dict, timeout: float | None = None) -> dict | list | str | None:
        return self._request("POST", path, payload, timeout=timeout)

    def patch(self, path: str, payload: dict, timeout: float | None = None) -> dict | list | str | None:
        return self._request("PATCH", path, payload, timeout=timeout)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def truncate_text(value: str, max_chars: int) -> str:
    value = normalize_whitespace(value)
    return value[:max_chars]


def clean_name(value: str) -> str:
    value = normalize_whitespace(value)
    value = re.sub(r"[\"'`]+", "", value)
    return value.strip(" ,;:-")


def parse_json_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z0-9_-]*\n", "", raw)
        raw = re.sub(r"\n```$", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def load_prompt_template() -> str:
    prompt_path = Path(env("PAPERLESS_AI_PROMPT_FILE", DEFAULT_PROMPT_PATH))
    if prompt_path.is_file():
        return prompt_path.read_text(encoding="utf-8")
    return DEFAULT_PROMPT_TEMPLATE


def looks_like_person_tag(value: str) -> bool:
    tokens = [token for token in re.split(r"\s+", normalize_whitespace(value)) if token]
    if len(tokens) < 2 or len(tokens) > 3:
        return False
    for token in tokens:
        if any(char.isdigit() for char in token):
            return False
        parts = [part for part in token.split("-") if part]
        if not parts:
            return False
        for part in parts:
            if len(part) < 2:
                return False
            if not part[0].isupper():
                return False
            if not part[1:].islower():
                return False
            if not part.replace("'", "").isalpha():
                return False
    return True


def prompt_for_document(document: dict, existing_person_tags: list[str]) -> str:
    title = document.get("title") or ""
    original = document.get("original_file_name") or ""
    correspondent = (document.get("correspondent") or {}).get("name", "") if isinstance(document.get("correspondent"), dict) else ""
    doc_type = (document.get("document_type") or {}).get("name", "") if isinstance(document.get("document_type"), dict) else ""
    tags = [tag.get("name", "") for tag in document.get("tags", []) if isinstance(tag, dict)]
    content = document.get("content") or ""
    content = truncate_text(content, int(env("PAPERLESS_AI_CONTENT_CHARS", "12000")))
    template = load_prompt_template()
    return template.format(
        title=title,
        original=original,
        correspondent=correspondent,
        doc_type=doc_type,
        tags=", ".join(tags),
        existing_person_tags=", ".join(existing_person_tags) or "-",
        content=content,
    )


def call_openai(prompt: str) -> dict:
    api_key = env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = env("PAPERLESS_AI_OPENAI_MODEL", "gpt-5.4-mini")
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Gib ausschliesslich valides JSON zurueck.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            },
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI request failed with {exc.code}: {body}") from exc
    output = []
    for item in raw.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                output.append(text)
    if not output:
        raise RuntimeError("OpenAI response did not contain text output")
    return parse_json_object("\n".join(output))


def call_ollama(prompt: str, model: str | None = None, timeout: float | None = None) -> dict:
    model = model or env("PAPERLESS_AI_OLLAMA_MODEL", "qwen2.5:7b-instruct")
    host = env("PAPERLESS_AI_OLLAMA_URL", "http://127.0.0.1:11434")
    client = HttpClient(host)
    num_thread = positive_int(env("PAPERLESS_AI_OLLAMA_NUM_THREAD", "4"), 4)
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"num_thread": num_thread},
        "messages": [
            {"role": "system", "content": "Du gibst ausschliesslich valides JSON aus."},
            {"role": "user", "content": prompt},
        ],
    }
    # Qwen 3.5 defaults to visible/internal thinking, which slows down
    # Paperless JSON extraction heavily. Disable it unless explicitly enabled.
    if model.startswith("qwen3.5:"):
        think_enabled = env("PAPERLESS_AI_QWEN35_THINK", "false").lower() in ("1", "true", "yes", "on")
        payload["think"] = think_enabled
    response = client.post("/api/chat", payload, timeout=timeout)
    if not isinstance(response, dict):
        raise RuntimeError("Unexpected Ollama response")
    message = response.get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError("Ollama response did not contain message.content")
    return parse_json_object(content)


def is_timeout_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return isinstance(exc, TimeoutError) or "timed out" in message or "timeout" in message


def get_provider_response_details(prompt: str) -> tuple[dict, dict]:
    provider = env("PAPERLESS_AI_PROVIDER", "ollama").lower()
    if provider == "openai":
        return call_openai(prompt), {
            "provider": "openai",
            "model": env("PAPERLESS_AI_OPENAI_MODEL", "gpt-5.4-mini"),
            "fallback_used": False,
        }
    if provider == "ollama":
        primary_model = env("PAPERLESS_AI_OLLAMA_MODEL", "qwen2.5:7b-instruct")
        primary_timeout = float(env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "300"))
        fallback_enabled = env("PAPERLESS_AI_FALLBACK_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        fallback_model = env("PAPERLESS_AI_FALLBACK_MODEL", "qwen2.5:3b-instruct")
        fallback_timeout = float(env("PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS", str(primary_timeout)))
        fallback_timeout_only = env("PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY", "true").lower() in ("1", "true", "yes", "on")
        try:
            return call_ollama(prompt, model=primary_model, timeout=primary_timeout), {
                "provider": "ollama",
                "model": primary_model,
                "fallback_used": False,
                "timeout_seconds": primary_timeout,
            }
        except Exception as exc:
            if not fallback_enabled:
                raise
            if fallback_timeout_only and not is_timeout_error(exc):
                raise
            warn(f"Primary model '{primary_model}' failed, using fallback '{fallback_model}': {exc}")
            return call_ollama(prompt, model=fallback_model, timeout=fallback_timeout), {
                "provider": "ollama",
                "model": fallback_model,
                "fallback_used": True,
                "fallback_from": primary_model,
                "timeout_seconds": fallback_timeout,
            }
    raise RuntimeError(f"Unsupported PAPERLESS_AI_PROVIDER: {provider}")


def get_provider_response(prompt: str) -> dict:
    return get_provider_response_details(prompt)[0]


def list_all(client: HttpClient, path: str) -> list[dict]:
    items: list[dict] = []
    next_url = f"{path}?page_size=1000"
    while next_url:
        response = client.get(next_url)
        if isinstance(response, dict) and "results" in response:
            items.extend(response["results"])
            next_url = response.get("next")
        elif isinstance(response, list):
            items.extend(response)
            next_url = None
        else:
            raise RuntimeError(f"Unexpected list response for {path}: {response}")
    return items


def find_by_name(items: list[dict], name: str) -> dict | None:
    name_cf = name.casefold()
    for item in items:
        if str(item.get("name", "")).casefold() == name_cf:
            return item
    return None


def ensure_named_object(client: HttpClient, endpoint: str, name: str, extra: dict | None = None) -> int | None:
    name = clean_name(name)
    if not name:
        return None
    items = list_all(client, endpoint)
    existing = find_by_name(items, name)
    if existing:
        return int(existing["id"])
    payload = {"name": name}
    if extra:
        payload.update(extra)
    created = client.post(f"{endpoint}", payload)
    if not isinstance(created, dict) or "id" not in created:
        raise RuntimeError(f"Could not create {endpoint} item {name}: {created}")
    log(f"Created {endpoint.strip('/')} '{name}'")
    return int(created["id"])


def resolve_tag_ids(client: HttpClient, tag_names: list[str], document_content: str) -> list[int]:
    existing_tags = list_all(client, "/api/tags/")
    existing_by_name = {
        str(tag.get("name", "")).casefold(): tag
        for tag in existing_tags
        if isinstance(tag, dict) and tag.get("name")
    }
    normalized_content = f" {normalize_whitespace(document_content).casefold()} "
    resolved_ids: list[int] = []
    for tag_name in tag_names:
        normalized = clean_name(tag_name)
        if not normalized:
            continue
        existing = existing_by_name.get(normalized.casefold())
        if looks_like_person_tag(normalized):
            if existing is None:
                log(f"Skipped new person tag '{normalized}': only existing person tags may be reused")
                continue
            exact_name = f" {normalized.casefold()} "
            if exact_name not in normalized_content:
                log(f"Skipped person tag '{normalized}': name not found exactly in document text")
                continue
            resolved_ids.append(int(existing["id"]))
            continue
        if existing is not None:
            resolved_ids.append(int(existing["id"]))
            continue
        created_id = ensure_named_object(
            client,
            "/api/tags/",
            normalized,
            {"color": env("PAPERLESS_AI_DEFAULT_TAG_COLOR", "#4f6bed")},
        )
        if created_id is not None:
            resolved_ids.append(created_id)
            existing_by_name[normalized.casefold()] = {"id": created_id, "name": normalized}
    return resolved_ids


def sanitize_result(result: dict) -> dict:
    title = clean_name(str(result.get("title", "")))
    correspondent = clean_name(str(result.get("correspondent", "")))
    document_type = clean_name(str(result.get("document_type", "")))
    tags = result.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    clean_tags = []
    seen = set()
    for tag in tags:
        tag_name = clean_name(str(tag))
        if not tag_name:
            continue
        key = tag_name.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean_tags.append(tag_name[:50])
    return {
        "title": title[:120],
        "correspondent": correspondent[:120],
        "document_type": document_type[:120],
        "tags": clean_tags[:6],
        "confidence": result.get("confidence"),
        "reason": truncate_text(str(result.get("reason", "")), 200),
    }


def detect_document_family(document: dict, result: dict) -> str:
    haystack = " ".join(
        str(value or "")
        for value in (
            document.get("content", ""),
            document.get("title", ""),
            document.get("original_file_name", ""),
            result.get("title", ""),
            result.get("document_type", ""),
            result.get("correspondent", ""),
            result.get("reason", ""),
        )
    ).casefold()
    if any(token in haystack for token in ("amtsgericht", "landgericht", "oberlandesgericht", "familiengericht", "beschluss", "pflegschaft", "sofortige beschwerde")):
        return "court"
    if any(token in haystack for token in ("schule", "realschule", "gymnasium", "schulleiter", "fehltag", "schulpflicht", "attest")):
        return "school"
    if any(token in haystack for token in ("arzt", "ärzt", "praxis", "klinik", "krankenhaus", "diagnose", "befund", "attest")):
        return "medical"
    if any(token in haystack for token in ("finanzamt", "steuer", "elster", "umsatzsteuer", "einkommensteuer", "steuerbescheid")):
        return "tax"
    return ""


def canonicalize_tag(tag: str) -> str:
    value = clean_name(tag)
    mapping = {
        "ärztliche atteste": "Attest",
        "aerztliche atteste": "Attest",
        "ärztliche bescheinigung": "Attest",
        "aerztliche bescheinigung": "Attest",
        "schulpflichtverletzung": "Schulpflicht",
        "fehlzeiten-attestforderung": "Fehlzeiten",
        "minderjährige kinder": "Minderjährige",
    }
    return mapping.get(value.casefold(), value)


def looks_like_institution_tag(tag: str) -> bool:
    lowered = clean_name(tag).casefold()
    return any(token in lowered for token in (
        "schule", "gericht", "amt", "behörde", "behoerde", "finanzamt",
        "realschule", "gymnasium", "familiengericht", "landgericht", "amtsgericht",
        "praxis", "klinik", "krankenhaus",
    ))


def refine_tags(result: dict, document: dict) -> list[str]:
    family = detect_document_family(document, result)
    correspondent = clean_name(str(result.get("correspondent", ""))).casefold()
    document_type = clean_name(str(result.get("document_type", ""))).casefold()
    title = clean_name(str(result.get("title", ""))).casefold()
    refined: list[str] = []
    seen: set[str] = set()
    for raw_tag in result.get("tags", []):
        tag = canonicalize_tag(str(raw_tag))
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        if looks_like_person_tag(tag):
            continue
        if correspondent and (key == correspondent or key in correspondent or correspondent in key):
            continue
        if document_type and (key == document_type or key in document_type):
            continue
        if title and len(key) > 5 and key in title:
            continue
        if re.fullmatch(r"\d{4}", tag):
            continue
        if family == "school":
            if key == "schule" or looks_like_institution_tag(tag):
                continue
        if family == "court":
            if looks_like_institution_tag(tag):
                continue
        if family == "tax":
            if looks_like_institution_tag(tag):
                continue
        seen.add(key)
        refined.append(tag[:50])
    return refined[:6]


def refine_result(result: dict, document: dict) -> dict:
    refined = dict(result)
    refined["tags"] = refine_tags(refined, document)
    return refined


def should_apply(result: dict) -> bool:
    threshold = float(env("PAPERLESS_AI_MIN_CONFIDENCE", "0.35"))
    confidence = result.get("confidence")
    if confidence is None:
        return True
    try:
        return float(confidence) >= threshold
    except (TypeError, ValueError):
        return True


def main() -> int:
    document_id = env("DOCUMENT_ID")
    api_url = env("PAPERLESS_API_URL")
    api_token = env("PAPERLESS_API_TOKEN")
    if not document_id:
        warn("DOCUMENT_ID is not set")
        return 0
    if not api_url or not api_token:
        warn("PAPERLESS_API_URL or PAPERLESS_API_TOKEN missing, skipping")
        return 0

    client = HttpClient(api_url, api_token)
    document = client.get(f"/api/documents/{document_id}/")
    if not isinstance(document, dict):
        raise RuntimeError(f"Unexpected document payload: {document}")

    existing_tags = list_all(client, "/api/tags/")
    existing_person_tags = [
        str(tag.get("name", ""))
        for tag in existing_tags
        if isinstance(tag, dict) and looks_like_person_tag(str(tag.get("name", "")))
    ]

    prompt = prompt_for_document(document, sorted(existing_person_tags, key=str.casefold))
    started = time.time()
    raw_result, response_meta = get_provider_response_details(prompt)
    result = refine_result(sanitize_result(raw_result), document)
    duration = round(time.time() - started, 2)
    model_info = response_meta.get("model", "-")
    if response_meta.get("fallback_used"):
        model_info = f"{model_info} (fallback from {response_meta.get('fallback_from', '-')})"
    log(f"LLM analyzed document {document_id} in {duration}s using {model_info}")

    if not should_apply(result):
        log(f"Skipped document {document_id}: confidence below threshold")
        return 0

    payload: dict = {}
    if result["title"]:
        payload["title"] = result["title"]

    current_correspondent = document.get("correspondent")
    if result["correspondent"]:
        correspondent_id = ensure_named_object(client, "/api/correspondents/", result["correspondent"])
        if correspondent_id is not None:
            if not isinstance(current_correspondent, dict) or int(current_correspondent.get("id", 0)) != correspondent_id:
                payload["correspondent"] = correspondent_id

    current_doc_type = document.get("document_type")
    if result["document_type"]:
        doc_type_id = ensure_named_object(client, "/api/document_types/", result["document_type"])
        if doc_type_id is not None:
            if not isinstance(current_doc_type, dict) or int(current_doc_type.get("id", 0)) != doc_type_id:
                payload["document_type"] = doc_type_id

    current_tags = document.get("tags", [])
    current_tag_ids = [int(tag["id"]) for tag in current_tags if isinstance(tag, dict) and "id" in tag]
    combined_tag_ids = list(current_tag_ids)
    for tag_id in resolve_tag_ids(client, result["tags"], document.get("content") or ""):
        if tag_id is not None and tag_id not in combined_tag_ids:
            combined_tag_ids.append(tag_id)
    if combined_tag_ids != current_tag_ids:
        payload["tags"] = combined_tag_ids

    if not payload:
        log(f"No metadata changes for document {document_id}")
        return 0

    client.patch(f"/api/documents/{document_id}/", payload)
    log(
        "Updated document "
        f"{document_id}: "
        f"title={payload.get('title', '-')}, "
        f"correspondent={result['correspondent'] or '-'}, "
        f"document_type={result['document_type'] or '-'}, "
        f"tags={','.join(result['tags']) or '-'}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        warn(str(exc))
        raise
