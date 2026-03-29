#!/usr/bin/env python3
import base64
import json
import importlib.util
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer


HOST = os.getenv("OLLAMA_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("OLLAMA_WEB_PORT", "3000"))
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
PAPERLESS_CONF = os.getenv("PAPERLESS_CONF", "/opt/paperless/paperless.conf")
PAPERLESS_BACKFILL = os.getenv("PAPERLESS_BACKFILL", "/opt/paperless/ai_backfill.py")
PAPERLESS_MODEL_HELPER = os.getenv("PAPERLESS_MODEL_HELPER", "/usr/local/sbin/paperless-set-ollama-model")
PAPERLESS_AI_HELPER = os.getenv("PAPERLESS_AI_HELPER", "/usr/local/sbin/paperless-ai-admin")
PREVIEW_CONFIG_PATH = os.getenv("PAPERLESS_PREVIEW_CONFIG_PATH", "/home/thomas/ollama-web/preview_config.json")
PREVIEW_JOBS: dict[str, dict] = {}
PREVIEW_JOBS_LOCK = threading.Lock()


HTML = """<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Paperless AI Console</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --bg-2: #edf2f8;
      --panel: rgba(255, 255, 255, 0.86);
      --panel-strong: rgba(255, 255, 255, 0.94);
      --line: rgba(16, 24, 40, 0.09);
      --line-strong: rgba(16, 24, 40, 0.16);
      --ink: #0f1728;
      --muted: #5d6880;
      --accent: #0b6bcb;
      --accent-2: #0e9f6e;
      --accent-soft: rgba(11, 107, 203, 0.1);
      --shadow: 0 30px 80px rgba(15, 23, 40, 0.12);
      --radius: 24px;
      --radius-sm: 16px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI Variable", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(11, 107, 203, 0.14), transparent 26%),
        radial-gradient(circle at 80% 0%, rgba(14, 159, 110, 0.14), transparent 22%),
        radial-gradient(circle at bottom right, rgba(99, 102, 241, 0.12), transparent 30%),
        linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
      min-height: 100vh;
    }
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.45) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.45) 1px, transparent 1px);
      background-size: 28px 28px;
      mask-image: linear-gradient(180deg, rgba(0,0,0,0.45), transparent 80%);
    }
    .wrap {
      max-width: 1820px;
      margin: 0 auto;
      padding: 28px 20px 56px;
    }
    .app-shell {
      display: grid;
      grid-template-columns: 190px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }
    .sidebar {
      position: sticky;
      top: 300px;
      display: grid;
      gap: 14px;
      justify-self: start;
      transform: translateX(-200px);
    }
    .nav-card {
      background: var(--panel);
      backdrop-filter: blur(16px);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: var(--shadow);
      padding: 12px;
    }
    .nav-list {
      display: grid;
      gap: 10px;
    }
    .nav-btn {
      width: 100%;
      min-width: 0;
      text-align: left;
      padding: 14px 14px;
      border-radius: 18px;
      background: rgba(255,255,255,0.76);
      color: var(--ink);
      box-shadow: none;
      border: 1px solid var(--line);
    }
    .nav-btn:hover:not(.active) {
      transform: none;
      box-shadow: none;
      background: rgba(255,255,255,0.92);
    }
    .nav-btn.active {
      background: linear-gradient(135deg, var(--accent), #2e89ea);
      color: white;
      border-color: transparent;
      box-shadow: 0 16px 30px rgba(11, 107, 203, 0.22);
    }
    .nav-btn small {
      display: block;
      margin-top: 4px;
      opacity: 0.8;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0;
    }
    .layout-toggle {
      display: inline-flex;
      gap: 8px;
      padding: 6px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.74);
    }
    .toggle-btn {
      min-width: 0;
      padding: 10px 14px;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      box-shadow: none;
      border: 0;
    }
    .toggle-btn.active {
      background: linear-gradient(135deg, var(--accent), #2e89ea);
      color: white;
      box-shadow: 0 12px 24px rgba(11, 107, 203, 0.18);
    }
    .workspace {
      display: grid;
      gap: 18px;
      min-width: 0;
    }
    .view {
      display: none;
      gap: 18px;
    }
    .view.active {
      display: grid;
    }
    .card {
      background: var(--panel);
      backdrop-filter: blur(16px);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .hero {
      position: relative;
      padding: 32px 32px 26px;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,255,255,0.72)),
        radial-gradient(circle at top right, rgba(11, 107, 203, 0.12), transparent 34%);
    }
    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.8fr);
      gap: 24px;
      align-items: end;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.18em;
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
      margin-bottom: 14px;
    }
    h1 {
      margin: 0;
      font-size: clamp(34px, 5vw, 64px);
      line-height: 0.92;
      letter-spacing: -0.04em;
      font-weight: 800;
      max-width: 900px;
    }
    .sub {
      margin-top: 16px;
      max-width: 760px;
      color: var(--muted);
      font-size: 17px;
      line-height: 1.6;
    }
    .hero-panel {
      display: grid;
      gap: 12px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(255,255,255,0.72));
      box-shadow: 0 20px 40px rgba(15, 23, 40, 0.08);
    }
    .hero-kicker {
      font-size: 12px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 700;
    }
    .hero-metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .hero-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 18px;
    }
    .metric {
      padding: 14px 12px;
      border-radius: 18px;
      background: rgba(248, 250, 252, 0.96);
      border: 1px solid rgba(16, 24, 40, 0.06);
    }
    .metric strong {
      display: block;
      font-size: 20px;
      letter-spacing: -0.03em;
      margin-bottom: 4px;
    }
    .metric span {
      display: block;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.45;
    }
    .controls {
      position: sticky;
      top: 0;
      z-index: 10;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 14px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: rgba(244, 247, 251, 0.78);
      backdrop-filter: blur(14px);
    }
    select, textarea, button, input {
      font: inherit;
    }
    select, textarea, input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 13px 15px;
      background: var(--panel-strong);
      color: var(--ink);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
      transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
    }
    select:focus, textarea:focus, input:focus {
      outline: none;
      border-color: rgba(11, 107, 203, 0.55);
      box-shadow: 0 0 0 4px rgba(11, 107, 203, 0.12);
    }
    button {
      border: 0;
      border-radius: var(--radius-sm);
      padding: 13px 18px;
      background: linear-gradient(135deg, var(--accent), #2e89ea);
      color: white;
      cursor: pointer;
      min-width: 140px;
      font-weight: 700;
      letter-spacing: -0.01em;
      box-shadow: 0 16px 30px rgba(11, 107, 203, 0.22);
      transition: transform .16s ease, box-shadow .16s ease, opacity .16s ease;
    }
    button:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 18px 34px rgba(11, 107, 203, 0.28);
    }
    button:disabled { opacity: 0.6; cursor: wait; }
    .chat {
      padding: 26px 24px 18px;
      display: grid;
      gap: 16px;
      min-height: 320px;
      background:
        linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.2)),
        radial-gradient(circle at top left, rgba(11, 107, 203, 0.05), transparent 28%);
    }
    .msg {
      max-width: 86%;
      padding: 16px 18px;
      border-radius: 22px;
      white-space: pre-wrap;
      line-height: 1.55;
      animation: rise .18s ease-out;
      box-shadow: 0 10px 26px rgba(15, 23, 40, 0.08);
    }
    .user {
      justify-self: end;
      background: linear-gradient(135deg, #0b6bcb, #2e89ea);
      color: white;
      border: 1px solid rgba(255,255,255,0.2);
    }
    .assistant {
      justify-self: start;
      background: rgba(255,255,255,0.96);
      border: 1px solid var(--line);
    }
    .composer {
      padding: 16px 24px 26px;
      display: grid;
      gap: 14px;
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.56);
    }
    .meta {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 7px 12px;
      background: var(--accent-soft);
      color: var(--accent);
      border: 1px solid rgba(11,107,203,0.16);
      font-weight: 700;
    }
    .section {
      padding: 28px 24px;
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.36);
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      margin-bottom: 18px;
      flex-wrap: wrap;
    }
    .section h2 {
      margin: 0 0 8px;
      font-size: 27px;
      letter-spacing: -0.03em;
    }
    .section p {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.6;
      max-width: 880px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }
    .field {
      display: grid;
      gap: 8px;
    }
    .field label {
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.02em;
      color: var(--muted);
      text-transform: uppercase;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
      padding: 10px 14px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      background: rgba(255,255,255,0.68);
    }
    .actions {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .radio-group {
      display: grid;
      gap: 12px;
      margin: 16px 0 18px;
    }
    .radio-card {
      display: grid;
      gap: 5px;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.82);
      box-shadow: 0 10px 26px rgba(15, 23, 40, 0.05);
    }
    .radio-card label {
      display: flex;
      gap: 12px;
      align-items: flex-start;
      cursor: pointer;
    }
    .radio-card strong {
      display: block;
      font-size: 16px;
      letter-spacing: -0.02em;
    }
    .radio-card span {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }
    .controls-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: end;
    }
    .doc-toolbar {
      display: grid;
      grid-template-columns: 1.2fr 160px auto auto;
      gap: 12px;
      margin-bottom: 14px;
    }
    .doc-list {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.94);
      max-height: 360px;
      overflow: auto;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
    }
    .doc-row {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 14px;
      padding: 14px 16px;
      border-top: 1px solid rgba(215,204,187,0.6);
      align-items: start;
    }
    .doc-row:first-child {
      border-top: 0;
    }
    .doc-row.active {
      background: rgba(11, 107, 203, 0.08);
    }
    .doc-main {
      display: grid;
      gap: 5px;
    }
    .doc-title {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }
    .doc-meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .doc-empty {
      padding: 22px 16px;
      color: var(--muted);
      font-size: 14px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(11, 107, 203, 0.08);
      color: #0b5db1;
      border: 1px solid rgba(11, 107, 203, 0.14);
      font-size: 12px;
      font-weight: 700;
    }
    .selection-info {
      margin-top: 12px;
      color: var(--muted);
      font-size: 14px;
    }
    .config-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin: 14px 0;
    }
    .wide {
      grid-column: 1 / -1;
    }
    .prompt-box {
      min-height: 300px;
      font-family: "SFMono-Regular", "Consolas", monospace;
      line-height: 1.45;
    }
    .summary-bar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .detail-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 16px;
    }
    .detail-card {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.94);
      padding: 16px;
      display: grid;
      gap: 10px;
      box-shadow: 0 16px 32px rgba(15, 23, 40, 0.06);
    }
    .detail-card h3 {
      margin: 0;
      font-size: 19px;
      letter-spacing: -0.02em;
    }
    .detail-sub {
      color: var(--muted);
      font-size: 13px;
    }
    .meta-table {
      display: grid;
      gap: 8px;
    }
    .meta-row {
      display: grid;
      gap: 2px;
    }
    .meta-label {
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-weight: 700;
    }
    .ocr-box {
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
      line-height: 1.45;
      font-family: "SFMono-Regular", "Consolas", monospace;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(248,250,252,0.95);
      padding: 14px;
    }
    .secondary {
      background: linear-gradient(135deg, #475467, #667085);
      box-shadow: 0 14px 28px rgba(71, 84, 103, 0.22);
    }
    .logbox {
      margin-top: 14px;
      min-height: 120px;
      max-height: 320px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(248,250,252,0.95);
      padding: 12px 14px;
      white-space: pre-wrap;
      line-height: 1.45;
      font-family: "SFMono-Regular", "Consolas", monospace;
    }
    .statusline {
      margin-top: 12px;
      font-size: 14px;
      color: var(--muted);
    }
    .warn {
      color: #b54708;
    }
    input[type="checkbox"], input[type="radio"] {
      width: 18px;
      height: 18px;
      accent-color: var(--accent);
      margin-top: 1px;
      box-shadow: none;
    }
    @media (min-width: 1100px) {
      .wrap {
        padding-top: 34px;
      }
      .card {
        display: grid;
        grid-template-columns: 1.1fr 1.5fr;
      }
      .hero,
      .workspace,
      .controls,
      .section,
      .composer {
        grid-column: 1 / -1;
      }
      .chat {
        border-top: 1px solid var(--line);
      }
    }
    @media (max-width: 760px) {
      .app-shell {
        grid-template-columns: 1fr;
      }
      .sidebar {
        position: static;
      }
      .sidebar[data-layout="top"] {
        display: none;
      }
      .hero-grid,
      .hero-metrics,
      .grid {
        grid-template-columns: 1fr;
      }
      .doc-toolbar,
      .controls-row,
      .config-grid,
      .detail-grid {
        grid-template-columns: 1fr;
      }
      .hero {
        padding: 24px 20px 20px;
      }
      .wrap {
        padding: 20px 16px 40px;
      }
      .controls,
      .section,
      .composer,
      .chat {
        padding-left: 20px;
        padding-right: 20px;
      }
    }
    body.layout-top .app-shell {
      grid-template-columns: 1fr;
    }
    body.layout-top .sidebar {
      position: static;
      order: 1;
    }
    body.layout-top .workspace {
      order: 2;
    }
    body.layout-top .nav-card {
      padding: 10px;
    }
    body.layout-top .nav-list {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
    body.layout-top .nav-btn small {
      display: none;
    }
    @keyframes rise {
      from { transform: translateY(6px); opacity: 0; }
      to { transform: translateY(0); opacity: 1; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="app-shell">
      <aside class="sidebar">
        <div class="nav-card">
          <div class="nav-list">
            <button class="nav-btn active" data-view-target="review-view">
              Review Workspace
              <small>Dokumente suchen, Vorschau erzeugen, KI-Vorschlag uebernehmen.</small>
            </button>
            <button class="nav-btn" data-view-target="control-view">
              Steuerung
              <small>Modelle, Prompt, OCR-Kontext, Timeout und Fallback verwalten.</small>
            </button>
            <button class="nav-btn" data-view-target="chat-view">
              Chat
              <small>Direkte Modelltests im Browser ohne Paperless-Lauf.</small>
            </button>
          </div>
        </div>
      </aside>
      <div class="workspace">
        <div class="card">
          <div class="hero">
            <div class="hero-grid">
              <div>
                <div class="eyebrow">Paperless AI Console</div>
                <h1>Lokale KI-Steuerung für Ollama und Paperless</h1>
                <div class="sub">
                  Eine zentrale Oberflaeche fuer Modellwahl, Prompt-Steuerung, Dokument-Review
                  und Nachlaeufe. Chat und Paperless bleiben lokal auf diesem Host.
                </div>
              </div>
              <div class="hero-panel">
                <div class="hero-kicker">Arbeitsmodus</div>
                <div class="hero-metrics">
                  <div class="metric">
                    <strong>Lokal</strong>
                    <span>Ollama und Paperless laufen auf deiner Infrastruktur.</span>
                  </div>
                  <div class="metric">
                    <strong>Review</strong>
                    <span>Einzeldokumente vor dem Schreiben per Vorschau pruefen.</span>
                  </div>
                  <div class="metric">
                    <strong>Backfill</strong>
                    <span>Bestehende Dokumente gezielt oder gesammelt nachziehen.</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="hero-actions">
              <div class="layout-toggle">
                <button id="layout-sidebar" class="toggle-btn active" type="button">Sidebar</button>
                <button id="layout-top" class="toggle-btn" type="button">Top Tabs</button>
              </div>
            </div>
          </div>
          <div class="workspace">
            <section id="review-view" class="view active">
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Paperless KI-Nachlauf</h2>
                    <p>
                      Starte den KI-Nachlauf entweder fuer sinnvolle Standardmengen oder waehle
                      gezielt Dokumente aus, die erneut geprueft werden sollen.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Batch</span>
                    <span class="pill">Einzeldokument</span>
                    <span class="pill">Review vor Apply</span>
                  </div>
                </div>
                <div class="radio-group">
                  <div class="radio-card">
                    <label>
                      <input type="radio" name="backfill-mode" value="missing" checked>
                      <div>
                        <strong>Nur Dokumente mit fehlenden Metadaten</strong>
                        <span>Standardmodus. Gut fuer den ersten Nachlauf.</span>
                      </div>
                    </label>
                  </div>
                  <div class="radio-card">
                    <label>
                      <input type="radio" name="backfill-mode" value="all">
                      <div>
                        <strong>Alle gefundenen Dokumente neu pruefen</strong>
                        <span>Auch Dokumente mit bereits gesetzten Tags, Typen oder Korrespondenzen.</span>
                      </div>
                    </label>
                  </div>
                  <div class="radio-card">
                    <label>
                      <input type="radio" name="backfill-mode" value="selected">
                      <div>
                        <strong>Nur ausgewaehlte Dokumente</strong>
                        <span>Geeignet fuer Korrekturen oder gezielte erneute KI-Pruefung.</span>
                      </div>
                    </label>
                  </div>
                </div>
                <div class="grid">
                  <div class="field">
                    <label for="backfill-limit">Limit</label>
                    <input id="backfill-limit" type="number" min="1" value="50">
                  </div>
                  <div class="field">
                    <label for="backfill-query">Paperless-Query</label>
                    <input id="backfill-query" type="text" placeholder="optional">
                  </div>
                  <div class="field">
                    <label for="backfill-from-id">Ab Dokument-ID</label>
                    <input id="backfill-from-id" type="number" min="1" placeholder="optional">
                  </div>
                </div>
                <div class="section" style="padding:16px 0 0;border-top:0;background:transparent;">
                  <h2 style="font-size:20px;">Dokumente auswaehlen</h2>
                  <p>
                    Suche in den vorhandenen Dokumenten und markiere genau die Eintraege,
                    die du erneut durch die KI laufen lassen willst.
                  </p>
                  <div class="doc-toolbar">
                    <input id="doc-search" type="text" placeholder="Suche nach Titel oder Dokument-ID">
                    <input id="doc-limit" type="number" min="1" max="200" value="40">
                    <button id="doc-refresh" class="secondary">Liste laden</button>
                    <button id="doc-clear-selection" class="secondary">Auswahl leeren</button>
                  </div>
                  <div id="doc-list" class="doc-list">
                    <div class="doc-empty">Dokumentliste wird geladen...</div>
                  </div>
                  <div id="doc-selection-info" class="selection-info">0 Dokumente ausgewaehlt.</div>
                  <div class="detail-grid">
                    <div class="detail-card">
                      <h3>Dokument-Details</h3>
                      <div class="detail-sub">Aktueller Stand in Paperless</div>
                      <div id="doc-detail-meta" class="meta-table">
                        <div class="doc-empty">Noch kein Dokument ausgewaehlt.</div>
                      </div>
                      <div class="actions">
                        <button id="doc-preview-single" class="secondary">Nur dieses Dokument Vorschau</button>
                        <button id="doc-run-single">Nur dieses Dokument neu pruefen</button>
                      </div>
                      <label class="check">
                        <input id="doc-preview-vision" type="checkbox">
                        Hybrid OCR + Vision fuer PDF-Seite 1 aktivieren
                      </label>
                      <div class="detail-sub">OCR erstellt den Entwurf, Vision prueft Briefkopf, Layout und schwer lesbare Stellen gezielt nach.</div>
                      <div id="doc-detail-status" class="statusline">Kein Einzel-Lauf gestartet.</div>
                    </div>
                    <div class="detail-card">
                      <h3>OCR-Vorschau</h3>
                      <div id="doc-detail-ocr" class="ocr-box">Noch kein Dokument ausgewaehlt.</div>
                    </div>
                    <div class="detail-card">
                      <h3>OCR-Struktur</h3>
                      <div class="detail-sub">Heuristisch erkannte Bereiche wie Briefkopf, Adressat, Datum, Betreff und Signatur ueber mehrere Seiten hinweg.</div>
                      <div id="doc-detail-ocr-structure" class="ocr-box">Noch keine OCR-Struktur erkannt.</div>
                    </div>
                    <div class="detail-card">
                      <h3>Vision-Lesefassung</h3>
                      <div class="detail-sub">Optional bereinigte Kurzfassung wichtiger sichtbarer Angaben. Der rohe OCR-Text bleibt unveraendert.</div>
                      <div id="doc-detail-vision-text" class="ocr-box">Noch keine Vision-Lesefassung vorhanden.</div>
                    </div>
                  </div>
                  <div class="detail-grid">
                    <div class="detail-card">
                      <h3>KI-Vorschlag</h3>
                      <div class="detail-sub">Wird erst nach der Vorschau erzeugt und noch nicht geschrieben.</div>
                      <div id="doc-proposal-meta" class="meta-table">
                        <div class="doc-empty">Noch kein KI-Vorschlag vorhanden.</div>
                      </div>
                      <div class="actions">
                        <button id="doc-apply-proposal">Vorschlag uebernehmen</button>
                        <button id="doc-discard-proposal" class="secondary">Vorschlag verwerfen</button>
                      </div>
                      <div id="doc-proposal-status" class="statusline">Kein Vorschlag geladen.</div>
                    </div>
                    <div class="detail-card">
                      <h3>Vorschlagsgrund</h3>
                      <div id="doc-proposal-reason" class="ocr-box">Noch kein KI-Vorschlag vorhanden.</div>
                    </div>
                  </div>
                </div>
                <div class="actions">
                  <button id="backfill-preview" class="secondary">Vorschau</button>
                  <button id="backfill-run">Backfill starten</button>
                </div>
                <div id="backfill-status" class="statusline">Noch kein Lauf gestartet.</div>
                <div id="backfill-log" class="logbox">Bereit.</div>
              </div>
            </section>
            <section id="control-view" class="view">
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Modellstrategie</h2>
                    <p>
                      Das Chat-Modell gilt sofort im Browser. Fuer Paperless kannst du ein Primärmodell
                      und optional ein Fallback-Modell festlegen, damit lange Dokumente nicht komplett
                      ohne Ergebnis enden.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Chat + Paperless</span>
                    <span class="pill">Fallback-faehig</span>
                  </div>
                </div>
                <div class="config-grid">
                  <div class="field">
                    <label for="paperless-model">Primärmodell</label>
                    <select id="paperless-model"></select>
                    <small>Dieses Modell nutzt der eigentliche Paperless-Import für neue Dokumente und Backfills.</small>
                  </div>
                  <div class="field">
                    <label for="paperless-fallback-model">Fallback-Modell</label>
                    <select id="paperless-fallback-model"></select>
                    <small>Optionales Ersatzmodell, wenn das Primärmodell scheitert oder zu lange braucht.</small>
                  </div>
                  <label class="check">
                    <input id="paperless-fallback-enabled" type="checkbox">
                    Fallback aktivieren
                    <small>Nur sinnvoll, wenn du bewusst ein kleineres Sicherheitsnetz neben dem Hauptmodell willst.</small>
                  </label>
                  <label class="check">
                    <input id="paperless-fallback-timeout-only" type="checkbox" checked>
                    Fallback nur bei Timeout
                    <small>Empfohlen. So springt das Fallback nicht bei jedem beliebigen Modellfehler an.</small>
                  </label>
                  <div class="field">
                    <label for="paperless-fallback-timeout">Fallback-Timeout in Sekunden</label>
                    <input id="paperless-fallback-timeout" type="number" min="30" step="30">
                    <small>Wie lange das Ersatzmodell maximal laufen darf, bevor auch dieser Versuch abgebrochen wird.</small>
                  </div>
                </div>
                <div class="actions">
                  <button id="save-paperless-model" class="secondary">Modellstrategie speichern</button>
                </div>
                <div id="paperless-model-status" class="statusline">Noch keine Modellstrategie gespeichert.</div>
              </div>
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Paperless KI-Konfiguration</h2>
                    <p>
                      Hier steuerst du die eigentlichen Regeln fuer die Paperless-KI: wie viel OCR-Text
                      beruecksichtigt wird, ab welcher Sicherheit Metadaten gesetzt werden und wie lange
                      ein Lauf auf das Modell warten darf.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">OCR-Kontext</span>
                    <span class="pill">Confidence</span>
                    <span class="pill">Timeout</span>
                  </div>
                </div>
                <div class="config-grid">
                  <div class="field">
                    <label for="cfg-content-chars">OCR-Zeichen</label>
                    <input id="cfg-content-chars" type="number" min="1000" step="1000">
                    <small>So viel OCR-Text geht in den normalen Paperless-Lauf. Mehr Text bringt mehr Kontext, kostet aber Zeit.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-min-confidence">Mindest-Confidence</label>
                    <input id="cfg-min-confidence" type="number" min="0" max="1" step="0.05">
                    <small>Unterhalb dieses Werts werden KI-Vorschläge im Auto-Lauf nicht automatisch übernommen.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-timeout">HTTP-Timeout in Sekunden</label>
                    <input id="cfg-timeout" type="number" min="30" step="30">
                    <small>Maximale Laufzeit für das aktive Paperless-Modell pro Dokument im Hintergrundbetrieb.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-tag-color">Standard-Tag-Farbe</label>
                    <input id="cfg-tag-color" type="text" placeholder="#4f6bed">
                    <small>Diese Farbe wird für neu von der KI angelegte Tags genutzt, wenn noch kein Tag vorhanden ist.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-tag-review-model">Tag-Review-Modell</label>
                    <select id="cfg-tag-review-model"></select>
                    <small>Nur fuer den zweiten Tag-Schritt. Hier darfst du ein staerkeres Modell nehmen, ohne den Hauptlauf zu veraendern.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-tag-review-timeout">Tag-Review-Timeout</label>
                    <input id="cfg-tag-review-timeout" type="number" min="30" step="30">
                    <small>Wie lange das Tag-Modell maximal laufen darf. Das betrifft nur die Tag-Endauswahl.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-review-min-confidence">Review-Tag unter Confidence</label>
                    <input id="cfg-review-min-confidence" type="number" min="0" max="1" step="0.05">
                    <small>Unterhalb dieses Werts markiert die Pipeline das Dokument zusaetzlich fuer Nachpruefung.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-review-tag-name">Review-Tag</label>
                    <input id="cfg-review-tag-name" type="text" placeholder="KI Nachpruefen">
                    <small>Dieses Tag markiert unsichere Faelle fuer spaetere manuelle oder teurere Zweitpruefung.</small>
                  </div>
                  <div class="field">
                    <label for="cfg-review-tag-color">Review-Tag-Farbe</label>
                    <input id="cfg-review-tag-color" type="text" placeholder="#7dd3fc">
                    <small>Eigene Farbe fuer Review-Tags. Hellblau ist als Standard sinnvoll, damit diese Faelle sofort sichtbar sind.</small>
                  </div>
                </div>
                <div class="field">
                  <label for="cfg-tag-allowlists">Erlaubte Tags je Familie (JSON)</label>
                  <textarea id="cfg-tag-allowlists" class="prompt-box" style="min-height:220px" placeholder='{"school":["Fehlzeiten","Schulpflicht","Attest"],"court":["Familienrecht","Pflegschaft"]}'></textarea>
                  <small>Nur generische Archiv-Tags eintragen. Keine persoenlichen Namen, Orte oder Einzelfall-Tags. Diese Liste bleibt lokal auf deinem System.</small>
                </div>
                <div class="field">
                  <label for="cfg-tag-rules">Regelbasierte Fallback-Tags je Familie (JSON)</label>
                  <textarea id="cfg-tag-rules" class="prompt-box" style="min-height:240px" placeholder='{"school":{"Fehlzeiten":["fehlzeit"],"Schulpflicht":["schulpflicht"],"Attest":["attest","ärzt"]}}'></textarea>
                  <small>Verstaendliche Pipeline-Regeln: Familie -> Tag -> Suchbegriffe. Diese Regeln greifen, wenn das Tag-Modell zu wenig oder nichts Brauchbares liefert.</small>
                </div>
                <div class="actions">
                  <button id="save-ai-config">KI-Konfiguration speichern</button>
                  <button id="reload-ai-config" class="secondary">Neu laden</button>
                </div>
                <div id="ai-config-status" class="statusline">Konfiguration noch nicht geladen.</div>
              </div>
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Preview & Vision</h2>
                    <p>
                      Diese Einstellungen betreffen nur die Vorschau in Port 3000. Damit kannst du die
                      Review-Ansicht schneller machen, ohne den eigentlichen Paperless-Import zu veraendern.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Vorschau</span>
                    <span class="pill">Vision</span>
                    <span class="pill">Tagging</span>
                  </div>
                </div>
                <div class="config-grid">
                  <div class="field">
                    <label for="preview-ocr-model">Vorschau-OCR-Modell</label>
                    <select id="preview-ocr-model"></select>
                    <small>Dieses Modell erzeugt den ersten Vorschlag in der Review-Ansicht. Kleiner ist schneller, groesser meist genauer.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-model">Vision-Modell</label>
                    <select id="preview-vision-model"></select>
                    <small>Dieses Modell prueft bei PDFs zusaetzlich das Seitenbild. Es aendert nichts am normalen Paperless-Import.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-content-chars">Vision OCR-Zeichen</label>
                    <input id="preview-vision-content-chars" type="number" min="200" step="100">
                    <small>So viel OCR-Text bekommt der Vision-Schritt zusaetzlich zum Bild. Kleinere Werte sind meist deutlich schneller.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-timeout">Vision-Timeout in Sekunden</label>
                    <input id="preview-vision-timeout" type="number" min="10" step="10">
                    <small>Nach dieser Zeit wird der Vision-Schritt beendet. Der OCR-Vorschlag bleibt trotzdem erhalten.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-max-pages">Vision nur bis Seitenzahl</label>
                    <input id="preview-vision-max-pages" type="number" min="1" step="1">
                    <small>Nur PDFs bis zu dieser Seitenzahl starten automatisch den Vision-Review. Laengere Dokumente bleiben bei OCR-only.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-tag-name">Vision-Zusatz-Tag</label>
                    <input id="preview-vision-tag-name" type="text" placeholder="KI Vision">
                    <small>Dieser Zusatz-Tag wird beim Uebernehmen gesetzt, wenn der Vision-Schritt erfolgreich in das Ergebnis eingeflossen ist.</small>
                  </div>
                  <div class="field">
                    <label for="preview-vision-tag-color">Vision-Tag-Farbe</label>
                    <input id="preview-vision-tag-color" type="text" placeholder="#d97706">
                    <small>Hex-Farbe fuer den Vision-Zusatz-Tag, damit Vision-unterstuetzte Dokumente in Paperless sofort erkennbar sind.</small>
                  </div>
                </div>
                <div class="actions">
                  <button id="save-preview-config">Preview & Vision speichern</button>
                  <button id="reload-preview-config" class="secondary">Neu laden</button>
                </div>
                <div id="preview-config-status" class="statusline">Preview-Konfiguration noch nicht geladen.</div>
              </div>
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Prompt</h2>
                    <p>
                      Dieser Prompt bestimmt, wie Titel, Korrespondenz, Dokumenttyp und Tags vorgeschlagen
                      werden. Aenderungen wirken auf die naechsten Laeufe.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Live editierbar</span>
                  </div>
                </div>
                <textarea id="prompt-editor" class="prompt-box" placeholder="Prompt wird geladen..."></textarea>
                <div class="actions">
                  <button id="save-prompt">Prompt speichern</button>
                  <button id="reload-prompt" class="secondary">Prompt neu laden</button>
                </div>
                <div id="prompt-status" class="statusline">Prompt noch nicht geladen.</div>
              </div>
            </section>
            <section id="chat-view" class="view">
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
            </section>
          </div>
        </div>
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
    const paperlessModelEl = document.getElementById('paperless-model');
    const paperlessFallbackModelEl = document.getElementById('paperless-fallback-model');
    const paperlessFallbackEnabledEl = document.getElementById('paperless-fallback-enabled');
    const paperlessFallbackTimeoutOnlyEl = document.getElementById('paperless-fallback-timeout-only');
    const paperlessFallbackTimeoutEl = document.getElementById('paperless-fallback-timeout');
    const savePaperlessModelBtn = document.getElementById('save-paperless-model');
    const paperlessModelStatusEl = document.getElementById('paperless-model-status');
    const cfgContentCharsEl = document.getElementById('cfg-content-chars');
    const cfgMinConfidenceEl = document.getElementById('cfg-min-confidence');
    const cfgTimeoutEl = document.getElementById('cfg-timeout');
    const cfgTagColorEl = document.getElementById('cfg-tag-color');
    const cfgTagReviewModelEl = document.getElementById('cfg-tag-review-model');
    const cfgTagReviewTimeoutEl = document.getElementById('cfg-tag-review-timeout');
    const cfgReviewMinConfidenceEl = document.getElementById('cfg-review-min-confidence');
    const cfgReviewTagNameEl = document.getElementById('cfg-review-tag-name');
    const cfgReviewTagColorEl = document.getElementById('cfg-review-tag-color');
    const cfgTagAllowlistsEl = document.getElementById('cfg-tag-allowlists');
    const cfgTagRulesEl = document.getElementById('cfg-tag-rules');
    const saveAiConfigBtn = document.getElementById('save-ai-config');
    const reloadAiConfigBtn = document.getElementById('reload-ai-config');
    const aiConfigStatusEl = document.getElementById('ai-config-status');
    const previewOcrModelEl = document.getElementById('preview-ocr-model');
    const previewVisionModelEl = document.getElementById('preview-vision-model');
    const previewVisionContentCharsEl = document.getElementById('preview-vision-content-chars');
    const previewVisionTimeoutEl = document.getElementById('preview-vision-timeout');
    const previewVisionMaxPagesEl = document.getElementById('preview-vision-max-pages');
    const previewVisionTagNameEl = document.getElementById('preview-vision-tag-name');
    const previewVisionTagColorEl = document.getElementById('preview-vision-tag-color');
    const savePreviewConfigBtn = document.getElementById('save-preview-config');
    const reloadPreviewConfigBtn = document.getElementById('reload-preview-config');
    const previewConfigStatusEl = document.getElementById('preview-config-status');
    const promptEditorEl = document.getElementById('prompt-editor');
    const savePromptBtn = document.getElementById('save-prompt');
    const reloadPromptBtn = document.getElementById('reload-prompt');
    const promptStatusEl = document.getElementById('prompt-status');
    const backfillLimitEl = document.getElementById('backfill-limit');
    const backfillQueryEl = document.getElementById('backfill-query');
    const backfillFromIdEl = document.getElementById('backfill-from-id');
    const backfillPreviewBtn = document.getElementById('backfill-preview');
    const backfillRunBtn = document.getElementById('backfill-run');
    const backfillStatusEl = document.getElementById('backfill-status');
    const backfillLogEl = document.getElementById('backfill-log');
    const docSearchEl = document.getElementById('doc-search');
    const docLimitEl = document.getElementById('doc-limit');
    const docRefreshBtn = document.getElementById('doc-refresh');
    const docClearSelectionBtn = document.getElementById('doc-clear-selection');
    const docListEl = document.getElementById('doc-list');
    const docSelectionInfoEl = document.getElementById('doc-selection-info');
    const docDetailMetaEl = document.getElementById('doc-detail-meta');
    const docDetailOcrEl = document.getElementById('doc-detail-ocr');
    const docDetailOcrStructureEl = document.getElementById('doc-detail-ocr-structure');
    const docDetailVisionTextEl = document.getElementById('doc-detail-vision-text');
    const docDetailStatusEl = document.getElementById('doc-detail-status');
    const docPreviewSingleBtn = document.getElementById('doc-preview-single');
    const docPreviewVisionEl = document.getElementById('doc-preview-vision');
    const docRunSingleBtn = document.getElementById('doc-run-single');
    const docProposalMetaEl = document.getElementById('doc-proposal-meta');
    const docProposalReasonEl = document.getElementById('doc-proposal-reason');
    const docProposalStatusEl = document.getElementById('doc-proposal-status');
    const docApplyProposalBtn = document.getElementById('doc-apply-proposal');
    const docDiscardProposalBtn = document.getElementById('doc-discard-proposal');
    const navButtons = Array.from(document.querySelectorAll('[data-view-target]'));
    const views = Array.from(document.querySelectorAll('.view'));
    const layoutSidebarBtn = document.getElementById('layout-sidebar');
    const layoutTopBtn = document.getElementById('layout-top');
    const backfillModeEls = Array.from(document.querySelectorAll('input[name="backfill-mode"]'));
    let messages = [];
    let selectedDocumentIds = new Set();
    let documentRows = [];
    let activeDocumentId = null;
    let activeProposal = null;
    let activePreviewJobId = null;
    let availableModelNames = [];

    function addMessage(role, content) {
      messages.push({ role, content });
      render();
    }

    function setActiveView(viewId) {
      views.forEach(view => view.classList.toggle('active', view.id === viewId));
      navButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.viewTarget === viewId));
    }

    function setLayoutMode(mode) {
      const top = mode === 'top';
      document.body.classList.toggle('layout-top', top);
      layoutSidebarBtn.classList.toggle('active', !top);
      layoutTopBtn.classList.toggle('active', top);
      try {
        localStorage.setItem('paperless-ui-layout', mode);
      } catch (_) {}
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
      paperlessModelEl.innerHTML = '';
      paperlessFallbackModelEl.innerHTML = '';
      previewOcrModelEl.innerHTML = '';
      previewVisionModelEl.innerHTML = '';
      cfgTagReviewModelEl.innerHTML = '';
      availableModelNames = [];
      for (const model of data.models || []) {
        availableModelNames.push(model.name);
        const option = document.createElement('option');
        option.value = model.name;
        option.textContent = model.name;
        modelEl.appendChild(option);
        const paperlessOption = document.createElement('option');
        paperlessOption.value = model.name;
        paperlessOption.textContent = model.name;
        paperlessModelEl.appendChild(paperlessOption);
        const fallbackOption = document.createElement('option');
        fallbackOption.value = model.name;
        fallbackOption.textContent = model.name;
        paperlessFallbackModelEl.appendChild(fallbackOption);
        const previewOcrOption = document.createElement('option');
        previewOcrOption.value = model.name;
        previewOcrOption.textContent = model.name;
        previewOcrModelEl.appendChild(previewOcrOption);
        const previewVisionOption = document.createElement('option');
        previewVisionOption.value = model.name;
        previewVisionOption.textContent = model.name;
        previewVisionModelEl.appendChild(previewVisionOption);
        const tagReviewOption = document.createElement('option');
        tagReviewOption.value = model.name;
        tagReviewOption.textContent = model.name;
        cfgTagReviewModelEl.appendChild(tagReviewOption);
      }
      if (data.paperless_model) {
        paperlessModelEl.value = data.paperless_model;
      }
      if (data.fallback_model) {
        paperlessFallbackModelEl.value = data.fallback_model;
      }
      if (data.chat_model) {
        modelEl.value = data.chat_model;
      }
      loadPreviewConfig();
    }

    function getBackfillMode() {
      const active = backfillModeEls.find(el => el.checked);
      return active ? active.value : 'missing';
    }

    function renderSelectionInfo() {
      const count = selectedDocumentIds.size;
      docSelectionInfoEl.textContent = `${count} Dokumente ausgewaehlt.`;
    }

    function getSelectedDocumentIdForSingleActions() {
      if (activeDocumentId) return activeDocumentId;
      if (selectedDocumentIds.size === 1) {
        return Array.from(selectedDocumentIds)[0];
      }
      return null;
    }

    function formatValue(value) {
      if (value === null || value === undefined || value === '') return '-';
      if (Array.isArray(value)) return value.length ? value.join(', ') : '-';
      return String(value);
    }

    function syncFallbackUi() {
      const enabled = paperlessFallbackEnabledEl.checked;
      paperlessFallbackModelEl.disabled = !enabled;
      paperlessFallbackTimeoutOnlyEl.disabled = !enabled;
      paperlessFallbackTimeoutEl.disabled = !enabled;
    }

    function metadataPills(doc) {
      const missing = [];
      if (!doc.correspondent) missing.push('Korrespondenz fehlt');
      if (!doc.document_type) missing.push('Dokumenttyp fehlt');
      if (!doc.tags || !doc.tags.length) missing.push('Tags fehlen');
      if (!missing.length) return '<span class="pill">Metadaten vorhanden</span>';
      return missing.map(item => `<span class="pill">${item}</span>`).join(' ');
    }

    function renderDocumentList() {
      if (!documentRows.length) {
        docListEl.innerHTML = '<div class="doc-empty">Keine Dokumente gefunden.</div>';
        renderSelectionInfo();
        return;
      }
      docListEl.innerHTML = documentRows.map(doc => `
        <label class="doc-row ${activeDocumentId === doc.id ? 'active' : ''}" data-doc-row="${doc.id}">
          <input type="checkbox" data-doc-id="${doc.id}" ${selectedDocumentIds.has(doc.id) ? 'checked' : ''}>
          <div class="doc-main">
            <div class="doc-title">#${doc.id} ${doc.title || '(ohne Titel)'}</div>
            <div class="doc-meta">${doc.created_date || '-'} · ${doc.original_file_name || '-'} · Seiten: ${doc.page_count || '-'}</div>
            <div class="doc-meta">${metadataPills(doc)}</div>
          </div>
          <div class="doc-meta">${doc.correspondent_name || 'keine Korrespondenz'}</div>
        </label>
      `).join('');
      docListEl.querySelectorAll('input[type="checkbox"]').forEach(box => {
        box.addEventListener('change', async () => {
          const docId = Number(box.dataset.docId);
          if (box.checked) {
            selectedDocumentIds.add(docId);
            if (!activeDocumentId || selectedDocumentIds.size === 1) {
              await loadDocumentDetail(docId);
            }
          } else {
            selectedDocumentIds.delete(docId);
            if (activeDocumentId === docId && selectedDocumentIds.size === 1) {
              await loadDocumentDetail(Array.from(selectedDocumentIds)[0]);
            }
          }
          renderSelectionInfo();
        });
      });
      docListEl.querySelectorAll('[data-doc-row]').forEach(row => {
        row.addEventListener('click', (event) => {
          if (event.target.closest('input[type="checkbox"]')) return;
          const docId = Number(row.dataset.docRow);
          loadDocumentDetail(docId);
        });
      });
      renderSelectionInfo();
    }

    function renderDocumentDetail(doc) {
      activeDocumentId = doc.id;
      activeProposal = null;
      activePreviewJobId = null;
      const tags = (doc.tags || []).map(tag => typeof tag === 'object' ? tag.name : tag);
      const currentCorrespondent = doc.correspondent_name || (doc.correspondent && doc.correspondent.name) || '';
      const currentDocumentType = doc.document_type_name || (doc.document_type && doc.document_type.name) || '';
      docDetailMetaEl.innerHTML = `
        <div class="meta-row"><div class="meta-label">Dokument</div><div>#${doc.id} ${formatValue(doc.title)}</div></div>
        <div class="meta-row"><div class="meta-label">Datei</div><div>${formatValue(doc.original_file_name)}</div></div>
        <div class="meta-row"><div class="meta-label">Datum</div><div>${formatValue(doc.created_date)}</div></div>
        <div class="meta-row"><div class="meta-label">Korrespondenz</div><div>${formatValue(currentCorrespondent)}</div></div>
        <div class="meta-row"><div class="meta-label">Dokumenttyp</div><div>${formatValue(currentDocumentType)}</div></div>
        <div class="meta-row"><div class="meta-label">Tags</div><div>${formatValue(tags)}</div></div>
      `;
      docDetailOcrEl.textContent = doc.content || 'Kein OCR-Inhalt vorhanden.';
      docDetailOcrStructureEl.textContent = 'Noch keine OCR-Struktur erkannt.';
      docDetailVisionTextEl.textContent = 'Noch keine Vision-Lesefassung vorhanden.';
      renderProposal(null);
      renderDocumentList();
    }

    function getHybridStatusText(proposal) {
      if (!proposal) return 'Kein Vorschlag geladen.';
      if (proposal._hybrid_pending) return 'OCR-Vorschlag geladen. Vision-Review laeuft im Hintergrund...';
      if (proposal._vision_used) return `Hybrid abgeschlossen. Vision hat ${proposal._vision_pages || 0} Seite(n) geprueft.`;
      if (proposal._vision_error) return `OCR-Vorschlag geladen. Vision-Review fehlgeschlagen: ${proposal._vision_error}`;
      if (proposal._vision_requested) return 'OCR-Vorschlag geladen. Vision wurde fuer dieses Dokument uebersprungen.';
      return 'OCR-Vorschlag geladen.';
    }

    function renderProposal(proposal) {
      activeProposal = proposal;
      if (!proposal) {
        docProposalMetaEl.innerHTML = '<div class="doc-empty">Noch kein KI-Vorschlag vorhanden.</div>';
        docProposalReasonEl.textContent = 'Noch kein KI-Vorschlag vorhanden.';
        docDetailOcrStructureEl.textContent = 'Noch keine OCR-Struktur erkannt.';
        docDetailVisionTextEl.textContent = 'Noch keine Vision-Lesefassung vorhanden.';
        docApplyProposalBtn.disabled = true;
        docDiscardProposalBtn.disabled = true;
        docProposalStatusEl.textContent = 'Kein Vorschlag geladen.';
        docProposalStatusEl.className = 'statusline';
        return;
      }
      docProposalMetaEl.innerHTML = `
        <div class="meta-row"><div class="meta-label">Titel</div><div>${formatValue(proposal.title)}</div></div>
        <div class="meta-row"><div class="meta-label">Korrespondenz</div><div>${formatValue(proposal.correspondent)}</div></div>
        <div class="meta-row"><div class="meta-label">Dokumenttyp</div><div>${formatValue(proposal.document_type)}</div></div>
        <div class="meta-row"><div class="meta-label">Tags</div><div>${formatValue(proposal.tags)}</div></div>
        <div class="meta-row"><div class="meta-label">Confidence</div><div>${formatValue(proposal.confidence)}</div></div>
        <div class="meta-row"><div class="meta-label">Modell</div><div>${formatValue(proposal._model)}</div></div>
        <div class="meta-row"><div class="meta-label">Fallback</div><div>${proposal._fallback_used ? `ja, von ${formatValue(proposal._fallback_from)}` : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Hybrid</div><div>${proposal._hybrid_used ? 'ja' : proposal._hybrid_pending ? 'laeuft' : proposal._vision_requested ? 'angefragt' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">OCR-Modell</div><div>${formatValue(proposal._ocr_model || proposal._model)}</div></div>
        <div class="meta-row"><div class="meta-label">Vision-Modell</div><div>${proposal._vision_used ? formatValue(proposal._vision_model) : '-'}</div></div>
        <div class="meta-row"><div class="meta-label">Vision</div><div>${proposal._vision_used ? `ja, ${proposal._vision_pages || 0} Seite(n)` : proposal._hybrid_pending ? 'laeuft' : proposal._vision_requested ? 'angefragt' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Review</div><div>${proposal._review_needed ? 'ja' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Review-Gruende</div><div>${formatValue(proposal._review_reasons)}</div></div>
      `;
      docProposalReasonEl.textContent = proposal.reason || '-';
      if (proposal._vision_error) {
        docProposalReasonEl.textContent += `\n\nVision-Hinweis: ${proposal._vision_error}`;
      }
      docDetailOcrStructureEl.textContent = proposal._ocr_structure_summary || 'Noch keine OCR-Struktur erkannt.';
      docDetailVisionTextEl.textContent = proposal._vision_refined_excerpt || 'Noch keine Vision-Lesefassung vorhanden.';
      docApplyProposalBtn.disabled = false;
      docDiscardProposalBtn.disabled = false;
      docProposalStatusEl.textContent = getHybridStatusText(proposal);
      docProposalStatusEl.className = proposal._vision_error ? 'statusline warn' : 'statusline';
    }

    async function pollPreviewJob(jobId) {
      activePreviewJobId = jobId;
      while (activePreviewJobId === jobId) {
        await new Promise(resolve => window.setTimeout(resolve, 4000));
        if (activePreviewJobId !== jobId) return;
        try {
          const res = await fetch(`/api/paperless/preview-jobs/${jobId}`);
          const data = await res.json();
          if (!res.ok) throw new Error(data.error || 'Fehler');
          if (data.status === 'done' && data.proposal) {
            renderProposal(data.proposal);
            backfillLogEl.textContent = JSON.stringify(data.proposal || {}, null, 2);
            docDetailStatusEl.textContent = `Hybrid-Vorschau fuer #${activeDocumentId} abgeschlossen.`;
            activePreviewJobId = null;
            return;
          }
          if (data.status === 'error') {
            if (activeProposal) {
              activeProposal._vision_error = data.error || 'Vision-Review fehlgeschlagen';
              activeProposal._hybrid_pending = false;
              renderProposal(activeProposal);
            }
            docDetailStatusEl.textContent = `Hybrid-Vorschau fuer #${activeDocumentId} beendet mit Fehler.`;
            docDetailStatusEl.className = 'statusline warn';
            activePreviewJobId = null;
            return;
          }
        } catch (err) {
          docProposalStatusEl.textContent = `Vision-Polling Fehler: ${err.message}`;
          docProposalStatusEl.className = 'statusline warn';
          activePreviewJobId = null;
          return;
        }
      }
    }

    async function loadDocumentDetail(docId) {
      docDetailStatusEl.textContent = `Dokument #${docId} wird geladen...`;
      docDetailStatusEl.className = 'statusline';
      try {
        const res = await fetch(`/api/paperless/document/${docId}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        renderDocumentDetail(data.document);
        docDetailStatusEl.textContent = `Dokument #${docId} geladen.`;
      } catch (err) {
        docDetailStatusEl.textContent = `Fehler: ${err.message}`;
        docDetailStatusEl.className = 'statusline warn';
      }
    }

    async function runSingleDocument(dryRun) {
      const documentId = getSelectedDocumentIdForSingleActions();
      if (!documentId) {
        docDetailStatusEl.textContent = selectedDocumentIds.size > 1
          ? 'Mehrere Dokumente markiert. Bitte ein Detaildokument oeffnen oder nur eines markieren.'
          : 'Kein Dokument ausgewaehlt.';
        docDetailStatusEl.className = 'statusline warn';
        return;
      }
      if (activeDocumentId !== documentId) {
        await loadDocumentDetail(documentId);
      }
      docPreviewSingleBtn.disabled = true;
      docRunSingleBtn.disabled = true;
      docDetailStatusEl.textContent = dryRun ? `Vorschau fuer #${documentId} laeuft...` : `Einzellauf fuer #${documentId} laeuft...`;
      docDetailStatusEl.className = 'statusline';
      try {
        const url = dryRun ? `/api/paperless/document/${documentId}/preview` : '/api/paperless/backfill';
        const payload = dryRun ? {
          use_vision: docPreviewVisionEl.checked
        } : {
          dry_run: false,
          document_ids: [documentId],
          mode: 'selected'
        };
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        if (dryRun) {
          renderProposal(data.proposal || null);
          backfillLogEl.textContent = JSON.stringify(data.proposal || {}, null, 2);
          if (data.preview_job && data.preview_job.id) {
            docDetailStatusEl.textContent = `OCR-Vorschau fuer #${documentId} abgeschlossen. Vision-Review laeuft...`;
            pollPreviewJob(data.preview_job.id);
          } else {
            docDetailStatusEl.textContent = `Vorschau fuer #${documentId} abgeschlossen.`;
          }
        } else {
          backfillLogEl.textContent = data.output || 'Keine Ausgabe';
          docDetailStatusEl.textContent = `Einzellauf fuer #${documentId} abgeschlossen.`;
          await loadDocumentDetail(documentId);
          await loadDocuments();
        }
      } catch (err) {
        docDetailStatusEl.textContent = `Fehler: ${err.message}`;
        docDetailStatusEl.className = 'statusline warn';
      } finally {
        docPreviewSingleBtn.disabled = false;
        docRunSingleBtn.disabled = false;
      }
    }

    async function applyProposal() {
      if (!activeDocumentId || !activeProposal) {
        docProposalStatusEl.textContent = 'Kein Vorschlag zum Uebernehmen vorhanden.';
        docProposalStatusEl.className = 'statusline warn';
        return;
      }
      docApplyProposalBtn.disabled = true;
      docDiscardProposalBtn.disabled = true;
      docProposalStatusEl.textContent = 'Vorschlag wird uebernommen...';
      docProposalStatusEl.className = 'statusline';
      try {
        const res = await fetch(`/api/paperless/document/${activeDocumentId}/apply`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ proposal: activeProposal })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        docProposalStatusEl.textContent = 'Vorschlag uebernommen.';
        await loadDocumentDetail(activeDocumentId);
        await loadDocuments();
      } catch (err) {
        docProposalStatusEl.textContent = `Fehler: ${err.message}`;
        docProposalStatusEl.className = 'statusline warn';
      } finally {
        docApplyProposalBtn.disabled = false;
        docDiscardProposalBtn.disabled = false;
      }
    }

    function discardProposal() {
      renderProposal(null);
      docProposalStatusEl.textContent = 'Vorschlag verworfen.';
    }

    async function loadDocuments() {
      docRefreshBtn.disabled = true;
      docListEl.innerHTML = '<div class="doc-empty">Dokumentliste wird geladen...</div>';
      try {
        const params = new URLSearchParams();
        const query = docSearchEl.value.trim();
        const limit = Number(docLimitEl.value || 0);
        if (query) params.set('query', query);
        if (limit > 0) params.set('limit', String(limit));
        const res = await fetch(`/api/paperless/documents?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        documentRows = data.documents || [];
        renderDocumentList();
      } catch (err) {
        docListEl.innerHTML = `<div class="doc-empty">Fehler: ${err.message}</div>`;
      } finally {
        docRefreshBtn.disabled = false;
      }
    }

    async function savePaperlessModel() {
      const model = paperlessModelEl.value;
      if (!model) return;
      savePaperlessModelBtn.disabled = true;
      paperlessModelStatusEl.textContent = 'Modellstrategie wird gespeichert...';
      paperlessModelStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            primary_model: model,
            fallback_enabled: paperlessFallbackEnabledEl.checked ? 'true' : 'false',
            fallback_model: paperlessFallbackModelEl.value,
            fallback_timeout_only: paperlessFallbackTimeoutOnlyEl.checked ? 'true' : 'false',
            fallback_http_timeout_seconds: paperlessFallbackTimeoutEl.value.trim()
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        paperlessModelStatusEl.textContent = `Aktiv: ${model}${paperlessFallbackEnabledEl.checked ? ` mit Fallback ${paperlessFallbackModelEl.value}` : ''}`;
      } catch (err) {
        paperlessModelStatusEl.textContent = `Fehler: ${err.message}`;
        paperlessModelStatusEl.className = 'statusline warn';
      } finally {
        savePaperlessModelBtn.disabled = false;
      }
    }

    async function loadAiConfig() {
      aiConfigStatusEl.textContent = 'Konfiguration wird geladen...';
      aiConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/config');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        cfgContentCharsEl.value = data.content_chars || '';
        cfgMinConfidenceEl.value = data.min_confidence || '';
        cfgTimeoutEl.value = data.http_timeout_seconds || '';
        cfgTagColorEl.value = data.default_tag_color || '';
        if (data.tag_review_model && availableModelNames.includes(data.tag_review_model)) {
          cfgTagReviewModelEl.value = data.tag_review_model;
        }
        cfgTagReviewTimeoutEl.value = data.tag_review_timeout_seconds || '';
        cfgReviewMinConfidenceEl.value = data.review_min_confidence || '';
        cfgReviewTagNameEl.value = data.review_tag_name || '';
        cfgReviewTagColorEl.value = data.review_tag_color || '';
        cfgTagAllowlistsEl.value = data.tag_allowlists_json || '';
        cfgTagRulesEl.value = data.tag_rules_json || '';
        if (data.model) {
          paperlessModelEl.value = data.model;
        }
        if (data.fallback_model) {
          paperlessFallbackModelEl.value = data.fallback_model;
        }
        paperlessFallbackEnabledEl.checked = String(data.fallback_enabled || '').toLowerCase() === 'true';
        paperlessFallbackTimeoutOnlyEl.checked = String(data.fallback_timeout_only || '').toLowerCase() !== 'false';
        paperlessFallbackTimeoutEl.value = data.fallback_http_timeout_seconds || data.http_timeout_seconds || '';
        aiConfigStatusEl.textContent = 'Konfiguration geladen.';
      } catch (err) {
        aiConfigStatusEl.textContent = `Fehler: ${err.message}`;
        aiConfigStatusEl.className = 'statusline warn';
      } finally {
        syncFallbackUi();
      }
    }

    async function saveAiConfig() {
      saveAiConfigBtn.disabled = true;
      aiConfigStatusEl.textContent = 'Konfiguration wird gespeichert...';
      aiConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            content_chars: cfgContentCharsEl.value.trim(),
            min_confidence: cfgMinConfidenceEl.value.trim(),
            http_timeout_seconds: cfgTimeoutEl.value.trim(),
            default_tag_color: cfgTagColorEl.value.trim(),
            tag_review_model: cfgTagReviewModelEl.value,
            tag_review_timeout_seconds: cfgTagReviewTimeoutEl.value.trim(),
            review_min_confidence: cfgReviewMinConfidenceEl.value.trim(),
            review_tag_name: cfgReviewTagNameEl.value.trim(),
            review_tag_color: cfgReviewTagColorEl.value.trim(),
            tag_allowlists_json: cfgTagAllowlistsEl.value,
            tag_rules_json: cfgTagRulesEl.value
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        aiConfigStatusEl.textContent = 'Konfiguration gespeichert und Worker neu geladen.';
      } catch (err) {
        aiConfigStatusEl.textContent = `Fehler: ${err.message}`;
        aiConfigStatusEl.className = 'statusline warn';
      } finally {
        saveAiConfigBtn.disabled = false;
      }
    }

    async function loadPreviewConfig() {
      previewConfigStatusEl.textContent = 'Preview-Konfiguration wird geladen...';
      previewConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/preview/config');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        if (data.preview_ocr_model && availableModelNames.includes(data.preview_ocr_model)) {
          previewOcrModelEl.value = data.preview_ocr_model;
        }
        if (data.vision_model && availableModelNames.includes(data.vision_model)) {
          previewVisionModelEl.value = data.vision_model;
        }
        previewVisionContentCharsEl.value = data.vision_content_chars || '';
        previewVisionTimeoutEl.value = data.vision_timeout_seconds || '';
        previewVisionMaxPagesEl.value = data.vision_max_pages || '';
        previewVisionTagNameEl.value = data.vision_tag_name || '';
        previewVisionTagColorEl.value = data.vision_tag_color || '';
        previewConfigStatusEl.textContent = 'Preview-Konfiguration geladen.';
      } catch (err) {
        previewConfigStatusEl.textContent = `Fehler: ${err.message}`;
        previewConfigStatusEl.className = 'statusline warn';
      }
    }

    async function savePreviewConfig() {
      savePreviewConfigBtn.disabled = true;
      previewConfigStatusEl.textContent = 'Preview-Konfiguration wird gespeichert...';
      previewConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/preview/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            preview_ocr_model: previewOcrModelEl.value,
            vision_model: previewVisionModelEl.value,
            vision_content_chars: previewVisionContentCharsEl.value.trim(),
            vision_timeout_seconds: previewVisionTimeoutEl.value.trim(),
            vision_max_pages: previewVisionMaxPagesEl.value.trim(),
            vision_tag_name: previewVisionTagNameEl.value.trim(),
            vision_tag_color: previewVisionTagColorEl.value.trim()
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        previewConfigStatusEl.textContent = 'Preview-Konfiguration gespeichert.';
      } catch (err) {
        previewConfigStatusEl.textContent = `Fehler: ${err.message}`;
        previewConfigStatusEl.className = 'statusline warn';
      } finally {
        savePreviewConfigBtn.disabled = false;
      }
    }

    async function loadPrompt() {
      promptStatusEl.textContent = 'Prompt wird geladen...';
      promptStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/prompt');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        promptEditorEl.value = data.prompt || '';
        promptStatusEl.textContent = 'Prompt geladen.';
      } catch (err) {
        promptStatusEl.textContent = `Fehler: ${err.message}`;
        promptStatusEl.className = 'statusline warn';
      }
    }

    async function savePrompt() {
      savePromptBtn.disabled = true;
      promptStatusEl.textContent = 'Prompt wird gespeichert...';
      promptStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/prompt', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: promptEditorEl.value })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        promptStatusEl.textContent = 'Prompt gespeichert.';
      } catch (err) {
        promptStatusEl.textContent = `Fehler: ${err.message}`;
        promptStatusEl.className = 'statusline warn';
      } finally {
        savePromptBtn.disabled = false;
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
      const mode = getBackfillMode();
      return {
        dry_run: dryRun,
        limit: Number(backfillLimitEl.value || 0),
        query: backfillQueryEl.value.trim(),
        from_id: Number(backfillFromIdEl.value || 0),
        only_missing_metadata: mode === 'missing',
        document_ids: mode === 'selected' ? Array.from(selectedDocumentIds) : [],
        mode
      };
    }

    async function runBackfill(dryRun) {
      const mode = getBackfillMode();
      const selectedCount = selectedDocumentIds.size;
      if (mode === 'selected' && selectedCount === 0) {
        backfillStatusEl.textContent = 'Keine Dokumente ausgewaehlt.';
        backfillStatusEl.className = 'statusline warn';
        return;
      }
      if (!dryRun) {
        const limit = Number(backfillLimitEl.value || 0);
        const query = backfillQueryEl.value.trim();
        const warning = [
          'Der echte Backfill startet jetzt die KI-Nachbearbeitung fuer vorhandene Paperless-Dokumente.',
          mode === 'missing' ? 'Modus: nur fehlende Metadaten' : mode === 'all' ? 'Modus: alle gefundenen Dokumente' : `Modus: nur Auswahl (${selectedCount})`,
          limit > 0 ? `Limit: ${limit}` : 'Limit: unbegrenzt',
          query ? `Query: ${query}` : 'Query: keine',
          mode === 'selected' ? `Ausgewaehlte Dokumente: ${selectedCount}` : 'Ausgewaehlte Dokumente: keine feste Auswahl'
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
    navButtons.forEach(btn => {
      btn.addEventListener('click', () => setActiveView(btn.dataset.viewTarget));
    });
    layoutSidebarBtn.addEventListener('click', () => setLayoutMode('sidebar'));
    layoutTopBtn.addEventListener('click', () => setLayoutMode('top'));
    paperlessFallbackEnabledEl.addEventListener('change', syncFallbackUi);
    savePaperlessModelBtn.addEventListener('click', savePaperlessModel);
    saveAiConfigBtn.addEventListener('click', saveAiConfig);
    reloadAiConfigBtn.addEventListener('click', loadAiConfig);
    savePreviewConfigBtn.addEventListener('click', savePreviewConfig);
    reloadPreviewConfigBtn.addEventListener('click', loadPreviewConfig);
    savePromptBtn.addEventListener('click', savePrompt);
    reloadPromptBtn.addEventListener('click', loadPrompt);
    docRefreshBtn.addEventListener('click', loadDocuments);
    docClearSelectionBtn.addEventListener('click', () => {
      selectedDocumentIds = new Set();
      renderDocumentList();
    });
    docPreviewSingleBtn.addEventListener('click', () => runSingleDocument(true));
    docRunSingleBtn.addEventListener('click', () => runSingleDocument(false));
    docApplyProposalBtn.addEventListener('click', applyProposal);
    docDiscardProposalBtn.addEventListener('click', discardProposal);
    docSearchEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loadDocuments();
    });
    backfillPreviewBtn.addEventListener('click', () => runBackfill(true));
    backfillRunBtn.addEventListener('click', () => runBackfill(false));

    loadModels().catch(() => {
      statusEl.textContent = 'Modelle konnten nicht geladen werden.';
    });
    try {
      const savedLayout = localStorage.getItem('paperless-ui-layout');
      if (savedLayout === 'top') setLayoutMode('top');
    } catch (_) {}
    syncFallbackUi();
    loadAiConfig();
    loadPreviewConfig();
    loadPrompt();
    loadDocuments();
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


def positive_int(value: str | int | None, default: int) -> int:
    try:
        parsed = int(str(value).strip())
    except (AttributeError, TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


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


def ollama_num_thread() -> int:
    try:
        env_map = load_paperless_env()
    except Exception:
        env_map = {}
    return positive_int(env_map.get("PAPERLESS_AI_OLLAMA_NUM_THREAD") or os.getenv("OLLAMA_NUM_THREAD") or "4", 4)


def default_preview_config() -> dict[str, str]:
    return {
        "preview_ocr_model": os.getenv("PAPERLESS_PREVIEW_OCR_MODEL", "qwen3.5:4b"),
        "vision_model": os.getenv("PAPERLESS_PREVIEW_VISION_MODEL", "qwen3.5:0.8b"),
        "vision_content_chars": os.getenv("PAPERLESS_PREVIEW_VISION_CONTENT_CHARS", "800"),
        "vision_timeout_seconds": os.getenv("PAPERLESS_PREVIEW_VISION_TIMEOUT_SECONDS", "120"),
        "vision_max_pages": os.getenv("PAPERLESS_PREVIEW_VISION_MAX_PAGES", "1"),
        "vision_tag_name": os.getenv("PAPERLESS_PREVIEW_VISION_TAG_NAME", "KI Vision"),
        "vision_tag_color": os.getenv("PAPERLESS_PREVIEW_VISION_TAG_COLOR", "#d97706"),
    }


def load_preview_config() -> dict[str, str]:
    config = default_preview_config()
    path = Path(PREVIEW_CONFIG_PATH)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid preview config: {exc}") from exc
        if isinstance(loaded, dict):
            for key in config:
                value = loaded.get(key)
                if value is not None and str(value).strip():
                    config[key] = str(value).strip()
    return config


def save_preview_config(payload: dict) -> tuple[int, dict]:
    allowed = default_preview_config()
    current = load_preview_config()
    for key in allowed:
        value = str(payload.get(key, "")).strip()
        if value:
            current[key] = value
    path = Path(PREVIEW_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 200, {"status": "ok"}


def read_paperless_prompt() -> tuple[int, dict]:
    prompt_path = Path("/opt/paperless/ai_enrich_prompt.txt")
    if not prompt_path.is_file():
        return 404, {"error": f"Prompt file not found: {prompt_path}"}
    return 200, {"prompt": prompt_path.read_text(encoding="utf-8")}


def load_hook_module(hook_path: str = "/opt/paperless/ai_enrich.py"):
    spec = importlib.util.spec_from_file_location("paperless_ai_enrich", hook_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load hook module from {hook_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_paperless_config() -> tuple[int, dict]:
    env_map = load_paperless_env()
    tag_allowlists_json = ""
    tag_rules_json = ""
    raw_b64 = env_map.get("PAPERLESS_AI_TAG_ALLOWLISTS_B64", "")
    if raw_b64:
        try:
            tag_allowlists_json = base64.b64decode(raw_b64).decode("utf-8")
        except Exception:
            tag_allowlists_json = ""
    raw_rules_b64 = env_map.get("PAPERLESS_AI_TAG_RULES_B64", "")
    if raw_rules_b64:
        try:
            tag_rules_json = base64.b64decode(raw_rules_b64).decode("utf-8")
        except Exception:
            tag_rules_json = ""
    if not tag_allowlists_json:
        try:
            module = load_hook_module()
            tag_allowlists_json = module.default_allowed_tags_by_family_json()
        except Exception:
            tag_allowlists_json = json.dumps(
                {
                    "school": ["Fehlzeiten", "Schulpflicht", "Attest", "Schulbescheinigung", "Ordnungsmaßnahme"],
                    "court": ["Beschluss", "Pflegschaft", "Familienrecht", "Unterhalt", "Umgangsrecht"],
                    "lawyer": ["Familienrecht", "Unterhalt", "Umgangsrecht", "Sorgerecht", "Schriftsatz"],
                    "medical": ["Attest", "Befund", "Labor", "Diagnose", "Medikation"],
                    "tax": ["Einkommensteuer", "Umsatzsteuer", "Steuerbescheid", "Steuererklärung", "ELSTER"],
                },
                ensure_ascii=False,
                indent=2,
            )
    if not tag_rules_json:
        try:
            module = load_hook_module()
            tag_rules_json = module.default_tag_rules_by_family_json()
        except Exception:
            tag_rules_json = json.dumps(
                {
                    "school": {"Fehlzeiten": ["fehlzeit"], "Schulpflicht": ["schulpflicht"], "Attest": ["attest", "ärzt", "aerzt"]},
                    "court": {"Beschluss": ["beschluss"], "Pflegschaft": ["pflegschaft"], "Familienrecht": ["familiengericht", "familienrecht"]},
                    "medical": {"Attest": ["attest", "ärztliche bescheinigung"], "Kinderarzt": ["kinderarzt", "kinder und jugendmedizin"]},
                    "tax": {"Einkommensteuer": ["einkommensteuer"], "Steuerbescheid": ["steuerbescheid"], "ELSTER": ["elster"]},
                    "lawyer": {"Familienrecht": ["familienrecht"], "Unterhalt": ["unterhalt"], "Schriftsatz": ["schriftsatz"]},
                },
                ensure_ascii=False,
                indent=2,
            )
    return 200, {
        "model": env_map.get("PAPERLESS_AI_OLLAMA_MODEL", ""),
        "fallback_enabled": env_map.get("PAPERLESS_AI_FALLBACK_ENABLED", "false"),
        "fallback_model": env_map.get("PAPERLESS_AI_FALLBACK_MODEL", ""),
        "fallback_timeout_only": env_map.get("PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY", "true"),
        "fallback_http_timeout_seconds": env_map.get("PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS", ""),
        "content_chars": env_map.get("PAPERLESS_AI_CONTENT_CHARS", ""),
        "min_confidence": env_map.get("PAPERLESS_AI_MIN_CONFIDENCE", ""),
        "http_timeout_seconds": env_map.get("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", ""),
        "default_tag_color": env_map.get("PAPERLESS_AI_DEFAULT_TAG_COLOR", ""),
        "tag_review_model": env_map.get("PAPERLESS_AI_TAG_OLLAMA_MODEL", ""),
        "tag_review_timeout_seconds": env_map.get("PAPERLESS_AI_TAG_HTTP_TIMEOUT_SECONDS", ""),
        "review_min_confidence": env_map.get("PAPERLESS_AI_REVIEW_MIN_CONFIDENCE", "0.8"),
        "review_tag_name": env_map.get("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen"),
        "review_tag_color": env_map.get("PAPERLESS_AI_REVIEW_TAG_COLOR", "#7dd3fc"),
        "tag_allowlists_json": tag_allowlists_json,
        "tag_rules_json": tag_rules_json,
    }


def read_preview_config() -> tuple[int, dict]:
    return 200, load_preview_config()


def call_ai_helper(args: list[str]) -> tuple[int, dict]:
    helper = Path(PAPERLESS_AI_HELPER)
    if not helper.is_file():
        return 500, {"error": f"Helper not found: {helper}"}
    result = subprocess.run(
        ["/usr/bin/sudo", str(helper), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return 500, {"error": output or "helper failed"}
    return 200, {"output": ((result.stdout or "") + (result.stderr or "")).strip()}


def save_paperless_prompt(prompt: str) -> tuple[int, dict]:
    prompt_text = str(prompt or "")
    tmp_path = Path("/tmp/paperless-ai-prompt.txt")
    tmp_path.write_text(prompt_text, encoding="utf-8")
    return call_ai_helper(["set-prompt", str(tmp_path)])


def save_paperless_config(payload: dict) -> tuple[int, dict]:
    allowed = {
        "primary_model": "PAPERLESS_AI_OLLAMA_MODEL",
        "fallback_enabled": "PAPERLESS_AI_FALLBACK_ENABLED",
        "fallback_model": "PAPERLESS_AI_FALLBACK_MODEL",
        "fallback_timeout_only": "PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY",
        "fallback_http_timeout_seconds": "PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS",
        "content_chars": "PAPERLESS_AI_CONTENT_CHARS",
        "min_confidence": "PAPERLESS_AI_MIN_CONFIDENCE",
        "http_timeout_seconds": "PAPERLESS_AI_HTTP_TIMEOUT_SECONDS",
        "default_tag_color": "PAPERLESS_AI_DEFAULT_TAG_COLOR",
        "tag_review_model": "PAPERLESS_AI_TAG_OLLAMA_MODEL",
        "tag_review_timeout_seconds": "PAPERLESS_AI_TAG_HTTP_TIMEOUT_SECONDS",
        "review_min_confidence": "PAPERLESS_AI_REVIEW_MIN_CONFIDENCE",
        "review_tag_name": "PAPERLESS_AI_REVIEW_TAG_NAME",
        "review_tag_color": "PAPERLESS_AI_REVIEW_TAG_COLOR",
    }
    for field, key in allowed.items():
        value = str(payload.get(field, "")).strip()
        if not value:
            continue
        status, response = call_ai_helper(["set-config", key, value])
        if status != 200:
            return status, response
    tag_allowlists_json = str(payload.get("tag_allowlists_json", "")).strip()
    if tag_allowlists_json:
        try:
            parsed = json.loads(tag_allowlists_json)
            if not isinstance(parsed, dict):
                return 400, {"error": "Tag-Allowlists muessen ein JSON-Objekt sein"}
        except Exception as exc:
            return 400, {"error": f"Ungueltiges Tag-Allowlist-JSON: {exc}"}
        encoded = base64.b64encode(tag_allowlists_json.encode("utf-8")).decode("ascii")
        status, response = call_ai_helper(["set-config", "PAPERLESS_AI_TAG_ALLOWLISTS_B64", encoded])
        if status != 200:
            return status, response
    tag_rules_json = str(payload.get("tag_rules_json", "")).strip()
    if tag_rules_json:
        try:
            parsed = json.loads(tag_rules_json)
            if not isinstance(parsed, dict):
                return 400, {"error": "Tag-Regeln muessen ein JSON-Objekt sein"}
        except Exception as exc:
            return 400, {"error": f"Ungueltiges Tag-Regel-JSON: {exc}"}
        encoded = base64.b64encode(tag_rules_json.encode("utf-8")).decode("ascii")
        status, response = call_ai_helper(["set-config", "PAPERLESS_AI_TAG_RULES_B64", encoded])
        if status != 200:
            return status, response
    status, response = call_ai_helper(["restart-workers"])
    if status != 200:
        return status, response
    return 200, {"status": "ok"}


def fetch_paperless_documents(query: str | None = None, limit: int = 40) -> tuple[int, dict]:
    paperless_env = load_paperless_env()
    api_url = paperless_env.get("PAPERLESS_API_URL")
    token = paperless_env.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        return 500, {"error": "Paperless API configuration is incomplete"}
    params = {"page_size": max(1, min(limit, 200)), "ordering": "-id"}
    if query:
        params["query"] = query
    url = f"{api_url.rstrip('/')}/api/documents/?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Token {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    documents = []
    for item in payload.get("results", []):
        correspondent_name = ""
        corr = item.get("correspondent")
        if isinstance(corr, dict):
            correspondent_name = corr.get("name", "")
        documents.append(
            {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "created_date": item.get("created_date", ""),
                "original_file_name": item.get("original_file_name", ""),
                "page_count": item.get("page_count"),
                "tags": item.get("tags", []),
                "document_type": item.get("document_type"),
                "correspondent": item.get("correspondent"),
                "correspondent_name": correspondent_name,
            }
        )
    return 200, {"documents": documents, "count": payload.get("count", len(documents))}


def fetch_paperless_document(document_id: int) -> tuple[int, dict]:
    paperless_env = load_paperless_env()
    api_url = paperless_env.get("PAPERLESS_API_URL")
    token = paperless_env.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        return 500, {"error": "Paperless API configuration is incomplete"}
    url = f"{api_url.rstrip('/')}/api/documents/{document_id}/"
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "Authorization": f"Token {token}"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=60) as response:
        item = json.loads(response.read().decode("utf-8"))
    correspondent_name = ""
    corr = item.get("correspondent")
    if isinstance(corr, dict):
        correspondent_name = corr.get("name", "")
    document_type_name = ""
    doc_type = item.get("document_type")
    if isinstance(doc_type, dict):
        document_type_name = doc_type.get("name", "")
    tags = []
    for tag in item.get("tags", []):
        if isinstance(tag, dict):
            tags.append({"id": tag.get("id"), "name": tag.get("name", "")})
    document = {
        "id": item.get("id"),
        "title": item.get("title", ""),
        "created_date": item.get("created_date", ""),
        "original_file_name": item.get("original_file_name", ""),
        "page_count": item.get("page_count"),
        "content": item.get("content", ""),
        "tags": tags,
        "document_type": item.get("document_type"),
        "document_type_name": document_type_name,
        "correspondent": item.get("correspondent"),
        "correspondent_name": correspondent_name,
    }
    return 200, {"document": document}


def fetch_paperless_document_binary(document_id: int) -> tuple[bytes, str]:
    paperless_env = load_paperless_env()
    api_url = paperless_env.get("PAPERLESS_API_URL")
    token = paperless_env.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        raise RuntimeError("Paperless API configuration is incomplete")
    candidates = (
        f"/api/documents/{document_id}/download/",
        f"/api/documents/{document_id}/original/",
        f"/api/documents/{document_id}/file/",
    )
    last_error = "document binary endpoint not found"
    for path in candidates:
        url = f"{api_url.rstrip('/')}{path}"
        req = urllib.request.Request(
            url,
            headers={"Accept": "*/*", "Authorization": f"Token {token}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                return response.read(), response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            last_error = f"{path} returned {exc.code}"
            if exc.code == 404:
                continue
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Downloading document {document_id} failed via {path}: {body}") from exc
    raise RuntimeError(f"Downloading document {document_id} failed: {last_error}")


def render_pdf_preview_images(pdf_bytes: bytes, max_pages: int = 1) -> list[str]:
    pdftoppm = "/usr/bin/pdftoppm"
    if not Path(pdftoppm).is_file():
        raise RuntimeError("pdftoppm is not installed on the host")
    with tempfile.TemporaryDirectory(prefix="paperless-ai-vision-") as tmpdir:
        tmp_path = Path(tmpdir)
        pdf_path = tmp_path / "document.pdf"
        pdf_path.write_bytes(pdf_bytes)
        output_prefix = tmp_path / "page"
        cmd = [
            pdftoppm,
            "-jpeg",
            "-f",
            "1",
            "-l",
            str(max(1, max_pages)),
            str(pdf_path),
            str(output_prefix),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
        if result.returncode != 0:
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            raise RuntimeError(output or "pdftoppm failed")
        image_paths = sorted(tmp_path.glob("page-*.jpg"))
        if not image_paths:
            raise RuntimeError("pdftoppm did not produce preview images")
        return [base64.b64encode(path.read_bytes()).decode("ascii") for path in image_paths]


def build_vision_prompt(base_prompt: str) -> str:
    addition = """

Zusatz fuer die Analyse:
- Nutze neben dem OCR-Inhalt auch das beigefuegte Seitenbild.
- Wenn OCR und Seitenbild widerspruechlich wirken, bewerte den sichtbaren Dokumentaufbau, Briefkopf und klar lesbare Textelemente mit.
- Bleibe trotz Bildanalyse streng beim JSON-Format.
""".strip()
    return f"{base_prompt}\n\n{addition}"


def build_document_prompt_with_limit(module, document: dict, existing_person_tags: list[str], content_chars: int) -> str:
    title = document.get("title") or ""
    original = document.get("original_file_name") or ""
    correspondent = (document.get("correspondent") or {}).get("name", "") if isinstance(document.get("correspondent"), dict) else ""
    doc_type = (document.get("document_type") or {}).get("name", "") if isinstance(document.get("document_type"), dict) else ""
    tags = [tag.get("name", "") for tag in document.get("tags", []) if isinstance(tag, dict)]
    content = module.truncate_text(document.get("content") or "", content_chars)
    template = module.load_prompt_template()
    return template.format(
        title=title,
        original=original,
        correspondent=correspondent,
        doc_type=doc_type,
        tags=", ".join(tags),
        existing_person_tags=", ".join(existing_person_tags) or "-",
        content=content,
    )


ORG_HINT_TOKENS = (
    "schule", "realschule", "grundschule", "gymnasium", "berufskolleg", "universit",
    "amt", "amtsgericht", "landgericht", "gericht", "stadt", "gemeinde", "kreis",
    "jugendamt", "finanzamt", "behoerde", "praxis", "arzt", "klinik", "krankenhaus",
    "versicherung", "bank", "sparkasse", "gmbh", "ug", "ag", "kg", "kanzlei", "notar",
    "steuerberater", "anwalt", "familiengericht", "schulleiter", "schulleitung",
)
ROLE_HINT_TOKENS = (
    "schulleiter", "schulleitung", "richter", "richterin", "arzt", "ärztin", "dr.",
    "prof.", "kanzlei", "anwalt", "anwältin", "notar", "notarin", "sachbearbeiter",
    "sachbearbeiterin", "jugendamt", "familiengericht",
)


def is_address_like_line(line: str) -> bool:
    lowered = line.casefold()
    if re.search(r"\b\d{5}\b", line):
        return True
    if "@" in line or "www." in lowered or "tel." in lowered or "fax" in lowered:
        return True
    if re.search(r"\b(?:str\.|straße|weg|platz|allee|gasse|ufer|chaussee)\b", lowered):
        return True
    return False


def clean_name_like_value(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,;-")
    text = re.sub(r"\b(?:Herr|Frau|Familie)\b\.?\s+", "", text, flags=re.IGNORECASE).strip()
    return text


def extract_person_from_salutation(line: str) -> str:
    match = re.search(r"(?:Sehr geehrte(?:r)?|Guten Tag|Hallo)\s+(.*)", str(line or ""), re.IGNORECASE)
    if not match:
        return ""
    value = clean_name_like_value(match.group(1))
    return value.rstrip(",")


def looks_like_org_line(line: str) -> bool:
    lowered = str(line or "").casefold()
    return any(token in lowered for token in ORG_HINT_TOKENS)


def looks_like_role_line(line: str) -> bool:
    lowered = str(line or "").casefold()
    return any(token in lowered for token in ROLE_HINT_TOKENS)


def extract_person_name_from_line(line: str) -> str:
    compact = re.sub(r"\s+", " ", str(line or "")).strip()
    match = re.search(r"\b([A-ZÄÖÜ][a-zäöüß.-]+)\s+([A-ZÄÖÜ][a-zäöüß.-]+)\b", compact)
    if not match:
        return ""
    candidate = clean_name_like_value(f"{match.group(1)} {match.group(2)}")
    if candidate.casefold() in {"förmliche zustellung", "foermliche zustellung"}:
        return ""
    return candidate


def canonical_org_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" ,;-")
    patterns = (
        r"(Amtsgericht\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
        r"(Landgericht\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
        r"(Oberlandesgericht\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
        r"(Finanzamt\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
        r"(Realschule\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
        r"(Gymnasium\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß.-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_sender_label(match.group(1))
    return normalize_sender_label(text)


def infer_org_from_email_domain(text: str) -> str:
    match = re.search(r"@([a-z0-9.-]+\.[a-z]{2,})", str(text or ""), re.IGNORECASE)
    if not match:
        return ""
    domain = match.group(1).split(".", 1)[0]
    parts = [part for part in re.split(r"[-_]+", domain) if part and part not in {"mail", "verwaltung", "info", "kontakt", "service"}]
    if not parts:
        return ""
    normalized = []
    for part in parts[:3]:
        if part in {"gmbh", "ag", "ug", "kg"}:
            normalized.append(part.upper())
        else:
            normalized.append(part.capitalize())
    return " ".join(normalized).strip()


def sanitize_org_candidate(line: str) -> str:
    value = re.sub(r"\s+", " ", str(line or "")).strip(" ,;-")
    value = re.sub(r"^[\"'`|{(\\\[\]]+\s*", "", value)
    value = re.sub(r"\s*[\"'`|})\\\[\]]+$", "", value)
    return value.strip()


def collapse_org_candidates(lines: list[str]) -> str:
    usable = [
        sanitize_org_candidate(line)
        for line in lines
        if line and (looks_like_org_line(line) or not is_address_like_line(line))
    ]
    usable = [line for line in usable if len(line) > 2]
    if not usable:
        return ""
    for line in usable:
        lowered = line.casefold()
        if ("amtsgericht" in lowered or "landgericht" in lowered or "oberlandesgericht" in lowered) and not re.search(r"[{}()]", line):
            return canonical_org_name(line)
    for line in usable:
        lowered = line.casefold()
        if "realschule" in lowered or "schule" in lowered:
            return canonical_org_name(line)
    primary = usable[0]
    if len(usable) > 1 and looks_like_org_line(primary) and not re.search(r"\b[A-ZÄÖÜ][a-zäöüß-]+\b", primary.split()[-1]):
        merged = f"{primary} {usable[1]}".strip()
        return canonical_org_name(re.sub(r"\s+", " ", merged))
    return canonical_org_name(primary)


def derive_document_hints(ocr_view: dict) -> dict:
    sections = dict(ocr_view.get("sections") or {})
    cleaned_text = str(ocr_view.get("cleaned_text") or "")
    header_lines = [line.strip() for line in str(sections.get("header") or "").splitlines() if line.strip()]
    recipient_lines = [line.strip() for line in str(sections.get("recipient") or "").splitlines() if line.strip()]
    signature_lines = [line.strip() for line in str(sections.get("signature") or "").splitlines() if line.strip()]
    salutation = str(sections.get("salutation") or "").strip()
    subject = str(sections.get("subject") or "").strip()

    sender_candidates = [line for line in header_lines if looks_like_org_line(line)]
    sender = collapse_org_candidates(sender_candidates[:2])
    domain_sender = infer_org_from_email_domain(cleaned_text)
    if domain_sender and (not sender or len(sender) < 10 or sender[:1].isdigit()):
        sender = domain_sender
    if not sender:
        for line in signature_lines:
            if looks_like_org_line(line) or looks_like_role_line(line):
                sender = clean_name_like_value(line)
                break

    recipient = ""
    if salutation:
        recipient = extract_person_from_salutation(salutation)
    recipient_line_name = ""
    for line in header_lines + recipient_lines:
        if is_address_like_line(line):
            extracted = extract_person_name_from_line(line)
            if extracted:
                recipient_line_name = extracted
                break
    if not recipient:
        for line in recipient_lines:
            if is_address_like_line(line):
                continue
            candidate = clean_name_like_value(line)
            if candidate and not looks_like_org_line(candidate) and "förmliche zustellung" not in candidate.casefold():
                recipient = candidate
                break
    if recipient_line_name and (not recipient or len(recipient.split()) < 2):
        recipient = recipient_line_name

    signer = ""
    for line in signature_lines:
        candidate = clean_name_like_value(line)
        if candidate and candidate.casefold() not in ("mit freundlichen grüßen", "mit freundlichen gruessen"):
            signer = candidate
            break

    subject_lines = []
    if subject:
        subject_lines.append(subject)
    for line in recipient_lines[:4]:
        lowered = line.casefold()
        if any(token in lowered for token in ("vorlage", "fehlzeiten", "rechnung", "beschluss", "bescheid", "steuer", "attest", "klage", "urteil")):
            if line not in subject_lines:
                subject_lines.append(line)
    subject_hint = " / ".join(subject_lines[:2]).strip()

    guidance = []
    if sender:
        guidance.append(f"Mutmasslicher Absender: {sender}")
    if recipient:
        guidance.append(f"Mutmasslicher Adressat: {recipient}")
        guidance.append("Adressat oder Name aus der Anrede ist nicht die Korrespondenz.")
    if signer:
        guidance.append(f"Mutmassliche Signatur: {signer}")
    if subject_hint:
        guidance.append(f"Mutmasslicher Betreff: {subject_hint}")
    if sender and signer and sender.casefold() not in signer.casefold():
        guidance.append("Bevorzuge die Organisation im Briefkopf als Korrespondenz vor einzelnen Namen in Signatur oder Anrede.")

    return {
        "sender": sender,
        "recipient": recipient,
        "signer": signer,
        "subject": subject_hint,
        "guidance_text": "\n".join(guidance).strip(),
    }


def detect_document_family(document_hints: dict, proposal: dict) -> str:
    sender = str(document_hints.get("sender", "") or "").casefold()
    signer = str(document_hints.get("signer", "") or "").casefold()
    subject = str(document_hints.get("subject", "") or "").casefold()
    haystack = " ".join(
        str(value or "")
        for value in (
            document_hints.get("sender", ""),
            document_hints.get("subject", ""),
            document_hints.get("signer", ""),
            proposal.get("document_type", ""),
            proposal.get("title", ""),
            proposal.get("reason", ""),
        )
    ).casefold()
    medical_markers = (
        "gemeinschaftspraxis", "kinder und jugendmedizin", "facharzt", "arzt",
        "ärzt", "aerzt", "praxis", "klinik", "krankenhaus", "allergologie",
        "kinder-pneumolog", "kinderarzt", "medizin"
    )
    school_markers = (
        "schule", "realschule", "gymnasium", "schulleiter", "schulpflicht",
        "unterricht", "fehlzeiten"
    )
    if any(token in sender or token in signer for token in medical_markers):
        return "medical"
    if any(token in sender or token in signer for token in school_markers):
        return "school"
    if any(token in haystack for token in ("gericht", "beschluss", "sofortige beschwerde", "familiengericht", "amtsgericht", "landgericht", "oberlandesgericht")):
        return "court"
    if any(token in subject for token in medical_markers):
        return "medical"
    if any(token in haystack for token in ("schule", "realschule", "gymnasium", "schul", "schulleiter", "fehltag")):
        return "school"
    if any(token in haystack for token in ("arzt", "ärzt", "praxis", "klinik", "krankenhaus", "medizin", "attest")):
        return "medical"
    if any(token in haystack for token in ("finanzamt", "steuer", "elster", "umsatzsteuer", "einkommensteuer", "bescheid")):
        return "tax"
    return ""


def canonical_subject(subject: str) -> str:
    value = re.sub(r"\s+", " ", str(subject or "")).strip(" ,;-")
    replacements = {
        "Fehlzeiten des Schülers / der Schülerin": "Fehlzeiten",
        "Fehlzeiten des Schuelers / der Schuelerin": "Fehlzeiten",
        "Vorlage ärztlicher Atteste": "Vorlage ärztlicher Atteste",
        "Vorlage aerztlicher Atteste": "Vorlage ärztlicher Atteste",
    }
    return replacements.get(value, value)


def normalize_sender_label(sender: str) -> str:
    return re.sub(r"\s+", " ", str(sender or "")).strip(" ,;-")


def build_domain_title(document_hints: dict, proposal: dict) -> str:
    family = detect_document_family(document_hints, proposal)
    sender = normalize_sender_label(document_hints.get("sender", ""))
    subject = canonical_subject(document_hints.get("subject", ""))
    doc_type = re.sub(r"\s+", " ", str(proposal.get("document_type") or "")).strip(" ,;-")

    if family == "school":
        if "attest" in subject.casefold():
            return f"Schule: {subject}"
        if subject:
            return f"Schule: {subject}"
        return f"Schule: {sender}" if sender else ""

    if family == "court":
        title_core = "Beschluss"
        if doc_type:
            title_core = doc_type
        elif subject and not re.search(r"[{}]|umsatzsteuer|id", subject, re.IGNORECASE):
            title_core = subject
        return f"{sender}: {title_core}".strip(": ") if sender else title_core

    if family == "medical":
        if doc_type:
            return f"Medizin: {doc_type}"
        if subject and any(token in subject.casefold() for token in ("ärzt", "aerzt", "attest", "bescheinigung")):
            return f"Medizin: {subject}"
        if subject:
            return f"Medizin: {subject}"
        return f"Medizin: {sender}" if sender else ""

    if family == "tax":
        if doc_type:
            return f"Steuer: {doc_type}"
        if subject:
            return f"Steuer: {subject}"
        return f"Steuer: {sender}" if sender else ""

    return ""


def apply_rule_based_preview_corrections(proposal: dict, document_hints: dict) -> dict:
    corrected = dict(proposal)
    sender = normalize_sender_label(clean_name_like_value(document_hints.get("sender", "")))
    recipient = clean_name_like_value(document_hints.get("recipient", ""))
    subject = str(document_hints.get("subject") or "").strip()
    signer = clean_name_like_value(document_hints.get("signer", ""))
    family = detect_document_family(document_hints, corrected)

    correspondent = clean_name_like_value(corrected.get("correspondent", ""))
    if family in {"school", "court", "tax"} and sender:
        corrected["correspondent"] = sender
    elif recipient and correspondent and correspondent.casefold() == recipient.casefold() and sender:
        corrected["correspondent"] = sender
    elif sender and (
        not correspondent
        or looks_like_role_line(correspondent)
        or correspondent.casefold() == signer.casefold()
        or (recipient and recipient.casefold() in correspondent.casefold())
    ):
        corrected["correspondent"] = sender

    title = str(corrected.get("title") or "").strip()
    if title.lower().startswith("dokumententyp:"):
        title = re.sub(r"^Dokumententyp:\s*", "", title, flags=re.IGNORECASE).strip()
    if subject and (not title or title.casefold() in {recipient.casefold(), signer.casefold()}):
        corrected["title"] = subject
    elif subject and sender and len(title) < 12:
        corrected["title"] = f"{subject} {sender}".strip()
    elif subject and sender and title:
        lowered = title.casefold()
        if sender.casefold() not in lowered and subject.casefold() not in lowered:
            corrected["title"] = f"{subject} {sender}".strip()
        else:
            corrected["title"] = title

    domain_title = build_domain_title(document_hints, corrected)
    if domain_title:
        corrected["title"] = domain_title

    return corrected


def normalize_ocr_lines(raw_text: str) -> list[str]:
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = text.replace("’", "'").replace("„", '"').replace("“", '"')
    lines = [line.strip(" \t") for line in text.split("\n")]
    cleaned: list[str] = []
    previous_blank = True
    for line in lines:
        line = re.sub(r"\s{2,}", " ", line).strip()
        if not line:
            if not previous_blank:
                cleaned.append("")
            previous_blank = True
            continue
        if len(line) == 1 and not line.isdigit():
            continue
        cleaned.append(line)
        previous_blank = False
    while cleaned and not cleaned[-1]:
        cleaned.pop()
    return cleaned


def collapse_paragraph_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if current:
            joinable = (
                not current[-1].endswith((".", ":", ";", "!", "?"))
                and line[:1].islower()
            )
            if joinable:
                current[-1] = f"{current[-1]} {line}"
            else:
                current.append(line)
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current).strip())
    return paragraphs


def build_structured_ocr_view(raw_text: str) -> dict:
    lines = normalize_ocr_lines(raw_text)
    cleaned_text = "\n".join(lines).strip()
    paragraphs = collapse_paragraph_lines(lines)

    subject_idx = None
    subject_value = ""
    for idx, line in enumerate(lines):
        lowered = line.casefold()
        if any(token in lowered for token in ("betreff", "vorlage", "rechnung", "beschluss", "bescheid", "mahnbescheid", "fehlzeiten", "steuer", "attest", "klage", "urteil")):
            if len(line) <= 140:
                subject_idx = idx
                subject_value = line
                break

    date_idx = None
    date_value = ""
    for idx, line in enumerate(lines):
        if re.search(r"\b\d{1,2}\.\d{1,2}\.\d{2,4}\b", line):
            date_idx = idx
            date_value = line
            break

    salutation_idx = None
    salutation = ""
    for idx, line in enumerate(lines):
        if re.match(r"^(Sehr geehrte(?:r|n)?|Guten Tag|Hallo|An das|An die)\b", line):
            salutation_idx = idx
            salutation = line
            break

    closing_idx = None
    for idx, line in enumerate(lines):
        if re.match(r"^(Mit freundlichen Gru[eü]ßen|Freundliche Gr[uü][ßs]e|Hochachtungsvoll)\b", line):
            closing_idx = idx
            break

    recipient_lines: list[str] = []
    if date_idx is not None:
        start = max(0, date_idx - 6)
        recipient_lines = [line for line in lines[start:date_idx] if line]

    header_lines: list[str] = []
    if recipient_lines and date_idx is not None:
        header_lines = [line for line in lines[: max(0, date_idx - len(recipient_lines))] if line]
    elif date_idx is not None:
        header_lines = [line for line in lines[:date_idx] if line]
    else:
        header_lines = [line for line in lines[:8] if line]

    body_lines: list[str] = []
    if salutation_idx is not None:
        end_idx = closing_idx if closing_idx is not None else len(lines)
        body_lines = [line for line in lines[salutation_idx + 1:end_idx] if line]
    elif subject_idx is not None:
        body_lines = [line for line in lines[subject_idx + 1:] if line][:30]

    signature_lines: list[str] = []
    if closing_idx is not None:
        signature_lines = [line for line in lines[closing_idx:] if line][:6]

    sections = {
        "header": "\n".join(header_lines[:8]).strip(),
        "recipient": "\n".join(recipient_lines[:6]).strip(),
        "date": date_value.strip(),
        "subject": subject_value.strip(),
        "salutation": salutation.strip(),
        "body": "\n\n".join(body_lines[:8]).strip(),
        "signature": "\n".join(signature_lines).strip(),
    }
    summary_parts = []
    for label, key in (
        ("Briefkopf", "header"),
        ("Adressat", "recipient"),
        ("Datum", "date"),
        ("Betreff", "subject"),
        ("Anrede", "salutation"),
        ("Signatur", "signature"),
    ):
        value = sections.get(key, "").strip()
        if value:
            summary_parts.append(f"{label}:\n{value}")
    structured_summary = "\n\n".join(summary_parts).strip()
    return {
        "cleaned_text": cleaned_text[:6000],
        "structured_summary": structured_summary[:2400],
        "sections": sections,
        "paragraphs": paragraphs[:40],
    }


def build_vision_review_prompt(module, document: dict, ocr_proposal: dict, existing_person_tags: list[str], content_chars: int) -> str:
    ocr_excerpt = module.truncate_text(document.get("content") or "", content_chars)
    ocr_structure = str(ocr_proposal.get("_ocr_structure_summary") or "").strip()
    ocr_hints = str(ocr_proposal.get("_ocr_hints_summary") or "").strip()
    return f"""Visueller Review fuer paperless-ngx.
Antworte nur als JSON.

Behalte den OCR-Vorschlag als Standard.
Pruefe nur diese Felder gezielt gegen das Seitenbild:
- `correspondent`
- `title`
- `document_type`

Korrigiere nur, wenn das Seitenbild klar bessere Hinweise liefert.
Nutze das Bild vor allem fuer Briefkopf, Adressfeld, Betreffzeile, Signatur und Dokumentart.
Fasse den Titel normal und knapp zusammen. Schreibe niemals Vorsaetze wie `Dokumententyp:` in den Titel.
Setze `correspondent` konservativ. Wenn Absender nicht klar lesbar ist, lasse den OCR-Wert stehen statt zu raten.
Lass `tags` leer, ausser das Bild liefert eine eindeutig bessere Korrektur.
`refined_excerpt` muss immer befuellt werden:
- 3 bis 6 kurze Zeilen
- nur klar lesbare Kernpunkte aus dem Seitenbild
- bevorzugt: Absender, Adressat, Datum, Betreff, Signatur
Keine neuen Personentags ausser aus dieser Liste: {", ".join(existing_person_tags) or "-"}

OCR-Vorschlag:
{json.dumps({"title": ocr_proposal.get("title", ""), "correspondent": ocr_proposal.get("correspondent", ""), "document_type": ocr_proposal.get("document_type", ""), "tags": ocr_proposal.get("tags", [])}, ensure_ascii=True)}

OCR-Struktur:
{ocr_structure or "-"}

Regelhinweise:
{ocr_hints or "-"}

Kurzer OCR-Auszug:
{ocr_excerpt}

Antwortformat:
{{"title":"","correspondent":"","document_type":"","tags":[],"confidence":0.0,"reason":"","refined_excerpt":""}}
"""


def merge_hybrid_proposals(base: dict, vision: dict) -> dict:
    merged = dict(base)
    if vision.get("title"):
        merged["title"] = vision["title"]
    if vision.get("correspondent"):
        merged["correspondent"] = vision["correspondent"]
    if vision.get("document_type"):
        merged["document_type"] = vision["document_type"]
    merged["tags"] = list(base.get("tags", []))[:6]
    try:
        base_conf = float(base.get("confidence") or 0)
    except (TypeError, ValueError):
        base_conf = 0.0
    try:
        vision_conf = float(vision.get("confidence") or 0)
    except (TypeError, ValueError):
        vision_conf = 0.0
    merged["confidence"] = round(max(base_conf, vision_conf), 2)
    base_reason = str(base.get("reason") or "").strip()
    vision_reason = str(vision.get("reason") or "").strip()
    reasons = []
    if base_reason:
        reasons.append(f"OCR: {base_reason}")
    if vision_reason:
        reasons.append(f"Vision: {vision_reason}")
    merged["reason"] = "\n".join(reasons)[:200]
    refined_excerpt = str(vision.get("refined_excerpt") or "").strip()
    if not refined_excerpt:
        refined_excerpt = str(base.get("_ocr_hints_summary") or "").strip()
    merged["_vision_refined_excerpt"] = refined_excerpt[:1200]
    return merged


def store_preview_job(job_id: str, payload: dict) -> None:
    with PREVIEW_JOBS_LOCK:
        PREVIEW_JOBS[job_id] = payload


def read_preview_job(job_id: str) -> dict | None:
    with PREVIEW_JOBS_LOCK:
        return PREVIEW_JOBS.get(job_id)


def run_hybrid_vision_review(job_id: str, document: dict, proposal: dict, existing_person_tags: list[str], preview_config: dict[str, str]) -> None:
    try:
        module = load_ai_hook_module()
        paperless_env = load_paperless_env()
        for key, value in paperless_env.items():
            os.environ[key] = value
        document_id = int(document.get("id"))
        pdf_bytes, content_type = fetch_paperless_document_binary(document_id)
        if not pdf_bytes:
            raise RuntimeError("downloaded file was empty")
        if content_type and "pdf" not in content_type.lower():
            raise RuntimeError(f"unexpected content type for PDF preview: {content_type or '-'}")
        image_payloads = render_pdf_preview_images(pdf_bytes, max_pages=1)
        review_prompt = build_vision_review_prompt(
            module,
            document,
            proposal,
            existing_person_tags,
            int(preview_config.get("vision_content_chars", "800")),
        )
        vision_raw, vision_meta = get_preview_response_details(
            module,
            review_prompt,
            image_payloads=image_payloads,
            model=preview_config.get("vision_model", "qwen3.5:0.8b"),
            timeout=float(preview_config.get("vision_timeout_seconds", "120")),
        )
        vision_proposal = module.refine_result(module.sanitize_result(vision_raw), document)
        merged = merge_hybrid_proposals(proposal, vision_proposal)
        try:
            merged, tag_meta = module.apply_tag_review(document, merged)
            merged["_tag_model"] = tag_meta.get("model", "")
        except Exception as exc:
            merged["_tag_model"] = ""
            merged["_tag_review_error"] = str(exc)
        review_needed, review_reasons = module.assess_review_flags(merged, document)
        merged["_review_needed"] = review_needed
        merged["_review_reasons"] = review_reasons
        merged["_model"] = proposal.get("_model", "")
        merged["_ocr_model"] = proposal.get("_ocr_model", proposal.get("_model", ""))
        merged["_fallback_used"] = bool(proposal.get("_fallback_used"))
        merged["_fallback_from"] = proposal.get("_fallback_from", "")
        merged["_vision_used"] = True
        merged["_vision_pages"] = len(image_payloads)
        merged["_vision_model"] = vision_meta.get("model", preview_config.get("vision_model", "qwen3.5:0.8b"))
        merged["_vision_error"] = ""
        merged["_hybrid_used"] = True
        merged["_hybrid_pending"] = False
        merged["_vision_requested"] = True
        store_preview_job(job_id, {"status": "done", "proposal": merged, "updated_at": time.time()})
    except Exception as exc:
        store_preview_job(job_id, {"status": "error", "error": str(exc), "updated_at": time.time()})


def load_ai_hook_module():
    hook_path = "/opt/paperless/ai_enrich.py"
    spec = importlib.util.spec_from_file_location("paperless_ai_hook", hook_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load hook module from {hook_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def call_ollama_preview(module, prompt: str, image_payloads: list[str] | None, model: str, timeout: float) -> dict:
    host = module.env("PAPERLESS_AI_OLLAMA_URL", "http://127.0.0.1:11434")
    client = module.HttpClient(host)
    user_message: dict[str, object] = {"role": "user", "content": prompt}
    if image_payloads:
        user_message["images"] = image_payloads
    num_thread = ollama_num_thread()
    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"num_thread": num_thread},
        "messages": [
            {"role": "system", "content": "Du gibst ausschliesslich valides JSON aus."},
            user_message,
        ],
    }
    if model.startswith("qwen3.5:"):
        think_enabled = module.env("PAPERLESS_AI_QWEN35_THINK", "false").lower() in ("1", "true", "yes", "on")
        payload["think"] = think_enabled
    response = client.post("/api/chat", payload, timeout=timeout)
    if not isinstance(response, dict):
        raise RuntimeError("Unexpected Ollama response")
    message = response.get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError("Ollama response did not contain message.content")
    return module.parse_json_object(content)


def get_preview_response_details(module, prompt: str, image_payloads: list[str] | None = None, model: str | None = None, timeout: float | None = None) -> tuple[dict, dict]:
    if not image_payloads:
        if model is None and timeout is None:
            return module.get_provider_response_details(prompt)
        provider = module.env("PAPERLESS_AI_PROVIDER", "ollama").lower()
        if provider != "ollama":
            return module.get_provider_response_details(prompt)
        primary_model = model or module.env("PAPERLESS_AI_OLLAMA_MODEL", "qwen2.5:7b-instruct")
        primary_timeout = timeout if timeout is not None else float(module.env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "300"))
        return call_ollama_preview(module, prompt, None, primary_model, primary_timeout), {
            "provider": "ollama",
            "model": primary_model,
            "fallback_used": False,
            "timeout_seconds": primary_timeout,
        }
    provider = module.env("PAPERLESS_AI_PROVIDER", "ollama").lower()
    if provider != "ollama":
        response, meta = module.get_provider_response_details(prompt)
        meta["vision_error"] = f"Vision preview is only implemented for Ollama, active provider is {provider}"
        return response, meta
    primary_model = model or module.env("PAPERLESS_AI_OLLAMA_MODEL", "qwen2.5:7b-instruct")
    primary_timeout = timeout if timeout is not None else float(module.env("PAPERLESS_AI_HTTP_TIMEOUT_SECONDS", "300"))
    fallback_enabled = module.env("PAPERLESS_AI_FALLBACK_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    fallback_model = module.env("PAPERLESS_AI_FALLBACK_MODEL", "qwen2.5:3b-instruct")
    fallback_timeout = float(module.env("PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS", str(primary_timeout)))
    fallback_timeout_only = module.env("PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY", "true").lower() in ("1", "true", "yes", "on")
    try:
        return call_ollama_preview(module, prompt, image_payloads, primary_model, primary_timeout), {
            "provider": "ollama",
            "model": primary_model,
            "fallback_used": False,
            "timeout_seconds": primary_timeout,
        }
    except Exception as exc:
        if not fallback_enabled:
            raise
        if fallback_timeout_only and not module.is_timeout_error(exc):
            raise
        module.warn(f"Primary preview model '{primary_model}' failed, using fallback '{fallback_model}': {exc}")
        return call_ollama_preview(module, prompt, image_payloads, fallback_model, fallback_timeout), {
            "provider": "ollama",
            "model": fallback_model,
            "fallback_used": True,
            "fallback_from": primary_model,
            "timeout_seconds": fallback_timeout,
        }


def build_ai_preview(document_id: int, use_vision: bool = False) -> tuple[int, dict]:
    module = load_ai_hook_module()
    paperless_env = load_paperless_env()
    preview_config = load_preview_config()
    api_url = paperless_env.get("PAPERLESS_API_URL")
    token = paperless_env.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        return 500, {"error": "Paperless API configuration is incomplete"}
    for key, value in paperless_env.items():
        os.environ[key] = value
    client = module.HttpClient(api_url, token)
    document = client.get(f"/api/documents/{document_id}/")
    if not isinstance(document, dict):
        return 500, {"error": f"Unexpected document payload: {document}"}
    existing_tags = module.list_all(client, "/api/tags/")
    existing_person_tags = [
        str(tag.get("name", ""))
        for tag in existing_tags
        if isinstance(tag, dict) and module.looks_like_person_tag(str(tag.get("name", "")))
    ]
    ocr_view = build_structured_ocr_view(str(document.get("content") or ""))
    document_hints = derive_document_hints(ocr_view)
    prompt_document = dict(document)
    prompt_document["content"] = "\n\n".join(
        part for part in (
            document_hints.get("guidance_text", "").strip(),
            ocr_view.get("structured_summary", "").strip(),
            ocr_view.get("cleaned_text", "").strip(),
        ) if part
    ) or str(document.get("content") or "")
    prompt = build_document_prompt_with_limit(
        module,
        prompt_document,
        sorted(existing_person_tags, key=str.casefold),
        int(paperless_env.get("PAPERLESS_AI_CONTENT_CHARS", "5000") or "5000"),
    )
    started = time.time()
    preview_ocr_model = preview_config.get("preview_ocr_model", "") or None
    raw_result, response_meta = get_preview_response_details(module, prompt, model=preview_ocr_model)
    proposal = module.refine_result(module.sanitize_result(raw_result), document)
    proposal = apply_rule_based_preview_corrections(proposal, document_hints)
    try:
        proposal, tag_meta = module.apply_tag_review(document, proposal)
        proposal["_tag_model"] = tag_meta.get("model", "")
    except Exception as exc:
        proposal["_tag_model"] = ""
        proposal["_tag_review_error"] = str(exc)
    review_needed, review_reasons = module.assess_review_flags(proposal, document)
    proposal["_review_needed"] = review_needed
    proposal["_review_reasons"] = review_reasons
    proposal["_model"] = response_meta.get("model", "")
    proposal["_ocr_model"] = response_meta.get("model", "")
    proposal["_fallback_used"] = bool(response_meta.get("fallback_used"))
    proposal["_fallback_from"] = response_meta.get("fallback_from", "")
    proposal["_vision_used"] = False
    proposal["_vision_pages"] = 0
    proposal["_vision_error"] = ""
    proposal["_hybrid_used"] = False
    proposal["_vision_model"] = ""
    proposal["_hybrid_pending"] = False
    proposal["_vision_requested"] = False
    proposal["_vision_refined_excerpt"] = ""
    proposal["_ocr_cleaned_excerpt"] = str(ocr_view.get("cleaned_text") or "")[:1600]
    proposal["_ocr_structure_summary"] = str(ocr_view.get("structured_summary") or "")[:1600]
    proposal["_ocr_hints_summary"] = str(document_hints.get("guidance_text") or "")[:1200]
    preview_job = None
    if use_vision:
        proposal["_vision_requested"] = True
        original_name = str(document.get("original_file_name") or "").lower()
        if original_name.endswith(".pdf"):
            page_count = int(document.get("page_count") or 0)
            vision_max_pages = int(preview_config.get("vision_max_pages", "1"))
            if page_count and page_count > vision_max_pages:
                proposal["_vision_error"] = (
                    f"Vision-Review uebersprungen: {page_count} Seiten, Limit ist {vision_max_pages}"
                )
            else:
                preview_job_id = uuid.uuid4().hex
                proposal["_hybrid_pending"] = True
                preview_job = {"id": preview_job_id, "status": "pending"}
                store_preview_job(preview_job_id, {"status": "pending", "document_id": document_id, "created_at": time.time()})
                worker = threading.Thread(
                    target=run_hybrid_vision_review,
                    args=(preview_job_id, document, proposal.copy(), sorted(existing_person_tags, key=str.casefold), preview_config),
                    daemon=True,
                )
                worker.start()
        else:
            proposal["_vision_error"] = "Vision preview is currently only enabled for PDF documents"
    duration = round(time.time() - started, 2)
    return 200, {"proposal": proposal, "duration_s": duration, "preview_job": preview_job}


def apply_ai_preview(document_id: int, proposal: dict) -> tuple[int, dict]:
    module = load_ai_hook_module()
    paperless_env = load_paperless_env()
    preview_config = load_preview_config()
    api_url = paperless_env.get("PAPERLESS_API_URL")
    token = paperless_env.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        return 500, {"error": "Paperless API configuration is incomplete"}
    for key, value in paperless_env.items():
        os.environ[key] = value
    client = module.HttpClient(api_url, token)
    document = client.get(f"/api/documents/{document_id}/")
    if not isinstance(document, dict):
        return 500, {"error": f"Unexpected document payload: {document}"}
    result = module.refine_result(module.sanitize_result(proposal), document)
    try:
        result, _ = module.apply_tag_review(document, result)
    except Exception:
        pass
    review_needed, review_reasons = module.assess_review_flags(result, document)
    result["_review_needed"] = review_needed
    result["_review_reasons"] = review_reasons
    if not module.should_apply(result):
        return 400, {"error": "Proposal confidence below threshold"}
    payload: dict = {}
    if result["title"]:
        payload["title"] = result["title"]
    current_correspondent = document.get("correspondent")
    if result["correspondent"]:
        correspondent_id = module.ensure_named_object(client, "/api/correspondents/", result["correspondent"])
        if correspondent_id is not None:
            if not isinstance(current_correspondent, dict) or int(current_correspondent.get("id", 0)) != correspondent_id:
                payload["correspondent"] = correspondent_id
    current_doc_type = document.get("document_type")
    if result["document_type"]:
        doc_type_id = module.ensure_named_object(client, "/api/document_types/", result["document_type"])
        if doc_type_id is not None:
            if not isinstance(current_doc_type, dict) or int(current_doc_type.get("id", 0)) != doc_type_id:
                payload["document_type"] = doc_type_id
    current_tags = document.get("tags", [])
    current_tag_ids = [int(tag["id"]) for tag in current_tags if isinstance(tag, dict) and "id" in tag]
    combined_tag_ids = list(current_tag_ids)
    for tag_id in module.resolve_tag_ids(client, result["tags"], document.get("content") or ""):
        if tag_id not in combined_tag_ids:
            combined_tag_ids.append(tag_id)
    if result.get("_review_needed"):
        review_tag_id = module.ensure_named_object(
            client,
            "/api/tags/",
            paperless_env.get("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen"),
            {"color": paperless_env.get("PAPERLESS_AI_REVIEW_TAG_COLOR", "#7dd3fc")},
        )
        if review_tag_id is not None and review_tag_id not in combined_tag_ids:
            combined_tag_ids.append(review_tag_id)
    if proposal.get("_vision_used"):
        vision_tag_id = module.ensure_named_object(
            client,
            "/api/tags/",
            preview_config.get("vision_tag_name", "KI Vision"),
            {"color": preview_config.get("vision_tag_color", "#d97706")},
        )
        if vision_tag_id is not None and vision_tag_id not in combined_tag_ids:
            combined_tag_ids.append(vision_tag_id)
    if combined_tag_ids != current_tag_ids:
        payload["tags"] = combined_tag_ids
    if payload:
        client.patch(f"/api/documents/{document_id}/", payload)
    return 200, {"status": "ok", "applied": payload}


def set_paperless_model(model: str) -> tuple[int, dict]:
    clean_model = str(model or "").strip()
    if not clean_model:
        return 400, {"error": "model missing"}
    helper = Path(PAPERLESS_MODEL_HELPER)
    if not helper.is_file():
        return 500, {"error": f"Helper not found: {helper}"}
    result = subprocess.run(
        ["/usr/bin/sudo", str(helper), clean_model],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode != 0:
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        return 500, {"error": output or "model switch failed"}
    return 200, {"model": clean_model}


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
        "PAPERLESS_AI_FALLBACK_ENABLED",
        "PAPERLESS_AI_FALLBACK_MODEL",
        "PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY",
        "PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS",
        "PAPERLESS_AI_PROMPT_FILE",
        "PAPERLESS_AI_CONTENT_CHARS",
        "PAPERLESS_AI_MIN_CONFIDENCE",
        "PAPERLESS_AI_DEFAULT_TAG_COLOR",
        "PAPERLESS_AI_HTTP_TIMEOUT_SECONDS",
        "OPENAI_API_KEY",
        "PAPERLESS_AI_OPENAI_MODEL",
    ):
        if key in paperless_env:
            child_env[key] = paperless_env[key]

    cmd = ["/usr/bin/python3", PAPERLESS_BACKFILL]
    limit = int(payload.get("limit") or 0)
    from_id = int(payload.get("from_id") or 0)
    query = str(payload.get("query") or "").strip()
    document_ids = [int(doc_id) for doc_id in payload.get("document_ids", []) if int(doc_id) > 0]
    if payload.get("only_missing_metadata"):
        cmd.append("--only-missing-metadata")
    if limit > 0:
        cmd.extend(["--limit", str(limit)])
    if from_id > 0:
        cmd.extend(["--from-id", str(from_id)])
    if query:
        cmd.extend(["--query", query])
    for doc_id in document_ids:
        cmd.extend(["--document-id", str(doc_id)])
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
        if self.path.startswith("/api/paperless/preview-jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            payload = read_preview_job(job_id)
            if payload is None:
                self._send(404, json.dumps({"error": "Preview job not found"}).encode("utf-8"), "application/json")
                return
            self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path.startswith("/api/paperless/document/"):
            try:
                document_id = int(self.path.rsplit("/", 1)[-1])
                status, payload = fetch_paperless_document(document_id)
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path.startswith("/api/paperless/document/") and self.path.endswith("/preview"):
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        if self.path == "/api/paperless/config":
            try:
                status, payload = read_paperless_config()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/preview/config":
            try:
                status, payload = read_preview_config()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/paperless/prompt":
            try:
                status, payload = read_paperless_prompt()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path.startswith("/api/paperless/documents"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            query = (params.get("query") or [""])[0].strip() or None
            try:
                limit = int((params.get("limit") or ["40"])[0])
            except ValueError:
                limit = 40
            try:
                status, payload = fetch_paperless_documents(query, limit)
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/models":
            status, payload = ollama_request("/api/tags")
            if status == 200 and isinstance(payload, dict):
                try:
                    paperless_env = load_paperless_env()
                except Exception as exc:
                    payload["paperless_error"] = str(exc)
                else:
                    payload["paperless_model"] = paperless_env.get("PAPERLESS_AI_OLLAMA_MODEL", "")
                    payload["fallback_model"] = paperless_env.get("PAPERLESS_AI_FALLBACK_MODEL", "")
                names = [item.get("name") for item in payload.get("models", []) if isinstance(item, dict) and item.get("name")]
                if names:
                    payload["chat_model"] = names[0]
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.startswith("/api/paperless/document/") and self.path.endswith("/preview"):
            length = int(self.headers.get("Content-Length", "0"))
            payload = {}
            if length:
                raw = self.rfile.read(length)
                if raw:
                    payload = json.loads(raw.decode("utf-8"))
            try:
                document_id = int(self.path.split("/")[-2])
                status, response = build_ai_preview(document_id, bool(payload.get("use_vision")))
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
            self._send(status, json.dumps(response).encode("utf-8"), "application/json")
            return
        if self.path.startswith("/api/paperless/document/") and self.path.endswith("/apply"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                document_id = int(self.path.split("/")[-2])
                status, response = apply_ai_preview(document_id, payload.get("proposal") or {})
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
            self._send(status, json.dumps(response).encode("utf-8"), "application/json")
            return
        if self.path not in ("/api/chat", "/api/paperless/backfill", "/api/paperless/model", "/api/paperless/config", "/api/preview/config", "/api/paperless/prompt"):
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
            options = payload.get("options")
            if not isinstance(options, dict):
                options = {}
            options["num_thread"] = ollama_num_thread()
            payload["options"] = options
            status, response = ollama_request("/api/chat", payload)
        elif self.path == "/api/paperless/model":
            try:
                status, response = set_paperless_model(payload.get("model"))
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/paperless/config":
            try:
                status, response = save_paperless_config(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/preview/config":
            try:
                status, response = save_preview_config(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/paperless/prompt":
            try:
                status, response = save_paperless_prompt(payload.get("prompt"))
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
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
