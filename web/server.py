#!/usr/bin/env python3
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer


HOST = os.getenv("OLLAMA_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("OLLAMA_WEB_PORT", "3000"))
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
PAPERLESS_CONF = os.getenv("PAPERLESS_CONF", "/opt/paperless/paperless.conf")
PAPERLESS_BACKFILL = os.getenv("PAPERLESS_BACKFILL", "/opt/paperless/ai_backfill.py")


HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ollama Web</title>
  <style>
    :root {
      --bg: #f3efe7;
      --panel: rgba(255,255,255,0.8);
      --line: #d7ccbb;
      --ink: #1d1a16;
      --muted: #6f6558;
      --accent: #1e5c49;
      --accent-2: #d8a743;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(216,167,67,0.15), transparent 30%),
        radial-gradient(circle at bottom right, rgba(30,92,73,0.16), transparent 32%),
        linear-gradient(135deg, #efe6d8, #f6f2eb 55%, #e9e0d2);
      min-height: 100vh;
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 18px 48px;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(8px);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 48px rgba(48, 35, 16, 0.12);
      overflow: hidden;
    }
    .hero {
      padding: 24px 24px 16px;
      border-bottom: 1px solid var(--line);
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 10px;
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 5vw, 58px);
      line-height: 0.95;
      font-weight: 600;
    }
    .sub {
      margin-top: 12px;
      max-width: 720px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.5;
    }
    .controls {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,0.45);
    }
    select, textarea, button {
      font: inherit;
    }
    select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
      background: rgba(255,255,255,0.85);
      color: var(--ink);
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 12px 18px;
      background: linear-gradient(135deg, var(--accent), #31765f);
      color: white;
      cursor: pointer;
      min-width: 130px;
    }
    button:disabled { opacity: 0.6; cursor: wait; }
    .chat {
      padding: 20px 24px;
      display: grid;
      gap: 14px;
      min-height: 360px;
      background:
        linear-gradient(rgba(255,255,255,0.35), rgba(255,255,255,0.35)),
        repeating-linear-gradient(
          to bottom,
          transparent 0,
          transparent 27px,
          rgba(130,112,84,0.08) 28px
        );
    }
    .msg {
      max-width: 86%;
      padding: 14px 16px;
      border-radius: 18px;
      white-space: pre-wrap;
      line-height: 1.45;
      animation: rise .18s ease-out;
    }
    .user {
      justify-self: end;
      background: #efe2c0;
      border: 1px solid #dbc48f;
    }
    .assistant {
      justify-self: start;
      background: rgba(255,255,255,0.9);
      border: 1px solid var(--line);
    }
    .composer {
      padding: 18px 24px 24px;
      display: grid;
      gap: 12px;
    }
    .meta {
      display: flex;
      gap: 12px;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(30,92,73,0.08);
      color: var(--accent);
      border: 1px solid rgba(30,92,73,0.18);
    }
    .section {
      padding: 20px 24px;
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.42);
    }
    .section h2 {
      margin: 0 0 6px;
      font-size: 24px;
    }
    .section p {
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.5;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 12px;
    }
    .field {
      display: grid;
      gap: 6px;
    }
    .field label {
      font-size: 13px;
      color: var(--muted);
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 14px;
    }
    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .secondary {
      background: linear-gradient(135deg, #8f7f68, #736552);
    }
    .logbox {
      margin-top: 14px;
      min-height: 120px;
      max-height: 320px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.92);
      padding: 12px 14px;
      white-space: pre-wrap;
      line-height: 1.45;
    }
    .statusline {
      margin-top: 10px;
      font-size: 14px;
      color: var(--muted);
    }
    .warn {
      color: #9d5a10;
    }
    @media (max-width: 760px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
    @keyframes rise {
      from { transform: translateY(6px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="hero">
        <div class="eyebrow">Local LLM</div>
        <h1>Ollama im Browser</h1>
        <div class="sub">
          Lokale Weboberflaeche fuer den laufenden Ollama-Server auf diesem Host.
          Antworten bleiben lokal und nutzen die installierten Modelle.
        </div>
      </div>
      <div class="controls">
        <select id="model"></select>
        <button id="clear">Verlauf loeschen</button>
      </div>
      <div id="chat" class="chat"></div>
      <div class="composer">
        <textarea id="prompt" rows="5" placeholder="Schreibe deine Nachricht..."></textarea>
        <div class="meta">
          <span class="badge">Port 3000</span>
          <span id="status">Bereit.</span>
        </div>
        <button id="send">Senden</button>
      </div>
      <div class="section">
        <h2>Paperless KI-Nachlauf</h2>
        <p>
          Bereits vorhandene Paperless-Dokumente koennen hier einmalig durch die KI
          nachbearbeitet werden.
        </p>
        <div class="grid">
          <div class="field">
            <label for="backfill-limit">Limit</label>
            <input id="backfill-limit" type="number" min="1" value="10">
          </div>
          <div class="field">
            <label for="backfill-query">Query</label>
            <input id="backfill-query" type="text" placeholder="optional">
          </div>
          <div class="field">
            <label for="backfill-from-id">Ab Dokument-ID</label>
            <input id="backfill-from-id" type="number" min="1" placeholder="optional">
          </div>
        </div>
        <label class="check">
          <input id="backfill-missing" type="checkbox" checked>
          Nur Dokumente mit fehlenden Metadaten
        </label>
        <div class="actions">
          <button id="backfill-preview" class="secondary">Vorschau</button>
          <button id="backfill-run">Backfill starten</button>
        </div>
        <div id="backfill-status" class="statusline">Noch kein Lauf gestartet.</div>
        <div id="backfill-log" class="logbox">Bereit.</div>
      </div>
    </div>
  </div>
  <script>
    const chatEl = document.getElementById('chat');
    const promptEl = document.getElementById('prompt');
    const modelEl = document.getElementById('model');
    const statusEl = document.getElementById('status');
    const sendBtn = document.getElementById('send');
    const clearBtn = document.getElementById('clear');
    const backfillLimitEl = document.getElementById('backfill-limit');
    const backfillQueryEl = document.getElementById('backfill-query');
    const backfillFromIdEl = document.getElementById('backfill-from-id');
    const backfillMissingEl = document.getElementById('backfill-missing');
    const backfillPreviewBtn = document.getElementById('backfill-preview');
    const backfillRunBtn = document.getElementById('backfill-run');
    const backfillStatusEl = document.getElementById('backfill-status');
    const backfillLogEl = document.getElementById('backfill-log');
    let messages = [];

    function addMessage(role, content) {
      messages.push({ role, content });
      render();
    }

    function render() {
      chatEl.innerHTML = '';
      for (const msg of messages) {
        const div = document.createElement('div');
        div.className = `msg ${msg.role}`;
        div.textContent = msg.content;
        chatEl.appendChild(div);
      }
      chatEl.scrollTop = chatEl.scrollHeight;
    }

    async function loadModels() {
      const res = await fetch('/api/models');
      const data = await res.json();
      modelEl.innerHTML = '';
      for (const model of data.models || []) {
        const option = document.createElement('option');
        option.value = model.name;
        option.textContent = model.name;
        modelEl.appendChild(option);
      }
    }

    async function sendPrompt() {
      const prompt = promptEl.value.trim();
      if (!prompt) return;
      addMessage('user', prompt);
      promptEl.value = '';
      sendBtn.disabled = true;
      statusEl.textContent = 'Modell arbeitet...';
      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            model: modelEl.value,
            messages: messages.map(m => ({
              role: m.role === 'assistant' ? 'assistant' : 'user',
              content: m.content
            }))
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        addMessage('assistant', data.message?.content || '(leer)');
        statusEl.textContent = 'Bereit.';
      } catch (err) {
        addMessage('assistant', `Fehler: ${err.message}`);
        statusEl.textContent = 'Fehler.';
      } finally {
        sendBtn.disabled = false;
      }
    }

    function getBackfillPayload(dryRun) {
      return {
        dry_run: dryRun,
        limit: Number(backfillLimitEl.value || 0),
        query: backfillQueryEl.value.trim(),
        from_id: Number(backfillFromIdEl.value || 0),
        only_missing_metadata: backfillMissingEl.checked
      };
    }

    async function runBackfill(dryRun) {
      if (!dryRun) {
        const limit = Number(backfillLimitEl.value || 0);
        const query = backfillQueryEl.value.trim();
        const warning = [
          'Der echte Backfill startet jetzt die KI-Nachbearbeitung fuer vorhandene Paperless-Dokumente.',
          limit > 0 ? `Limit: ${limit}` : 'Limit: unbegrenzt',
          query ? `Query: ${query}` : 'Query: keine',
          backfillMissingEl.checked ? 'Nur fehlende Metadaten: ja' : 'Nur fehlende Metadaten: nein'
        ].join('\\n');
        if (!window.confirm(warning + '\\n\\nFortfahren?')) {
          backfillStatusEl.textContent = 'Start abgebrochen.';
          return;
        }
      }
      backfillPreviewBtn.disabled = true;
      backfillRunBtn.disabled = true;
      backfillStatusEl.textContent = dryRun ? 'Vorschau laeuft...' : 'Backfill laeuft...';
      backfillStatusEl.className = 'statusline';
      backfillLogEl.textContent = dryRun ? 'Vorschau laeuft...' : 'Backfill laeuft...';
      try {
        const res = await fetch('/api/paperless/backfill', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(getBackfillPayload(dryRun))
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        backfillLogEl.textContent = data.output || 'Keine Ausgabe';
        backfillStatusEl.textContent = dryRun ? 'Vorschau abgeschlossen.' : 'Backfill abgeschlossen.';
      } catch (err) {
        backfillLogEl.textContent = `Fehler: ${err.message}`;
        backfillStatusEl.textContent = 'Fehler beim Backfill.';
        backfillStatusEl.className = 'statusline warn';
      } finally {
        backfillPreviewBtn.disabled = false;
        backfillRunBtn.disabled = false;
      }
    }

    sendBtn.addEventListener('click', sendPrompt);
    promptEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendPrompt();
    });
    clearBtn.addEventListener('click', () => {
      messages = [];
      render();
      statusEl.textContent = 'Verlauf geloescht.';
    });
    backfillPreviewBtn.addEventListener('click', () => runBackfill(true));
    backfillRunBtn.addEventListener('click', () => runBackfill(false));

    loadModels().catch(() => {
      statusEl.textContent = 'Modelle konnten nicht geladen werden.';
    });
  </script>
</body>
</html>
"""


def ollama_request(path: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"{OLLAMA_URL}{path}"
    headers = {"Content-Type": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, {"error": body}
    except Exception as exc:
        return 500, {"error": str(exc)}


def load_paperless_env() -> dict[str, str]:
    env_map: dict[str, str] = {}
    path = Path(PAPERLESS_CONF)
    if not path.is_file():
        raise RuntimeError(f"Paperless config not found: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env_map[key.strip()] = value.strip()
    return env_map


def run_paperless_backfill(payload: dict) -> tuple[int, dict]:
    if not Path(PAPERLESS_BACKFILL).is_file():
        return 500, {"error": f"Backfill script not found: {PAPERLESS_BACKFILL}"}

    paperless_env = load_paperless_env()
    child_env = os.environ.copy()
    for key in (
        "PAPERLESS_API_URL",
        "PAPERLESS_API_TOKEN",
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
        if key in paperless_env:
            child_env[key] = paperless_env[key]

    cmd = ["/usr/bin/python3", PAPERLESS_BACKFILL]
    limit = int(payload.get("limit") or 0)
    from_id = int(payload.get("from_id") or 0)
    query = str(payload.get("query") or "").strip()
    if payload.get("only_missing_metadata"):
        cmd.append("--only-missing-metadata")
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    if from_id > 0:
        cmd.extend(["--from-id", str(from_id)])
    if query:
        cmd.extend(["--query", query])
    if payload.get("dry_run"):
        cmd.append("--dry-run")

    result = subprocess.run(
        cmd,
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=3600,
    )
    output = (result.stdout or "") + (result.stderr or "")
    status = 200 if result.returncode == 0 else 500
    return status, {"output": output.strip(), "returncode": result.returncode}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/api/models":
            status, payload = ollama_request("/api/tags")
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if self.path not in ("/api/chat", "/api/paperless/backfill"):
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return
        if self.path == "/api/chat":
            payload["stream"] = False
            status, response = ollama_request("/api/chat", payload)
        else:
            try:
                status, response = run_paperless_backfill(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        self._send(status, json.dumps(response).encode("utf-8"), "application/json")

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Ollama web listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
