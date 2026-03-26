#!/usr/bin/env python3
import json
import os
import urllib.error
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer


HOST = os.getenv("OLLAMA_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("OLLAMA_WEB_PORT", "3000"))
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


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
    </div>
  </div>
  <script>
    const chatEl = document.getElementById('chat');
    const promptEl = document.getElementById('prompt');
    const modelEl = document.getElementById('model');
    const statusEl = document.getElementById('status');
    const sendBtn = document.getElementById('send');
    const clearBtn = document.getElementById('clear');
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

    sendBtn.addEventListener('click', sendPrompt);
    promptEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendPrompt();
    });
    clearBtn.addEventListener('click', () => {
      messages = [];
      render();
      statusEl.textContent = 'Verlauf geloescht.';
    });

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
        if self.path != "/api/chat":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, b'{"error":"invalid json"}', "application/json")
            return
        payload["stream"] = False
        status, response = ollama_request("/api/chat", payload)
        self._send(status, json.dumps(response).encode("utf-8"), "application/json")

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Ollama web listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
