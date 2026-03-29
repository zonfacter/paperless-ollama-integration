#!/usr/bin/env python3
import base64
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


def prompt_for_tags(document: dict, result: dict) -> str:
    content_chars = int(env("PAPERLESS_AI_TAG_CONTENT_CHARS", env("PAPERLESS_AI_CONTENT_CHARS", "5000")))
    content = truncate_text(document.get("content") or "", content_chars)
    title = clean_name(str(result.get("title", "")))
    correspondent = clean_name(str(result.get("correspondent", "")))
    document_type = clean_name(str(result.get("document_type", "")))
    reason = truncate_text(str(result.get("reason", "")), 200)
    family = detect_document_family(document, result) or "-"
    allowed_tags = sorted(load_allowed_tags_by_family().get(family, set()), key=str.casefold) if family != "-" else []
    family_rules = load_tag_rules_by_family().get(family, {}) if family != "-" else {}
    allowed_tags_text = ", ".join(allowed_tags) if allowed_tags else "-"
    if family_rules:
        rule_lines = [f"- {tag}: {', '.join(keywords)}" for tag, keywords in family_rules.items()]
        family_rules_text = "\n".join(rule_lines)
    else:
        family_rules_text = "-"
    return f"""Du waehlst nur wenige, gute Archiv-Tags fuer paperless-ngx.
Antworte nur als JSON.

Ziel:
- Liefere 1 bis 3 Haupttags.
- Nur der Hauptkontext des Dokuments.
- Keine Nebenbegriffe und keine Randthemen.

Leitplanken:
- Korrespondenz: {correspondent or "-"}
- Dokumenttyp: {document_type or "-"}
- Dokumentfamilie: {family}
- Titel: {title or "-"}
- Einordnung: {reason or "-"}
- Erlaubte Tags fuer diese Familie: {allowed_tags_text}
- Regelhinweise fuer diese Familie:
{family_rules_text}

Regeln:
- Keine Personen, keine Orte, keine Institutionen als Tags.
- Keine Kanzleinamen, Gerichte, Aemter, Schulen, Praxen, Krankenhaeuser als Tags.
- Keine Jahre, Aktenzeichen, IDs, Formularnummern oder Adressen.
- Bei anwaltlichen, behoerdlichen oder gerichtlichen Schreiben muessen Tags den Vorgang beschreiben, nicht den Absender.
- Bei medizinischen Dokumenten nur Diagnose, Befund, Behandlung, Attest, Labor, Medikation o. ae., wenn das Hauptthema es traegt.
- Bei schulischen Schreiben nur den Vorgang oder die Massnahme taggen, nicht die Schule oder beteiligte Personen.
- Nutze nur Tags, die als Archivkategorie wiederverwendbar sind.
- Bevorzuge die oben erlaubten Tags.
- Wenn ein Regelhinweis klar passt, nimm genau diesen Archiv-Tag statt eines freien Synonyms.
- Wenn unklar, lieber weniger Tags.

Rueckgabeformat:
{{"tags":["string"],"reason":"kurz","confidence":0.0}}

OCR-Inhalt:
{content}
"""


def call_openai(prompt: str, model: str | None = None) -> dict:
    api_key = env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = model or env("PAPERLESS_AI_OPENAI_MODEL", "gpt-5.4-mini")
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


def get_provider_response_details(
    prompt: str,
    model_override: str | None = None,
    timeout_override: float | None = None,
    fallback_model_override: str | None = None,
    fallback_timeout_override: float | None = None,
    fallback_enabled_override: bool | None = None,
) -> tuple[dict, dict]:
    provider = env("PAPERLESS_AI_PROVIDER", "ollama").lower()
    if provider == "openai":
        return call_openai(prompt, model=model_override or env("PAPERLESS_AI_OPENAI_MODEL", "gpt-5.4-mini")), {
            "provider": "openai",
            "model": model_override or env("PAPERLESS_AI_OPENAI_MODEL", "gpt-5.4-mini"),
            "fallback_used": False,
        }
    if provider == "ollama":
        primary_model = model_override or env("PAPERLESS_AI_OLLAMA_MODEL", "qwen2.5:7b-instruct")
        primary_timeout = timeout_override if timeout_override is not None else float(env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "300"))
        fallback_enabled = fallback_enabled_override if fallback_enabled_override is not None else env("PAPERLESS_AI_FALLBACK_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        fallback_model = fallback_model_override or env("PAPERLESS_AI_FALLBACK_MODEL", "qwen2.5:3b-instruct")
        fallback_timeout = fallback_timeout_override if fallback_timeout_override is not None else float(env("PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS", str(primary_timeout)))
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
    content = str(document.get("content", "") or "")
    title = str(document.get("title", "") or "")
    original = str(document.get("original_file_name", "") or "")
    result_title = str(result.get("title", "") or "")
    result_type = str(result.get("document_type", "") or "")
    correspondent = str(result.get("correspondent", "") or "")
    reason = str(result.get("reason", "") or "")
    haystack = " ".join(
        str(value or "")
        for value in (
            content,
            title,
            original,
            result_title,
            result_type,
            correspondent,
            reason,
        )
    ).casefold()
    header = "\n".join(content.splitlines()[:30]).casefold()
    correspondent_cf = clean_name(correspondent).casefold()
    medical_markers = (
        "gemeinschaftspraxis", "kinder und jugendmedizin", "facharzt", "arzt",
        "ärzt", "aerzt", "praxis", "klinik", "krankenhaus", "allergologie",
        "kinder-pneumolog", "kinderarzt", "med."
    )
    school_markers = (
        "schule", "realschule", "gymnasium", "schulleiter", "schulpflicht",
        "unterricht", "fehlzeiten"
    )
    if any(token in correspondent_cf for token in medical_markers) or any(token in header for token in medical_markers):
        return "medical"
    if any(token in correspondent_cf for token in school_markers) or any(token in header for token in school_markers):
        return "school"
    if any(token in haystack for token in ("amtsgericht", "landgericht", "oberlandesgericht", "familiengericht", "beschluss", "pflegschaft", "sofortige beschwerde")):
        return "court"
    if any(token in haystack for token in ("kanzlei", "rechtsanwalt", "rechtsanwält", "rechtsanwaelt", "schriftsatz", "stellungnahme", "gegnerbevollmächtig", "gegnerbevollmaechtig", "strafprozeßvollmacht", "strafprozessvollmacht")):
        return "lawyer"
    if any(token in haystack for token in ("schule", "realschule", "gymnasium", "schulleiter", "fehltag", "schulpflicht")):
        return "school"
    if any(token in haystack for token in ("arzt", "ärzt", "praxis", "klinik", "krankenhaus", "diagnose", "befund", "attest")):
        return "medical"
    if any(token in haystack for token in ("finanzamt", "steuer", "elster", "umsatzsteuer", "einkommensteuer", "steuerbescheid")):
        return "tax"
    return ""


def canonicalize_tag(tag: str) -> str:
    value = clean_name(tag).replace("/", " ").replace("_", " ")
    value = normalize_whitespace(value)
    mapping = {
        "schulpflicht": "Schulpflicht",
        "fehlzeiten": "Fehlzeiten",
        "familienrecht": "Familienrecht",
        "ermittlungsverfahren": "Ermittlungsverfahren",
        "strafverfahren": "Strafverfahren",
        "unterhalt": "Unterhalt",
        "behandlung": "Behandlung",
        "labor": "Labor",
        "medikation": "Medikation",
        "diagnose": "Diagnose",
        "befund": "Befund",
        "kinderarzt": "Kinderarzt",
        "psychotherapie": "Psychotherapie",
        "kieferorthopädie": "Kieferorthopädie",
        "kieferorthopaedie": "Kieferorthopädie",
        "zahnmedizin": "Zahnmedizin",
        "einkommensteuer": "Einkommensteuer",
        "steuererklärung": "Steuererklärung",
        "steuererklaerung": "Steuererklärung",
        "formular": "Formular",
        "elster": "ELSTER",
        "school fehlzeiten": "Fehlzeiten",
        "court pflegschaft": "Pflegschaft",
        "aufhebung pflegschaft": "Pflegschaft",
        "aufhebung der pflegschaft": "Pflegschaft",
        "aufhebung pflegschaft der kinder": "Pflegschaft",
        "ärztliches attest": "Attest",
        "aerztliches attest": "Attest",
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


DEFAULT_ALLOWED_TAGS_BY_FAMILY = {
    "lawyer": {
        "Familienrecht", "Unterhalt", "Umgangsrecht", "Sorgerecht",
        "Strafverfahren", "Ermittlungsverfahren", "Schriftsatz",
        "Stellungnahme", "Vollmacht", "Gewaltschutz",
    },
    "school": {
        "Fehlzeiten", "Schulpflicht", "Attest", "Bußgeld", "Versetzung",
        "Zeugnis", "Förderung", "Unterrichtsausfall", "Schulpsychologie",
    },
    "court": {
        "Familienrecht", "Pflegschaft", "Unterhalt", "Umgangsrecht",
        "Ermittlungsverfahren", "Strafverfahren", "Beschwerde",
        "Beschluss", "Sorgerecht", "Gewaltschutz",
    },
    "medical": {
        "Diagnose", "Befund", "Attest", "Labor", "Medikation",
        "Psychotherapie", "Kieferorthopädie", "Kinderarzt",
        "Behandlung", "Krankschreibung", "Allergologie",
        "Zahnmedizin", "Intelligenztest",
    },
    "tax": {
        "Einkommensteuer", "Steuererklärung", "ELSTER", "Formular",
        "Sonderausgaben", "Renteneinkünfte", "Kirchensteuer",
        "Außergewöhnliche Belastungen", "Kapitaleinkünfte",
    },
}


DEFAULT_TAG_RULES_BY_FAMILY = {
    "school": {
        "Fehlzeiten": ["fehlzeit", "fehlzeiten des schülers", "fehlzeiten des schuelers"],
        "Schulpflicht": ["schulpflicht", "schulpflichtverletzung"],
        "Attest": ["attest", "ärzt", "aerzt"],
    },
    "court": {
        "Beschluss": ["beschluss"],
        "Pflegschaft": ["pflegschaft"],
        "Familienrecht": ["familiengericht", "familienrecht", "16 f "],
        "Unterhalt": ["unterhalt"],
    },
    "medical": {
        "Attest": ["attest", "ärztliche bescheinigung", "aerztliche bescheinigung"],
        "Kinderarzt": ["kinderarzt", "kinder und jugendmedizin"],
        "Befund": ["befund"],
        "Diagnose": ["diagnose"],
    },
    "tax": {
        "Einkommensteuer": ["einkommensteuer"],
        "Umsatzsteuer": ["umsatzsteuer"],
        "Steuerbescheid": ["steuerbescheid"],
        "Steuererklärung": ["steuererklärung", "steuererklaerung"],
        "ELSTER": ["elster"],
    },
    "lawyer": {
        "Familienrecht": ["familienrecht"],
        "Unterhalt": ["unterhalt"],
        "Umgangsrecht": ["umgang"],
        "Sorgerecht": ["sorgerecht"],
        "Schriftsatz": ["schriftsatz"],
    },
}


def load_allowed_tags_by_family() -> dict[str, set[str]]:
    raw_b64 = env("PAPERLESS_AI_TAG_ALLOWLISTS_B64", "")
    source = DEFAULT_ALLOWED_TAGS_BY_FAMILY
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                normalized: dict[str, set[str]] = {}
                for family, tags in parsed.items():
                    if not isinstance(tags, list):
                        continue
                    normalized[str(family)] = {clean_name(str(tag)) for tag in tags if clean_name(str(tag))}
                if normalized:
                    source = normalized
        except Exception as exc:
            warn(f"Could not parse PAPERLESS_AI_TAG_ALLOWLISTS_B64, using defaults: {exc}")
    return {family: set(tags) for family, tags in source.items()}


def default_allowed_tags_by_family_json() -> str:
    serializable = {family: sorted(tags, key=str.casefold) for family, tags in DEFAULT_ALLOWED_TAGS_BY_FAMILY.items()}
    return json.dumps(serializable, indent=2, ensure_ascii=False)


def load_tag_rules_by_family() -> dict[str, dict[str, list[str]]]:
    raw_b64 = env("PAPERLESS_AI_TAG_RULES_B64", "")
    source = DEFAULT_TAG_RULES_BY_FAMILY
    if raw_b64:
        try:
            decoded = base64.b64decode(raw_b64).decode("utf-8")
            parsed = json.loads(decoded)
            if isinstance(parsed, dict):
                normalized: dict[str, dict[str, list[str]]] = {}
                for family, rules in parsed.items():
                    if not isinstance(rules, dict):
                        continue
                    family_rules: dict[str, list[str]] = {}
                    for tag_name, keywords in rules.items():
                        cleaned_tag = clean_name(str(tag_name))
                        if not cleaned_tag or not isinstance(keywords, list):
                            continue
                        cleaned_keywords = [clean_name(str(keyword)).casefold() for keyword in keywords if clean_name(str(keyword))]
                        if cleaned_keywords:
                            family_rules[cleaned_tag] = cleaned_keywords
                    if family_rules:
                        normalized[str(family)] = family_rules
                if normalized:
                    source = normalized
        except Exception as exc:
            warn(f"Could not parse PAPERLESS_AI_TAG_RULES_B64, using defaults: {exc}")
    return source


def default_tag_rules_by_family_json() -> str:
    return json.dumps(DEFAULT_TAG_RULES_BY_FAMILY, indent=2, ensure_ascii=False)


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
        if title and len(key) > 5 and key in title and family not in {"school", "court", "medical", "tax", "lawyer"}:
            continue
        if re.fullmatch(r"\d{4}", tag):
            continue
        if family == "school":
            if key == "schule" or looks_like_institution_tag(tag):
                continue
        if family == "court":
            if looks_like_institution_tag(tag):
                continue
        if family == "lawyer":
            if looks_like_institution_tag(tag):
                continue
        if family == "tax":
            if looks_like_institution_tag(tag):
                continue
        if family:
            allowed = load_allowed_tags_by_family().get(family, set())
            if allowed and tag not in allowed:
                continue
        seen.add(key)
        refined.append(tag[:50])
    return refined[:6]


def fallback_tags_for_family(result: dict, document: dict) -> list[str]:
    family = detect_document_family(document, result)
    content = " ".join(
        str(value or "")
        for value in (
            document.get("content", ""),
            result.get("title", ""),
            result.get("document_type", ""),
            result.get("reason", ""),
        )
    ).casefold()
    rules = load_tag_rules_by_family().get(family, {})
    tags: list[str] = []
    for tag_name, keywords in rules.items():
        if any(keyword in content for keyword in keywords):
            tags.append(tag_name)
    return tags[:3]


def refine_result(result: dict, document: dict) -> dict:
    refined = dict(result)
    refined["tags"] = refine_tags(refined, document)
    if not refined["tags"]:
        refined["tags"] = refine_tags({**refined, "tags": fallback_tags_for_family(refined, document)}, document)
    return refined


def sanitize_tag_result(result: dict | list | None) -> list[str]:
    if isinstance(result, dict):
        tags = result.get("tags", [])
    elif isinstance(result, list):
        tags = result
    else:
        tags = []
    if not isinstance(tags, list):
        return []
    clean_tags: list[str] = []
    seen: set[str] = set()
    for item in tags:
        tag = clean_name(str(item))
        if not tag:
            continue
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        clean_tags.append(tag[:50])
    return clean_tags[:3]


def merge_tag_candidates(primary: list[str], secondary: list[str], limit: int = 3) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for source in (primary, secondary):
        for item in source:
            tag = clean_name(str(item))
            if not tag:
                continue
            key = tag.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(tag)
            if len(merged) >= limit:
                return merged
    return merged


def assess_review_flags(result: dict, document: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    family = detect_document_family(document, result)
    confidence_value = result.get("confidence")
    threshold = float(env("PAPERLESS_AI_REVIEW_MIN_CONFIDENCE", "0.8"))
    try:
        confidence = float(confidence_value) if confidence_value is not None else 1.0
    except (TypeError, ValueError):
        confidence = 1.0
    if confidence < threshold:
        reasons.append(f"confidence<{threshold}")
    tags = [clean_name(str(tag)) for tag in result.get("tags", []) if clean_name(str(tag))]
    if not tags:
        reasons.append("tags_missing")
    elif family == "school" and tags == ["Attest"]:
        reasons.append("school_tags_too_narrow")
    elif family == "court" and tags == ["Beschluss"]:
        reasons.append("court_tags_too_narrow")
    title = clean_name(str(result.get("title", ""))).casefold()
    document_type = clean_name(str(result.get("document_type", ""))).casefold()
    if family == "school" and "ärztliche bescheinigung" in document_type:
        reasons.append("school_doc_type_mismatch")
    if family == "medical" and title.startswith("schule:"):
        reasons.append("medical_title_mismatch")
    if not clean_name(str(result.get("correspondent", ""))):
        reasons.append("correspondent_missing")
    if not clean_name(str(result.get("document_type", ""))):
        reasons.append("document_type_missing")
    needed = env("PAPERLESS_AI_REVIEW_TAG_ENABLED", "true").lower() in ("1", "true", "yes", "on") and bool(reasons)
    return needed, reasons


def apply_tag_review(document: dict, result: dict) -> tuple[dict, dict]:
    review_enabled = env("PAPERLESS_AI_TAG_REVIEW_ENABLED", "true").lower() in ("1", "true", "yes", "on")
    if not review_enabled:
        return refine_result(result, document), {"enabled": False, "model": ""}
    prompt = prompt_for_tags(document, result)
    tag_model = env("PAPERLESS_AI_TAG_OLLAMA_MODEL", env("PAPERLESS_AI_OLLAMA_MODEL", "qwen3.5:9b"))
    tag_timeout = float(env("PAPERLESS_AI_TAG_HTTP_TIMEOUT_SECONDS", env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "600")))
    fallback_model = env("PAPERLESS_AI_TAG_FALLBACK_MODEL", env("PAPERLESS_AI_FALLBACK_MODEL", "qwen3.5:0.8b"))
    fallback_timeout = float(env("PAPERLESS_AI_TAG_FALLBACK_HTTP_TIMEOUT_SECONDS", env("PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS", str(tag_timeout))))
    fallback_enabled = env("PAPERLESS_AI_TAG_FALLBACK_ENABLED", env("PAPERLESS_AI_FALLBACK_ENABLED", "true")).lower() in ("1", "true", "yes", "on")
    raw_tags, meta = get_provider_response_details(
        prompt,
        model_override=tag_model,
        timeout_override=tag_timeout,
        fallback_model_override=fallback_model,
        fallback_timeout_override=fallback_timeout,
        fallback_enabled_override=fallback_enabled,
    )
    reviewed = dict(result)
    reviewed["tags"] = merge_tag_candidates(
        fallback_tags_for_family(result, document),
        sanitize_tag_result(raw_tags),
    )
    reviewed = refine_result(reviewed, document)
    meta["enabled"] = True
    return reviewed, meta


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
    tag_meta = {"enabled": False, "model": ""}
    try:
        result, tag_meta = apply_tag_review(document, result)
    except Exception as exc:
        warn(f"Tag review failed for document {document_id}: {exc}")
    review_needed, review_reasons = assess_review_flags(result, document)
    result["_review_needed"] = review_needed
    result["_review_reasons"] = review_reasons
    duration = round(time.time() - started, 2)
    model_info = response_meta.get("model", "-")
    if response_meta.get("fallback_used"):
        model_info = f"{model_info} (fallback from {response_meta.get('fallback_from', '-')})"
    tag_model_info = tag_meta.get("model", "-") if tag_meta.get("enabled") else "-"
    log(f"LLM analyzed document {document_id} in {duration}s using {model_info}; tag_review={tag_model_info}")

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
    if review_needed:
        review_tag_id = ensure_named_object(
            client,
            "/api/tags/",
            env("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen"),
            {"color": env("PAPERLESS_AI_REVIEW_TAG_COLOR", "#7dd3fc")},
        )
        if review_tag_id is not None and review_tag_id not in combined_tag_ids:
            combined_tag_ids.append(review_tag_id)
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
        f"tags={','.join(result['tags']) or '-'}, "
        f"review={'yes' if review_needed else 'no'}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        warn(str(exc))
        raise
