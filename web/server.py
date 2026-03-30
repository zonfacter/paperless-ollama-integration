#!/usr/bin/env python3
import base64
import html
import json
import importlib.util
import math
import os
import re
import shlex
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
BACKFILL_STATE_PATH = os.getenv("PAPERLESS_BACKFILL_STATE_PATH", "/home/thomas/ollama-web/backfill_jobs.json")
PROVIDER_CONFIG_PATH = os.getenv("PAPERLESS_PROVIDER_CONFIG_PATH", "/home/thomas/ollama-web/provider_config.json")
MODEL_CONFIG_PATH = os.getenv("PAPERLESS_MODEL_CONFIG_PATH", "/home/thomas/ollama-web/model_config.json")
PADDLEOCR_API_INSTALL_SCRIPT = os.getenv(
    "PADDLEOCR_API_INSTALL_SCRIPT",
    "/home/hytale/paperless-ollama-integration/scripts/install-paddleocr-api.sh",
)
PREVIEW_JOBS: dict[str, dict] = {}
PREVIEW_JOBS_LOCK = threading.Lock()
BACKFILL_JOBS: dict[str, dict] = {}
BACKFILL_JOBS_LOCK = threading.Lock()
BACKFILL_LATEST_JOB_ID: str | None = None


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
      z-index: 20;
      pointer-events: auto;
    }
    .nav-card {
      position: relative;
      z-index: 21;
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
      position: relative;
      overflow: hidden;
      width: 100%;
      min-width: 0;
      text-align: left;
      padding: 15px 15px 15px 18px;
      border-radius: 20px;
      background: rgba(255,255,255,0.76);
      color: var(--ink);
      box-shadow: none;
      border: 1px solid var(--line);
      transition: background .18s ease, border-color .18s ease, box-shadow .18s ease, transform .18s ease;
    }
    .nav-btn::before {
      content: "";
      position: absolute;
      inset: 8px auto 8px 8px;
      width: 4px;
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(11, 107, 203, 0.18), rgba(14, 159, 110, 0.12));
      opacity: 0.75;
    }
    .nav-btn:hover:not(.active) {
      transform: translateY(-1px);
      box-shadow: 0 14px 28px rgba(15, 23, 40, 0.08);
      background: rgba(255,255,255,0.92);
      border-color: rgba(11, 107, 203, 0.16);
    }
    .nav-btn.active {
      background: linear-gradient(135deg, var(--accent), #2e89ea);
      color: white;
      border-color: transparent;
      box-shadow: 0 16px 30px rgba(11, 107, 203, 0.22);
    }
    .nav-btn.active::before {
      background: rgba(255,255,255,0.82);
      opacity: 1;
    }
    .nav-btn small {
      display: block;
      margin-top: 5px;
      opacity: 0.82;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0;
      line-height: 1.4;
    }
    .nav-btn[data-view-target="review-view"]::before {
      background: linear-gradient(180deg, rgba(14, 159, 110, 0.44), rgba(14, 159, 110, 0.16));
    }
    .nav-btn[data-view-target="tasks-view"]::before {
      background: linear-gradient(180deg, rgba(245, 158, 11, 0.46), rgba(245, 158, 11, 0.18));
    }
    .nav-btn[data-view-target="models-view"]::before {
      background: linear-gradient(180deg, rgba(11, 107, 203, 0.46), rgba(11, 107, 203, 0.18));
    }
    .nav-btn[data-view-target="providers-view"]::before {
      background: linear-gradient(180deg, rgba(99, 102, 241, 0.42), rgba(99, 102, 241, 0.16));
    }
    .nav-btn[data-view-target="control-view"]::before {
      background: linear-gradient(180deg, rgba(6, 148, 162, 0.42), rgba(6, 148, 162, 0.16));
    }
    .nav-btn[data-view-target="chat-view"]::before {
      background: linear-gradient(180deg, rgba(168, 85, 247, 0.42), rgba(168, 85, 247, 0.16));
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
      position: relative;
      z-index: 1;
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
    .provider-split {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 16px;
    }
    .provider-panel {
      display: grid;
      gap: 14px;
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      box-shadow: 0 16px 32px rgba(15, 23, 40, 0.06);
    }
    .provider-panel.local {
      background: linear-gradient(180deg, rgba(236, 253, 245, 0.94), rgba(255,255,255,0.92));
      border-color: rgba(14, 159, 110, 0.18);
    }
    .provider-panel.remote {
      background: linear-gradient(180deg, rgba(239, 246, 255, 0.94), rgba(255,255,255,0.92));
      border-color: rgba(11, 107, 203, 0.16);
    }
    .provider-panel-head {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: start;
    }
    .provider-panel-head h3 {
      margin: 0;
      font-size: 18px;
      letter-spacing: -0.02em;
    }
    .provider-panel-head p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }
    .provider-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 82px;
      padding: 7px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.88);
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .provider-badge.active {
      background: linear-gradient(135deg, var(--accent), #2e89ea);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(11, 107, 203, 0.18);
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 86px;
      padding: 7px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.88);
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .status-badge.running {
      background: linear-gradient(135deg, #0e9f6e, #2fb786);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(14, 159, 110, 0.18);
    }
    .status-badge.done {
      background: linear-gradient(135deg, #0b6bcb, #2e89ea);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(11, 107, 203, 0.18);
    }
    .status-badge.error {
      background: linear-gradient(135deg, #dc6803, #f79009);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(220, 104, 3, 0.18);
    }
    .status-badge.starting {
      background: linear-gradient(135deg, #667085, #98a2b3);
      color: white;
      border-color: transparent;
      box-shadow: 0 12px 24px rgba(102, 112, 133, 0.18);
    }
    .provider-diagram {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 42px minmax(0, 1fr) 42px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      margin-top: 18px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.94);
    }
    .flow-node {
      display: grid;
      gap: 8px;
      min-height: 92px;
      padding: 14px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(248,250,252,0.95);
      align-content: start;
    }
    .flow-node strong {
      font-size: 15px;
    }
    .flow-node span {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .flow-node.active {
      border-color: rgba(11, 107, 203, 0.22);
      background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(255,255,255,0.94));
      box-shadow: 0 14px 28px rgba(11, 107, 203, 0.10);
    }
    .flow-arrow {
      text-align: center;
      color: var(--muted);
      font-size: 24px;
      font-weight: 800;
      opacity: 0.75;
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
      .detail-grid,
      .provider-split,
      .provider-diagram {
        grid-template-columns: 1fr;
      }
      .flow-arrow {
        transform: rotate(90deg);
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
            <button class="nav-btn active" data-view-target="review-view" type="button">
              Review Workspace
              <small>Dokumente suchen, Vorschau erzeugen, KI-Vorschlag uebernehmen.</small>
            </button>
            <button class="nav-btn" data-view-target="tasks-view" type="button">
              Task Manager
              <small>Hintergrundjobs, Laufstatus und Logs ohne Shell verfolgen.</small>
            </button>
            <button class="nav-btn" data-view-target="models-view" type="button">
              Modelle
              <small>Rollen, Installationshilfe und lokale Modellquellen pflegen.</small>
            </button>
            <button class="nav-btn" data-view-target="providers-view" type="button">
              Provider
              <small>Lokale und externe KI-/OCR-Dienste anbinden und testen.</small>
            </button>
            <button class="nav-btn" data-view-target="control-view" type="button">
              Steuerung
              <small>Modelle, Prompt, OCR-Kontext, Timeout und Fallback verwalten.</small>
            </button>
            <button class="nav-btn" data-view-target="chat-view" type="button">
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
                <div class="provider-diagram">
                  <div class="flow-node active">
                    <strong>Dokumentauswahl</strong>
                    <span>Suche, Auswahl und Einzeldokument-Review direkt aus dem Archivbestand.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>KI-Vorschau</strong>
                    <span>OCR, Struktur, optionale Zusatzpfade und Metadatenvorschlag vor dem Schreiben.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Apply oder Batch</strong>
                    <span>Einzeln uebernehmen oder als Hintergrund-Backfill fuer viele Dokumente starten.</span>
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
                      <h3>PaddleOCR-Vorschau</h3>
                      <div class="detail-sub">Optionale zweite OCR-Quelle fuer Seite 1. Gut fuer Briefkoepfe, Umlaute und schwer lesbare Scanbereiche.</div>
                      <div id="doc-detail-paddle-ocr" class="ocr-box">Noch keine PaddleOCR-Vorschau vorhanden.</div>
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
                  <button id="backfill-clear-review" class="secondary">Hellblaue Review-Tags entfernen</button>
                  <button id="backfill-run">Backfill starten</button>
                  <button id="backfill-refresh-job" class="secondary">Job-Status aktualisieren</button>
                </div>
                <label class="check">
                  <input id="backfill-clear-review-first" type="checkbox">
                  Vor dem Start hellblaue Review-Tags entfernen
                  <small>Empfohlen fuer einen kompletten Neuaufbau. Der Lauf startet danach im Hintergrund und kann spaeter weiter verfolgt werden.</small>
                </label>
                <div id="backfill-status" class="statusline">__BACKFILL_STATUS__</div>
                <div id="backfill-log" class="logbox">__BACKFILL_LOG__</div>
              </div>
            </section>
            <section id="tasks-view" class="view">
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Task Manager</h2>
                    <p>
                      Ueberwache laufende und letzte Hintergrundjobs direkt im Browser. So kannst du
                      die Verbindung trennen und spaeter einfach wieder in den aktuellen Lauf einsteigen.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Backfill</span>
                    <span class="pill">Persistent</span>
                    <span class="pill">Ohne Shell</span>
                  </div>
                </div>
                <div class="provider-diagram">
                  <div class="flow-node active">
                    <strong>Start</strong>
                    <span>Backfill und groessere Nachlaeufe starten aus der Weboberflaeche im Hintergrund.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Ueberwachung</strong>
                    <span>Task Manager zeigt Jobstatus, letzte Aktivitaet, Fehlergrund und Systemlast.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Aktionen</strong>
                    <span>Jobs aktualisieren, abbrechen oder aus dem Task Manager entfernen ohne Shellzugriff.</span>
                  </div>
                </div>
                <div class="actions">
                  <button id="tasks-refresh" class="secondary">Aufgaben aktualisieren</button>
                  <button id="tasks-show-latest" class="secondary">Letzten Job laden</button>
                </div>
                <div id="tasks-status" class="statusline">Jobliste wird geladen...</div>
                <div class="detail-grid">
                  <div class="detail-card">
                    <h3>Systemlast</h3>
                    <div class="detail-sub">Live-Metriken fuer CPU, RAM, Datentraeger und GPU-Status dieser VM.</div>
                    <div id="tasks-system-metrics" class="meta-table">
                      <div class="doc-empty">Systemmetriken werden geladen...</div>
                    </div>
                  </div>
                </div>
                <div class="detail-grid">
                  <div class="detail-card">
                    <h3>Hintergrundjobs</h3>
                    <div class="detail-sub">Die neuesten Backfill-Laeufe mit Status, Dokumentanzahl und Startzeit.</div>
                    <div id="tasks-list" class="doc-list">
                      <div class="doc-empty">Noch keine Hintergrundjobs bekannt.</div>
                    </div>
                  </div>
                  <div class="detail-card">
                    <h3>Job-Details</h3>
                    <div class="detail-sub">Auswahl laden, aktuellen Fortschritt ansehen und direkt zum Log springen.</div>
                    <div id="tasks-detail-meta" class="meta-table">
                      <div class="doc-empty">Noch kein Job ausgewaehlt.</div>
                    </div>
                    <div class="actions">
                      <button id="tasks-refresh-selected" class="secondary">Ausgewaehlten Job aktualisieren</button>
                      <button id="tasks-cancel-selected" class="secondary">Ausgewaehlten Job abbrechen</button>
                      <button id="tasks-delete-selected" class="secondary">Aus Task Manager entfernen</button>
                    </div>
                    <div id="tasks-detail-log" class="logbox">Bereit.</div>
                  </div>
                </div>
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
                <div class="provider-diagram">
                  <div class="flow-node active">
                    <strong>Importpfad</strong>
                    <span>Das Primärmodell verarbeitet neue Dokumente und normale Backfills.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Fallback</strong>
                    <span>Greift optional bei Timeout oder spaeteren Sonderfaellen.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Review-Regeln</strong>
                    <span>Confidence, Tag-Regeln und Nachpruefungs-Tags steuern die Qualitaet.</span>
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
                    <div style="display:flex;gap:12px;align-items:center;">
                      <input id="cfg-tag-color-picker" type="color" value="#4f6bed" style="width:56px;height:44px;padding:4px;">
                      <input id="cfg-tag-color" type="text" placeholder="#4f6bed">
                    </div>
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
                    <label for="cfg-tag-rules-force">Harte Familienregeln</label>
                    <select id="cfg-tag-rules-force">
                      <option value="false">Aus</option>
                      <option value="true">Ein</option>
                    </select>
                    <small>Wenn aktiv, duerfen passende Familienregeln das Modell bei Tags direkt ueberstimmen. Standard ist bewusst aus.</small>
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
                    <div style="display:flex;gap:12px;align-items:center;">
                      <input id="cfg-review-tag-color-picker" type="color" value="#7dd3fc" style="width:56px;height:44px;padding:4px;">
                      <input id="cfg-review-tag-color" type="text" placeholder="#7dd3fc">
                    </div>
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
                    <label for="preview-ocr-source">OCR-Quelle fuer Vorschau</label>
                    <select id="preview-ocr-source">
                      <option value="paperless">Paperless OCR</option>
                      <option value="paddleocr">PaddleOCR Seite 1</option>
                      <option value="hybrid">Hybrid: PaddleOCR + Paperless OCR</option>
                    </select>
                    <small>Legt fest, ob die Vorschau nur den bestehenden Paperless-OCR-Text, nur PaddleOCR fuer Seite 1 oder beide Quellen kombiniert nutzt.</small>
                  </div>
                  <div class="field">
                    <label for="preview-paddleocr-api-url">PaddleOCR API URL</label>
                    <input id="preview-paddleocr-api-url" type="text" placeholder="http://127.0.0.1:8091">
                    <small>Lokaler HTTP-Dienst fuer PaddleOCR. Die Vorschau fragt ihn nur an, wenn `PaddleOCR` oder `Hybrid` aktiv ist.</small>
                  </div>
                  <div class="field">
                    <label for="preview-paddleocr-timeout">PaddleOCR-Timeout in Sekunden</label>
                    <input id="preview-paddleocr-timeout" type="number" min="10" step="10">
                    <small>Wie lange auf die zweite OCR-Quelle gewartet wird. Bei Fehlern faellt die Vorschau auf Paperless OCR zurueck.</small>
                  </div>
                  <div class="field">
                    <label for="preview-paddleocr-max-pages">PaddleOCR nur bis Seitenzahl</label>
                    <input id="preview-paddleocr-max-pages" type="number" min="1" step="1">
                    <small>Begrenzt die zweite OCR-Quelle auf kurze PDFs. Laengere Dokumente bleiben bei Paperless OCR.</small>
                  </div>
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
                    <div style="display:flex;gap:12px;align-items:center;">
                      <input id="preview-vision-tag-color-picker" type="color" value="#d97706" style="width:56px;height:44px;padding:4px;">
                      <input id="preview-vision-tag-color" type="text" placeholder="#d97706">
                    </div>
                    <small>Hex-Farbe fuer den Vision-Zusatz-Tag, damit Vision-unterstuetzte Dokumente in Paperless sofort erkennbar sind.</small>
                  </div>
                </div>
                <div class="actions">
                  <button id="save-preview-config">Preview & Vision speichern</button>
                  <button id="reload-preview-config" class="secondary">Neu laden</button>
                  <button id="show-paddleocr-install" class="secondary">PaddleOCR Installationshilfe</button>
                </div>
                <div id="preview-config-status" class="statusline">Preview-Konfiguration noch nicht geladen.</div>
                <div id="paddleocr-install-plan" class="logbox">Noch keine Installationshilfe geladen.</div>
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
            <section id="models-view" class="view">
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Modelle</h2>
                    <p>
                      Hier pflegst du die Rollen der Modelle, Installationshinweise und lokale Referenzen.
                      Die eigentliche Modellstrategie bleibt weiterhin unter `Steuerung`.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">Lokale Bibliothek</span>
                    <span class="pill">Installationshilfe</span>
                    <span class="pill">Provider-faehig</span>
                  </div>
                </div>
                <div class="provider-diagram">
                  <div class="flow-node active">
                    <strong>Bibliothek</strong>
                    <span>Modelle, Rollen und Referenzlinks fuer Import, Preview, Tag-Review und Chat.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Installation</strong>
                    <span>Lokale VM-Installation oder spaeter externe Modellquellen per Provider.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div class="flow-node active">
                    <strong>Zuweisung</strong>
                    <span>Die eigentliche Aktivierung passiert weiter ueber Modellstrategie und Preview-Konfiguration.</span>
                  </div>
                </div>
                <div class="provider-split">
                  <div class="provider-panel local">
                    <div class="provider-panel-head">
                      <div>
                        <h3>Lokale Modellbibliothek</h3>
                        <p>Pflegt Modellrollen, Provider-Referenzen und spaetere NAS-kompatible Zuordnungen.</p>
                      </div>
                      <span class="provider-badge active">Lokal</span>
                    </div>
                    <div class="field">
                      <label for="model-library-json">Modellbibliothek (JSON)</label>
                      <textarea id="model-library-json" class="prompt-box" style="min-height:260px" placeholder='[{"name":"qwen3.5:9b","role":"paperless_primary","provider":"ollama_local","homepage":"https://ollama.com/library/qwen3.5:9b"}]'></textarea>
                      <small>Lokale Bibliothek fuer Modelle, Rollen und Referenzlinks. Diese Datei bleibt lokal und kann spaeter auf dem NAS weitergefuehrt werden.</small>
                    </div>
                  </div>
                  <div class="provider-panel remote">
                    <div class="provider-panel-head">
                      <div>
                        <h3>Installation & externe Referenzen</h3>
                        <p>Lokaler Pull fuer die VM und gleichzeitig saubere Referenz auf spaetere NAS-/Remote-Quellen.</p>
                      </div>
                      <span class="provider-badge">Hybrid</span>
                    </div>
                    <div class="config-grid">
                      <div class="field">
                        <label for="model-install-name">Lokales Ollama-Modell installieren</label>
                        <input id="model-install-name" type="text" placeholder="qwen3.5:4b">
                        <small>Einfacher lokaler Installationspfad fuer die native VM. Nutzt `ollama pull` auf dem aktuellen Host.</small>
                      </div>
                      <div class="field">
                        <label for="model-install-link">Externer Modell-Link</label>
                        <input id="model-install-link" type="text" placeholder="https://ollama.com/library/qwen3.5:4b">
                        <small>Nur als Referenz/Installationshilfe. So bleibt spaeter auch ein externer NAS-Workflow dokumentiert.</small>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="actions">
                  <button id="save-model-config">Modellbibliothek speichern</button>
                  <button id="reload-model-config" class="secondary">Neu laden</button>
                  <button id="install-local-model" class="secondary">Lokal installieren</button>
                </div>
                <div id="model-config-status" class="statusline">Modellbereich noch nicht geladen.</div>
                <div id="model-install-output" class="logbox">Noch keine Installationsausgabe.</div>
              </div>
            </section>
            <section id="providers-view" class="view">
              <div class="section">
                <div class="section-head">
                  <div>
                    <h2>Provider</h2>
                    <p>
                      Bereite lokale und externe KI-/OCR-Dienste vor. So bleibt die VM-Weboberflaeche
                      kompatibel mit spaeteren NAS- oder Remote-Docker-Setups.
                    </p>
                  </div>
                  <div class="summary-bar">
                    <span class="pill">ollama local</span>
                    <span class="pill">ollama remote</span>
                    <span class="pill">OCR API</span>
                  </div>
                </div>
                <div class="provider-diagram">
                  <div class="flow-node active">
                    <strong>Paperless AI Web</strong>
                    <span>Steuerung, Review, Task Manager und spaetere Modellrollen.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div id="provider-diagram-ollama" class="flow-node">
                    <strong>LLM-Pfad</strong>
                    <span>Lokales oder externes `ollama` fuer Titel, Typ, Tags und Chat.</span>
                  </div>
                  <div class="flow-arrow">→</div>
                  <div id="provider-diagram-ocr" class="flow-node">
                    <strong>OCR-Zusatzpfad</strong>
                    <span>Lokale oder externe OCR-API fuer schwierige Dokumente und Zusatzpruefung.</span>
                  </div>
                </div>
                <div class="provider-split">
                  <div class="provider-panel local">
                    <div class="provider-panel-head">
                      <div>
                        <h3>Lokale Provider</h3>
                        <p>Alles, was direkt auf dieser VM oder spaeter lokal im Docker-Stack laeuft.</p>
                      </div>
                      <span id="provider-local-badge" class="provider-badge">Passiv</span>
                    </div>
                    <div class="config-grid">
                      <div class="field">
                        <label for="provider-active-ollama">Aktiver Ollama-Provider</label>
                        <select id="provider-active-ollama">
                          <option value="local">Lokal</option>
                          <option value="remote">Remote</option>
                        </select>
                        <small>Steuert, ob die Oberflaeche lokal oder spaeter extern priorisiert arbeitet.</small>
                      </div>
                      <div class="field">
                        <label for="provider-local-ollama-url">Lokale Ollama-URL</label>
                        <input id="provider-local-ollama-url" type="text" placeholder="http://127.0.0.1:11434">
                        <small>Native VM oder spaeter lokaler Docker-Dienst.</small>
                      </div>
                      <div class="field">
                        <label for="provider-active-ocr">Aktiver OCR-Zusatzpfad</label>
                        <select id="provider-active-ocr">
                          <option value="local">Lokal</option>
                          <option value="remote">Remote</option>
                        </select>
                        <small>Bereitet die Trennung lokal vs. extern schon jetzt vor.</small>
                      </div>
                      <div class="field">
                        <label for="provider-local-ocr-url">Lokale OCR-API URL</label>
                        <input id="provider-local-ocr-url" type="text" placeholder="http://127.0.0.1:8091">
                        <small>Aktueller lokaler `PaddleOCR`- oder spaeter anderer OCR-Dienst.</small>
                      </div>
                    </div>
                  </div>
                  <div class="provider-panel remote">
                    <div class="provider-panel-head">
                      <div>
                        <h3>Externe Provider</h3>
                        <p>Vorbereitung fuer NAS, Remote-Docker oder andere Hosts im LAN.</p>
                      </div>
                      <span id="provider-remote-badge" class="provider-badge">Passiv</span>
                    </div>
                    <div class="config-grid">
                      <div class="field">
                        <label for="provider-remote-ollama-url">Externe Ollama-URL</label>
                        <input id="provider-remote-ollama-url" type="text" placeholder="http://nas-host:11434">
                        <small>Fuer spaetere NAS- oder andere Docker-Hosts im LAN.</small>
                      </div>
                      <div class="field">
                        <label for="provider-remote-ocr-url">Externe OCR-API URL</label>
                        <input id="provider-remote-ocr-url" type="text" placeholder="http://nas-host:8091">
                        <small>Vorbereitung fuer OCR-Docker ausserhalb dieser VM.</small>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="actions">
                  <button id="save-provider-config">Provider speichern</button>
                  <button id="reload-provider-config" class="secondary">Neu laden</button>
                  <button id="test-provider-config" class="secondary">Provider testen</button>
                </div>
                <div id="provider-config-status" class="statusline">Providerbereich noch nicht geladen.</div>
                <div id="provider-test-output" class="logbox">Noch kein Verbindungstest ausgefuehrt.</div>
              </div>
            </section>
            <section id="chat-view" class="view">
              <div class="provider-diagram" style="margin: 22px 22px 0;">
                <div class="flow-node active">
                  <strong>Browser</strong>
                  <span>Direkte Modelltests ohne Paperless-Job und ohne Metadaten-Schreibpfad.</span>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-node active">
                  <strong>Aktives Chat-Modell</strong>
                  <span>Nutze lokale Modelle fuer schnelle Tests oder spaeter externe Provider.</span>
                </div>
                <div class="flow-arrow">→</div>
                <div class="flow-node active">
                  <strong>Antwort</strong>
                  <span>Ideal fuer Modellvergleich, Prompttests und schnelle Gegenproben.</span>
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
    const cfgTagColorPickerEl = document.getElementById('cfg-tag-color-picker');
    const cfgTagReviewModelEl = document.getElementById('cfg-tag-review-model');
    const cfgTagReviewTimeoutEl = document.getElementById('cfg-tag-review-timeout');
    const cfgTagRulesForceEl = document.getElementById('cfg-tag-rules-force');
    const cfgReviewMinConfidenceEl = document.getElementById('cfg-review-min-confidence');
    const cfgReviewTagNameEl = document.getElementById('cfg-review-tag-name');
    const cfgReviewTagColorEl = document.getElementById('cfg-review-tag-color');
    const cfgReviewTagColorPickerEl = document.getElementById('cfg-review-tag-color-picker');
    const cfgTagAllowlistsEl = document.getElementById('cfg-tag-allowlists');
    const cfgTagRulesEl = document.getElementById('cfg-tag-rules');
    const saveAiConfigBtn = document.getElementById('save-ai-config');
    const reloadAiConfigBtn = document.getElementById('reload-ai-config');
    const aiConfigStatusEl = document.getElementById('ai-config-status');
    const previewOcrModelEl = document.getElementById('preview-ocr-model');
    const previewOcrSourceEl = document.getElementById('preview-ocr-source');
    const previewPaddleApiUrlEl = document.getElementById('preview-paddleocr-api-url');
    const previewPaddleTimeoutEl = document.getElementById('preview-paddleocr-timeout');
    const previewPaddleMaxPagesEl = document.getElementById('preview-paddleocr-max-pages');
    const previewVisionModelEl = document.getElementById('preview-vision-model');
    const previewVisionContentCharsEl = document.getElementById('preview-vision-content-chars');
    const previewVisionTimeoutEl = document.getElementById('preview-vision-timeout');
    const previewVisionMaxPagesEl = document.getElementById('preview-vision-max-pages');
    const previewVisionTagNameEl = document.getElementById('preview-vision-tag-name');
    const previewVisionTagColorEl = document.getElementById('preview-vision-tag-color');
    const previewVisionTagColorPickerEl = document.getElementById('preview-vision-tag-color-picker');
    const savePreviewConfigBtn = document.getElementById('save-preview-config');
    const reloadPreviewConfigBtn = document.getElementById('reload-preview-config');
    const showPaddleOcrInstallBtn = document.getElementById('show-paddleocr-install');
    const previewConfigStatusEl = document.getElementById('preview-config-status');
    const paddleOcrInstallPlanEl = document.getElementById('paddleocr-install-plan');
    const promptEditorEl = document.getElementById('prompt-editor');
    const savePromptBtn = document.getElementById('save-prompt');
    const reloadPromptBtn = document.getElementById('reload-prompt');
    const promptStatusEl = document.getElementById('prompt-status');
    const backfillLimitEl = document.getElementById('backfill-limit');
    const backfillQueryEl = document.getElementById('backfill-query');
    const backfillFromIdEl = document.getElementById('backfill-from-id');
    const backfillPreviewBtn = document.getElementById('backfill-preview');
    const backfillClearReviewBtn = document.getElementById('backfill-clear-review');
    const backfillRunBtn = document.getElementById('backfill-run');
    const backfillRefreshJobBtn = document.getElementById('backfill-refresh-job');
    const backfillClearReviewFirstEl = document.getElementById('backfill-clear-review-first');
    const backfillStatusEl = document.getElementById('backfill-status');
    const backfillLogEl = document.getElementById('backfill-log');
    const tasksRefreshBtn = document.getElementById('tasks-refresh');
    const tasksShowLatestBtn = document.getElementById('tasks-show-latest');
    const tasksRefreshSelectedBtn = document.getElementById('tasks-refresh-selected');
    const tasksCancelSelectedBtn = document.getElementById('tasks-cancel-selected');
    const tasksDeleteSelectedBtn = document.getElementById('tasks-delete-selected');
    const tasksStatusEl = document.getElementById('tasks-status');
    const tasksListEl = document.getElementById('tasks-list');
    const tasksDetailMetaEl = document.getElementById('tasks-detail-meta');
    const tasksDetailLogEl = document.getElementById('tasks-detail-log');
    const tasksSystemMetricsEl = document.getElementById('tasks-system-metrics');
    const docSearchEl = document.getElementById('doc-search');
    const docLimitEl = document.getElementById('doc-limit');
    const docRefreshBtn = document.getElementById('doc-refresh');
    const docClearSelectionBtn = document.getElementById('doc-clear-selection');
    const docListEl = document.getElementById('doc-list');
    const docSelectionInfoEl = document.getElementById('doc-selection-info');
    const docDetailMetaEl = document.getElementById('doc-detail-meta');
    const docDetailOcrEl = document.getElementById('doc-detail-ocr');
    const docDetailPaddleOcrEl = document.getElementById('doc-detail-paddle-ocr');
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
    const modelLibraryJsonEl = document.getElementById('model-library-json');
    const modelInstallNameEl = document.getElementById('model-install-name');
    const modelInstallLinkEl = document.getElementById('model-install-link');
    const saveModelConfigBtn = document.getElementById('save-model-config');
    const reloadModelConfigBtn = document.getElementById('reload-model-config');
    const installLocalModelBtn = document.getElementById('install-local-model');
    const modelConfigStatusEl = document.getElementById('model-config-status');
    const modelInstallOutputEl = document.getElementById('model-install-output');
    const providerActiveOllamaEl = document.getElementById('provider-active-ollama');
    const providerLocalOllamaUrlEl = document.getElementById('provider-local-ollama-url');
    const providerRemoteOllamaUrlEl = document.getElementById('provider-remote-ollama-url');
    const providerActiveOcrEl = document.getElementById('provider-active-ocr');
    const providerLocalOcrUrlEl = document.getElementById('provider-local-ocr-url');
    const providerRemoteOcrUrlEl = document.getElementById('provider-remote-ocr-url');
    const providerLocalBadgeEl = document.getElementById('provider-local-badge');
    const providerRemoteBadgeEl = document.getElementById('provider-remote-badge');
    const providerDiagramOllamaEl = document.getElementById('provider-diagram-ollama');
    const providerDiagramOcrEl = document.getElementById('provider-diagram-ocr');
    const saveProviderConfigBtn = document.getElementById('save-provider-config');
    const reloadProviderConfigBtn = document.getElementById('reload-provider-config');
    const testProviderConfigBtn = document.getElementById('test-provider-config');
    const providerConfigStatusEl = document.getElementById('provider-config-status');
    const providerTestOutputEl = document.getElementById('provider-test-output');
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
    let activeBackfillJobId = null;
    let activeTaskJobId = null;
    let availableModelNames = [];
    const cfgTagColorControl = bindColorInput(cfgTagColorEl, cfgTagColorPickerEl, '#4f6bed');
    const cfgReviewTagColorControl = bindColorInput(cfgReviewTagColorEl, cfgReviewTagColorPickerEl, '#7dd3fc');
    const previewVisionTagColorControl = bindColorInput(previewVisionTagColorEl, previewVisionTagColorPickerEl, '#d97706');

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

    function normalizeHexColor(value, fallback) {
      const raw = String(value || '').trim();
      if (/^#[0-9a-fA-F]{6}$/.test(raw)) return raw.toLowerCase();
      if (/^[0-9a-fA-F]{6}$/.test(raw)) return `#${raw.toLowerCase()}`;
      return fallback;
    }

    function bindColorInput(textEl, pickerEl, fallback) {
      const syncFromText = () => {
        pickerEl.value = normalizeHexColor(textEl.value, fallback);
      };
      const syncFromPicker = () => {
        textEl.value = pickerEl.value;
      };
      textEl.addEventListener('input', syncFromText);
      pickerEl.addEventListener('input', syncFromPicker);
      syncFromText();
      return {
        set(value) {
          textEl.value = value || '';
          syncFromText();
        }
      };
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
      docDetailPaddleOcrEl.textContent = 'Noch keine PaddleOCR-Vorschau vorhanden.';
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
        docDetailPaddleOcrEl.textContent = 'Noch keine PaddleOCR-Vorschau vorhanden.';
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
        <div class="meta-row"><div class="meta-label">OCR-Quelle</div><div>${formatValue(proposal._ocr_source || 'paperless')}</div></div>
        <div class="meta-row"><div class="meta-label">OCR-Modell</div><div>${formatValue(proposal._ocr_model || proposal._model)}</div></div>
        <div class="meta-row"><div class="meta-label">PaddleOCR</div><div>${proposal._paddle_ocr_used ? `ja, ${proposal._paddle_ocr_seconds || '-'}s` : proposal._paddle_ocr_error ? 'fehlerhaft' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Vision-Modell</div><div>${proposal._vision_used ? formatValue(proposal._vision_model) : '-'}</div></div>
        <div class="meta-row"><div class="meta-label">Vision</div><div>${proposal._vision_used ? `ja, ${proposal._vision_pages || 0} Seite(n)` : proposal._hybrid_pending ? 'laeuft' : proposal._vision_requested ? 'angefragt' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Review</div><div>${proposal._review_needed ? 'ja' : 'nein'}</div></div>
        <div class="meta-row"><div class="meta-label">Review-Gruende</div><div>${formatValue(proposal._review_reasons)}</div></div>
      `;
      docProposalReasonEl.textContent = proposal.reason || '-';
      if (proposal._paddle_ocr_error) {
        docProposalReasonEl.textContent += `\n\nPaddleOCR-Hinweis: ${proposal._paddle_ocr_error}`;
      }
      if (proposal._vision_error) {
        docProposalReasonEl.textContent += `\n\nVision-Hinweis: ${proposal._vision_error}`;
      }
      docDetailPaddleOcrEl.textContent = proposal._paddle_ocr_excerpt || 'Noch keine PaddleOCR-Vorschau vorhanden.';
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
        cfgTagColorControl.set(data.default_tag_color || '');
        if (data.tag_review_model && availableModelNames.includes(data.tag_review_model)) {
          cfgTagReviewModelEl.value = data.tag_review_model;
        }
        cfgTagReviewTimeoutEl.value = data.tag_review_timeout_seconds || '';
        cfgTagRulesForceEl.value = data.tag_rules_force || 'false';
        cfgReviewMinConfidenceEl.value = data.review_min_confidence || '';
        cfgReviewTagNameEl.value = data.review_tag_name || '';
        cfgReviewTagColorControl.set(data.review_tag_color || '');
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
            tag_rules_force: cfgTagRulesForceEl.value,
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
        previewOcrSourceEl.value = data.ocr_source || 'paperless';
        previewPaddleApiUrlEl.value = data.paddleocr_api_url || '';
        previewPaddleTimeoutEl.value = data.paddleocr_timeout_seconds || '';
        previewPaddleMaxPagesEl.value = data.paddleocr_max_pages || '';
        if (data.vision_model && availableModelNames.includes(data.vision_model)) {
          previewVisionModelEl.value = data.vision_model;
        }
        previewVisionContentCharsEl.value = data.vision_content_chars || '';
        previewVisionTimeoutEl.value = data.vision_timeout_seconds || '';
        previewVisionMaxPagesEl.value = data.vision_max_pages || '';
        previewVisionTagNameEl.value = data.vision_tag_name || '';
        previewVisionTagColorControl.set(data.vision_tag_color || '');
        previewConfigStatusEl.textContent = 'Preview-Konfiguration geladen.';
      } catch (err) {
        previewConfigStatusEl.textContent = `Fehler: ${err.message}`;
        previewConfigStatusEl.className = 'statusline warn';
      }
    }

    async function loadModelConfig() {
      modelConfigStatusEl.textContent = 'Modellbereich wird geladen...';
      modelConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/models/config');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        modelLibraryJsonEl.value = data.library_json || '';
        modelConfigStatusEl.textContent = 'Modellbereich geladen.';
      } catch (err) {
        modelConfigStatusEl.textContent = `Fehler: ${err.message}`;
        modelConfigStatusEl.className = 'statusline warn';
      }
    }

    async function saveModelConfigUi() {
      saveModelConfigBtn.disabled = true;
      modelConfigStatusEl.textContent = 'Modellbibliothek wird gespeichert...';
      modelConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/models/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ library_json: modelLibraryJsonEl.value })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        modelConfigStatusEl.textContent = 'Modellbibliothek gespeichert.';
      } catch (err) {
        modelConfigStatusEl.textContent = `Fehler: ${err.message}`;
        modelConfigStatusEl.className = 'statusline warn';
      } finally {
        saveModelConfigBtn.disabled = false;
      }
    }

    async function installLocalModelUi() {
      const modelName = modelInstallNameEl.value.trim();
      if (!modelName) {
        modelConfigStatusEl.textContent = 'Bitte ein Modell fuer die Installation eintragen.';
        modelConfigStatusEl.className = 'statusline warn';
        return;
      }
      installLocalModelBtn.disabled = true;
      modelConfigStatusEl.textContent = `Lokale Installation fuer ${modelName} laeuft...`;
      modelConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/models/install', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ model: modelName, link: modelInstallLinkEl.value.trim() })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        modelInstallOutputEl.textContent = [
          `Modell: ${data.model || modelName}`,
          `Returncode: ${data.returncode}`,
          data.stdout || '',
          data.stderr || '',
          modelInstallLinkEl.value.trim() ? `Referenzlink: ${modelInstallLinkEl.value.trim()}` : ''
        ].filter(Boolean).join('\\n\\n');
        modelInstallOutputEl.scrollTop = modelInstallOutputEl.scrollHeight;
        modelConfigStatusEl.textContent = `Lokale Installation fuer ${modelName} abgeschlossen.`;
        await loadModels();
      } catch (err) {
        modelInstallOutputEl.textContent = `Fehler: ${err.message}`;
        modelConfigStatusEl.textContent = 'Fehler bei der lokalen Installation.';
        modelConfigStatusEl.className = 'statusline warn';
      } finally {
        installLocalModelBtn.disabled = false;
      }
    }

    async function loadProviderConfigUi() {
      providerConfigStatusEl.textContent = 'Providerbereich wird geladen...';
      providerConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/providers/config');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        providerActiveOllamaEl.value = data.active_ollama_provider || 'local';
        providerLocalOllamaUrlEl.value = data.local_ollama_url || '';
        providerRemoteOllamaUrlEl.value = data.remote_ollama_url || '';
        providerActiveOcrEl.value = data.active_ocr_provider || 'local';
        providerLocalOcrUrlEl.value = data.local_ocr_url || '';
        providerRemoteOcrUrlEl.value = data.remote_ocr_url || '';
        const localActive = providerActiveOllamaEl.value === 'local' || providerActiveOcrEl.value === 'local';
        const remoteActive = providerActiveOllamaEl.value === 'remote' || providerActiveOcrEl.value === 'remote';
        providerLocalBadgeEl.textContent = localActive ? 'Aktiv' : 'Passiv';
        providerRemoteBadgeEl.textContent = remoteActive ? 'Aktiv' : 'Passiv';
        providerLocalBadgeEl.classList.toggle('active', localActive);
        providerRemoteBadgeEl.classList.toggle('active', remoteActive);
        providerDiagramOllamaEl.classList.toggle('active', providerActiveOllamaEl.value === 'local' || providerActiveOllamaEl.value === 'remote');
        providerDiagramOllamaEl.querySelector('span').textContent = providerActiveOllamaEl.value === 'local'
          ? 'Aktiv ueber lokales Ollama auf dieser VM.'
          : 'Aktiv ueber externes Ollama, z. B. spaeter auf dem NAS.';
        providerDiagramOcrEl.classList.toggle('active', providerActiveOcrEl.value === 'local' || providerActiveOcrEl.value === 'remote');
        providerDiagramOcrEl.querySelector('span').textContent = providerActiveOcrEl.value === 'local'
          ? 'Aktiv ueber lokale OCR-API auf dieser VM.'
          : 'Aktiv ueber externe OCR-API ausserhalb dieser VM.';
        providerConfigStatusEl.textContent = 'Providerbereich geladen.';
      } catch (err) {
        providerConfigStatusEl.textContent = `Fehler: ${err.message}`;
        providerConfigStatusEl.className = 'statusline warn';
      }
    }

    async function saveProviderConfigUi() {
      saveProviderConfigBtn.disabled = true;
      providerConfigStatusEl.textContent = 'Provider werden gespeichert...';
      providerConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/providers/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            active_ollama_provider: providerActiveOllamaEl.value,
            local_ollama_url: providerLocalOllamaUrlEl.value.trim(),
            remote_ollama_url: providerRemoteOllamaUrlEl.value.trim(),
            active_ocr_provider: providerActiveOcrEl.value,
            local_ocr_url: providerLocalOcrUrlEl.value.trim(),
            remote_ocr_url: providerRemoteOcrUrlEl.value.trim()
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        providerConfigStatusEl.textContent = 'Provider gespeichert.';
      } catch (err) {
        providerConfigStatusEl.textContent = `Fehler: ${err.message}`;
        providerConfigStatusEl.className = 'statusline warn';
      } finally {
        saveProviderConfigBtn.disabled = false;
      }
    }

    async function testProviderConfigUi() {
      testProviderConfigBtn.disabled = true;
      providerConfigStatusEl.textContent = 'Provider-Test laeuft...';
      providerConfigStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/providers/test', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        providerTestOutputEl.textContent = JSON.stringify(data, null, 2);
        providerTestOutputEl.scrollTop = providerTestOutputEl.scrollHeight;
        providerConfigStatusEl.textContent = 'Provider-Test abgeschlossen.';
      } catch (err) {
        providerTestOutputEl.textContent = `Fehler: ${err.message}`;
        providerConfigStatusEl.textContent = 'Fehler beim Provider-Test.';
        providerConfigStatusEl.className = 'statusline warn';
      } finally {
        testProviderConfigBtn.disabled = false;
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
            ocr_source: previewOcrSourceEl.value,
            paddleocr_api_url: previewPaddleApiUrlEl.value.trim(),
            paddleocr_timeout_seconds: previewPaddleTimeoutEl.value.trim(),
            paddleocr_max_pages: previewPaddleMaxPagesEl.value.trim(),
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

    async function loadPaddleOcrInstallPlan() {
      paddleOcrInstallPlanEl.textContent = 'Installationshilfe wird geladen...';
      try {
        const res = await fetch('/api/paddleocr/install-plan');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        const lines = [];
        if (data.script) lines.push(`Skript: ${data.script}`);
        if (Array.isArray(data.commands)) {
          lines.push('');
          lines.push(...data.commands);
        }
        paddleOcrInstallPlanEl.textContent = lines.join('\\n') || 'Keine Installationshilfe vorhanden.';
      } catch (err) {
        paddleOcrInstallPlanEl.textContent = `Fehler: ${err.message}`;
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
        clear_review_tags_first: !dryRun && !!backfillClearReviewFirstEl.checked,
        mode
      };
    }

    function setBackfillJobState(jobId) {
      activeBackfillJobId = jobId || null;
      try {
        if (activeBackfillJobId) {
          localStorage.setItem('paperless-backfill-job-id', activeBackfillJobId);
        } else {
          localStorage.removeItem('paperless-backfill-job-id');
        }
      } catch (_) {}
    }

    function renderBackfillJob(job) {
      if (!job) {
        backfillStatusEl.textContent = 'Noch kein Hintergrund-Job bekannt.';
        backfillStatusEl.className = 'statusline';
        backfillLogEl.textContent = 'Bereit.';
        backfillLogEl.scrollTop = backfillLogEl.scrollHeight;
        return;
      }
      const prefix = job.document_count ? `${job.document_count} Dokumente` : 'Backfill-Job';
      if (job.status === 'running') {
        backfillStatusEl.textContent = `${prefix}: Hintergrundlauf aktiv (${job.id}).`;
        backfillStatusEl.className = 'statusline';
      } else if (job.status === 'done') {
        backfillStatusEl.textContent = `${prefix}: abgeschlossen (${job.id}).`;
        backfillStatusEl.className = 'statusline';
      } else if (job.status === 'error') {
        backfillStatusEl.textContent = `${prefix}: Fehler (${job.id}).`;
        backfillStatusEl.className = 'statusline warn';
      } else {
        backfillStatusEl.textContent = `${prefix}: ${job.status || 'unbekannt'} (${job.id}).`;
        backfillStatusEl.className = 'statusline';
      }
      const lines = [];
      lines.push(`Job-ID: ${job.id}`);
      if (job.started_at) lines.push(`Gestartet: ${job.started_at}`);
      if (job.finished_at) lines.push(`Beendet: ${job.finished_at}`);
      if (job.returncode !== undefined && job.returncode !== null) lines.push(`Returncode: ${job.returncode}`);
      if (job.log_path) lines.push(`Log: ${job.log_path}`);
      if (job.review_tag_name) lines.push(`Review-Tag: ${job.review_tag_name}`);
      if (job.clear_summary) lines.push(`Vorbereitung: ${job.clear_summary}`);
      if (job.tail) {
        lines.push('');
        lines.push(job.tail);
      }
      backfillLogEl.textContent = lines.join('\\n');
      backfillLogEl.scrollTop = backfillLogEl.scrollHeight;
    }

    function renderTaskJobList(jobs) {
      if (!Array.isArray(jobs) || !jobs.length) {
        tasksListEl.innerHTML = '<div class="doc-empty">Noch keine Hintergrundjobs bekannt.</div>';
        return;
      }
      tasksListEl.innerHTML = jobs.map(job => {
        const countText = job.document_count ? `${job.document_count} Dokumente` : 'Dokumentanzahl unbekannt';
        const startedText = job.started_at || 'Startzeit unbekannt';
        const statusText = job.status || 'unbekannt';
        const statusClass = String(statusText).toLowerCase().replace(/[^a-z0-9_-]/g, '');
        const activeClass = activeTaskJobId === job.id ? ' active' : '';
        return `
          <button class="doc-row${activeClass}" data-task-job-id="${job.id}" type="button">
            <div class="doc-main">
              <div class="doc-title">${job.id}</div>
              <div class="doc-meta">${countText} · ${startedText}</div>
              <div class="doc-meta"><span class="status-badge ${statusClass}">${statusText}</span></div>
            </div>
          </button>
        `;
      }).join('');
      tasksListEl.querySelectorAll('[data-task-job-id]').forEach(btn => {
        btn.addEventListener('click', () => loadBackfillJobStatus(btn.dataset.taskJobId));
      });
    }

    function renderTaskJobDetail(job) {
      if (!job) {
        tasksDetailMetaEl.innerHTML = '<div class="doc-empty">Noch kein Job ausgewaehlt.</div>';
        tasksDetailLogEl.textContent = 'Bereit.';
        tasksDetailLogEl.scrollTop = tasksDetailLogEl.scrollHeight;
        tasksCancelSelectedBtn.disabled = true;
        tasksDeleteSelectedBtn.disabled = true;
        return;
      }
      activeTaskJobId = job.id || null;
      tasksCancelSelectedBtn.disabled = !['running', 'starting'].includes(String(job.status || ''));
      tasksDeleteSelectedBtn.disabled = false;
      const detailStatus = String(job.status || 'unbekannt');
      const detailStatusClass = detailStatus.toLowerCase().replace(/[^a-z0-9_-]/g, '');
      tasksDetailMetaEl.innerHTML = `
        <div class="meta-row"><div class="meta-label">Job-ID</div><div>${formatValue(job.id)}</div></div>
        <div class="meta-row"><div class="meta-label">Status</div><div><span class="status-badge ${detailStatusClass}">${formatValue(job.status)}</span></div></div>
        <div class="meta-row"><div class="meta-label">Dokumente</div><div>${formatValue(job.document_count)}</div></div>
        <div class="meta-row"><div class="meta-label">Gestartet</div><div>${formatValue(job.started_at)}</div></div>
        <div class="meta-row"><div class="meta-label">Beendet</div><div>${formatValue(job.finished_at)}</div></div>
        <div class="meta-row"><div class="meta-label">Returncode</div><div>${formatValue(job.returncode)}</div></div>
        <div class="meta-row"><div class="meta-label">Fehlergrund</div><div>${formatValue(job.error_reason || job.error)}</div></div>
        <div class="meta-row"><div class="meta-label">Letzte Dokument-ID</div><div>${formatValue(job.last_document_id || job.last_analyzed_document_id)}</div></div>
        <div class="meta-row"><div class="meta-label">Letzte Aktivitaet</div><div>${formatValue(job.last_activity)}</div></div>
        <div class="meta-row"><div class="meta-label">Logdatei</div><div>${formatValue(job.log_path)}</div></div>
        <div class="meta-row"><div class="meta-label">Vorbereitung</div><div>${formatValue(job.clear_summary)}</div></div>
      `;
      const lines = [];
      if (job.tail) {
        lines.push(job.tail);
      } else {
        lines.push('Noch keine Logausgabe vorhanden.');
      }
      tasksDetailLogEl.textContent = lines.join('\\n');
      tasksDetailLogEl.scrollTop = tasksDetailLogEl.scrollHeight;
      renderTaskJobList(window.__taskJobsCache || []);
    }

    async function cancelSelectedTaskJob() {
      const jobId = activeTaskJobId || activeBackfillJobId;
      if (!jobId) {
        tasksStatusEl.textContent = 'Kein Job zum Abbrechen ausgewaehlt.';
        tasksStatusEl.className = 'statusline warn';
        return;
      }
      if (!window.confirm(`Hintergrundjob ${jobId} wirklich abbrechen?`)) {
        return;
      }
      tasksCancelSelectedBtn.disabled = true;
      tasksStatusEl.textContent = `Job ${jobId} wird abgebrochen...`;
      tasksStatusEl.className = 'statusline';
      try {
        const res = await fetch(`/api/paperless/backfill-jobs/${jobId}/cancel`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        tasksStatusEl.textContent = data.message || `Job ${jobId} wurde abgebrochen.`;
        await loadTaskJobs();
        await loadBackfillJobStatus(jobId);
      } catch (err) {
        tasksStatusEl.textContent = `Fehler beim Abbrechen: ${err.message}`;
        tasksStatusEl.className = 'statusline warn';
      } finally {
        tasksCancelSelectedBtn.disabled = false;
      }
    }

    async function deleteSelectedTaskJob() {
      const jobId = activeTaskJobId || activeBackfillJobId;
      if (!jobId) {
        tasksStatusEl.textContent = 'Kein Job zum Entfernen ausgewaehlt.';
        tasksStatusEl.className = 'statusline warn';
        return;
      }
      if (!window.confirm(`Job ${jobId} aus dem Task Manager entfernen? Die Logdatei wird dabei ebenfalls geloescht, wenn moeglich.`)) {
        return;
      }
      tasksDeleteSelectedBtn.disabled = true;
      tasksStatusEl.textContent = `Job ${jobId} wird entfernt...`;
      tasksStatusEl.className = 'statusline';
      try {
        const res = await fetch(`/api/paperless/backfill-jobs/${jobId}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        if (activeTaskJobId === jobId) {
          activeTaskJobId = null;
        }
        if (activeBackfillJobId === jobId) {
          setBackfillJobState(null);
          renderBackfillJob(null);
        }
        tasksStatusEl.textContent = data.message || `Job ${jobId} wurde entfernt.`;
        await loadTaskJobs();
      } catch (err) {
        tasksStatusEl.textContent = `Fehler beim Entfernen: ${err.message}`;
        tasksStatusEl.className = 'statusline warn';
      } finally {
        tasksDeleteSelectedBtn.disabled = false;
      }
    }

    async function loadTaskJobs() {
      tasksStatusEl.textContent = 'Jobliste wird geladen...';
      tasksStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/backfill-jobs');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        const jobs = Array.isArray(data.jobs) ? data.jobs : [];
        window.__taskJobsCache = jobs;
        renderTaskJobList(jobs);
        if (jobs.length) {
          tasksStatusEl.textContent = `${jobs.length} Hintergrundjob(s) gefunden.`;
        } else {
          tasksStatusEl.textContent = 'Noch kein Hintergrundjob bekannt.';
        }
        if (!activeTaskJobId && jobs.length) {
          await loadBackfillJobStatus(jobs[0].id);
        } else if (activeTaskJobId) {
          renderTaskJobList(jobs);
        } else {
          renderTaskJobDetail(null);
        }
      } catch (err) {
        tasksStatusEl.textContent = `Fehler beim Laden der Jobliste: ${err.message}`;
        tasksStatusEl.className = 'statusline warn';
      }
    }

    async function loadSystemMetrics() {
      try {
        const res = await fetch('/api/system/metrics');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        const gpuSummary = data.gpu && data.gpu.available
          ? `${data.gpu.label || 'GPU erkannt'}${data.gpu.devices && data.gpu.devices.length ? ` · ${data.gpu.devices.join(', ')}` : ''}`
          : (data.gpu && data.gpu.note) || 'Keine nutzbare GPU in dieser VM sichtbar';
        tasksSystemMetricsEl.innerHTML = `
          <div class="meta-row"><div class="meta-label">CPU-Auslastung</div><div>${formatValue(data.cpu_percent)} %</div></div>
          <div class="meta-row"><div class="meta-label">Load Average</div><div>${formatValue(data.load_average)}</div></div>
          <div class="meta-row"><div class="meta-label">RAM</div><div>${formatValue(data.memory_used_human)} / ${formatValue(data.memory_total_human)} (${formatValue(data.memory_percent)} %)</div></div>
          <div class="meta-row"><div class="meta-label">Datentraeger /</div><div>${formatValue(data.disk_used_human)} / ${formatValue(data.disk_total_human)} (${formatValue(data.disk_percent)} % frei: ${formatValue(data.disk_free_human)})</div></div>
          <div class="meta-row"><div class="meta-label">GPU</div><div>${formatValue(gpuSummary)}</div></div>
        `;
      } catch (err) {
        tasksSystemMetricsEl.innerHTML = `<div class="doc-empty">Fehler beim Laden der Systemmetriken: ${err.message}</div>`;
      }
    }

    async function loadBackfillJobStatus(jobId) {
      const cleanJobId = jobId || activeBackfillJobId;
      if (!cleanJobId) {
        renderBackfillJob(null);
        renderTaskJobDetail(null);
        return;
      }
      try {
        const res = await fetch(`/api/paperless/backfill-jobs/${cleanJobId}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        setBackfillJobState(data.id || cleanJobId);
        renderBackfillJob(data);
        renderTaskJobDetail(data);
      } catch (err) {
        backfillStatusEl.textContent = `Fehler beim Laden des Job-Status: ${err.message}`;
        backfillStatusEl.className = 'statusline warn';
        tasksStatusEl.textContent = `Fehler beim Laden des Job-Status: ${err.message}`;
        tasksStatusEl.className = 'statusline warn';
      }
    }

    async function loadLatestBackfillJobStatus() {
      try {
        const res = await fetch('/api/paperless/backfill-jobs/latest');
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        if (!data.id) {
          renderBackfillJob(null);
          renderTaskJobDetail(null);
          return;
        }
        setBackfillJobState(data.id);
        renderBackfillJob(data);
        renderTaskJobDetail(data);
      } catch (_) {
        try {
          const storedJobId = localStorage.getItem('paperless-backfill-job-id');
          if (storedJobId) {
            await loadBackfillJobStatus(storedJobId);
          }
        } catch (_) {}
      }
    }

    async function clearReviewTags() {
      if (!window.confirm('Die Zuordnung des hellblauen Review-Tags wird jetzt auf allen Dokumenten entfernt. Fortfahren?')) {
        backfillStatusEl.textContent = 'Review-Tag-Bereinigung abgebrochen.';
        return;
      }
      backfillClearReviewBtn.disabled = true;
      backfillStatusEl.textContent = 'Review-Tags werden entfernt...';
      backfillStatusEl.className = 'statusline';
      try {
        const res = await fetch('/api/paperless/review-tags/clear', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Fehler');
        backfillStatusEl.textContent = `Review-Tag entfernt von ${data.updated_documents || 0} Dokumenten.`;
        backfillLogEl.textContent = [
          `Review-Tag: ${data.tag_name || '-'}`,
          `Betroffene Dokumente: ${data.updated_documents || 0}`,
          data.deleted_tag ? 'Tag-Objekt geloescht: ja' : 'Tag-Objekt geloescht: nein'
        ].join('\\n');
        backfillLogEl.scrollTop = backfillLogEl.scrollHeight;
      } catch (err) {
        backfillStatusEl.textContent = `Fehler beim Entfernen der Review-Tags: ${err.message}`;
        backfillStatusEl.className = 'statusline warn';
      } finally {
        backfillClearReviewBtn.disabled = false;
      }
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
          'Der echte Backfill startet jetzt die KI-Nachbearbeitung fuer vorhandene Paperless-Dokumente im Hintergrund.',
          mode === 'missing' ? 'Modus: nur fehlende Metadaten' : mode === 'all' ? 'Modus: alle gefundenen Dokumente' : `Modus: nur Auswahl (${selectedCount})`,
          limit > 0 ? `Limit: ${limit}` : 'Limit: unbegrenzt',
          query ? `Query: ${query}` : 'Query: keine',
          mode === 'selected' ? `Ausgewaehlte Dokumente: ${selectedCount}` : 'Ausgewaehlte Dokumente: keine feste Auswahl',
          backfillClearReviewFirstEl.checked ? 'Vorbereitung: hellblaue Review-Tags werden zuerst entfernt' : 'Vorbereitung: keine Tag-Bereinigung'
        ].join('\\n');
        if (!window.confirm(warning + '\\n\\nFortfahren?')) {
          backfillStatusEl.textContent = 'Start abgebrochen.';
          return;
        }
      }
      backfillPreviewBtn.disabled = true;
      backfillClearReviewBtn.disabled = true;
      backfillRunBtn.disabled = true;
      backfillRefreshJobBtn.disabled = true;
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
        if (dryRun) {
          backfillLogEl.textContent = data.output || 'Keine Ausgabe';
          backfillLogEl.scrollTop = backfillLogEl.scrollHeight;
          backfillStatusEl.textContent = 'Vorschau abgeschlossen.';
        } else {
          setBackfillJobState(data.job?.id || null);
          renderBackfillJob(data.job || null);
          backfillStatusEl.textContent = `Backfill im Hintergrund gestartet (${data.job?.id || '-'})`;
        }
      } catch (err) {
        backfillLogEl.textContent = `Fehler: ${err.message}`;
        backfillLogEl.scrollTop = backfillLogEl.scrollHeight;
        backfillStatusEl.textContent = 'Fehler beim Backfill.';
        backfillStatusEl.className = 'statusline warn';
      } finally {
        backfillPreviewBtn.disabled = false;
        backfillClearReviewBtn.disabled = false;
        backfillRunBtn.disabled = false;
        backfillRefreshJobBtn.disabled = false;
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
    showPaddleOcrInstallBtn.addEventListener('click', loadPaddleOcrInstallPlan);
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
    backfillClearReviewBtn.addEventListener('click', clearReviewTags);
    backfillRunBtn.addEventListener('click', () => runBackfill(false));
    backfillRefreshJobBtn.addEventListener('click', () => loadBackfillJobStatus());
    tasksRefreshBtn.addEventListener('click', async () => {
      await loadTaskJobs();
      await loadSystemMetrics();
    });
    tasksShowLatestBtn.addEventListener('click', loadLatestBackfillJobStatus);
    tasksRefreshSelectedBtn.addEventListener('click', () => loadBackfillJobStatus(activeTaskJobId || activeBackfillJobId));
    tasksCancelSelectedBtn.addEventListener('click', cancelSelectedTaskJob);
    tasksDeleteSelectedBtn.addEventListener('click', deleteSelectedTaskJob);
    saveModelConfigBtn.addEventListener('click', saveModelConfigUi);
    reloadModelConfigBtn.addEventListener('click', loadModelConfig);
    installLocalModelBtn.addEventListener('click', installLocalModelUi);
    saveProviderConfigBtn.addEventListener('click', saveProviderConfigUi);
    reloadProviderConfigBtn.addEventListener('click', loadProviderConfigUi);
    testProviderConfigBtn.addEventListener('click', testProviderConfigUi);

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
    loadLatestBackfillJobStatus();
    loadTaskJobs();
    loadSystemMetrics();
    loadModelConfig();
    loadProviderConfigUi();
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


def ollama_preview_num_ctx() -> int:
    try:
        env_map = load_paperless_env()
    except Exception:
        env_map = {}
    return positive_int(
        env_map.get("PAPERLESS_PREVIEW_OLLAMA_NUM_CTX")
        or os.getenv("PAPERLESS_PREVIEW_OLLAMA_NUM_CTX")
        or "32768",
        32768,
    )


def default_preview_config() -> dict[str, str]:
    default_local_ocr_url = os.getenv("PAPERLESS_PROVIDER_LOCAL_OCR_URL", "http://127.0.0.1:8091")
    return {
        "preview_ocr_model": os.getenv("PAPERLESS_PREVIEW_OCR_MODEL", "qwen3.5:4b"),
        "ocr_source": os.getenv("PAPERLESS_PREVIEW_OCR_SOURCE", "paperless"),
        "paddleocr_api_url": os.getenv("PAPERLESS_PREVIEW_PADDLEOCR_API_URL", default_local_ocr_url),
        "paddleocr_timeout_seconds": os.getenv("PAPERLESS_PREVIEW_PADDLEOCR_TIMEOUT_SECONDS", "90"),
        "paddleocr_max_pages": os.getenv("PAPERLESS_PREVIEW_PADDLEOCR_MAX_PAGES", "1"),
        "vision_model": os.getenv("PAPERLESS_PREVIEW_VISION_MODEL", "qwen3.5:0.8b"),
        "vision_content_chars": os.getenv("PAPERLESS_PREVIEW_VISION_CONTENT_CHARS", "800"),
        "vision_timeout_seconds": os.getenv("PAPERLESS_PREVIEW_VISION_TIMEOUT_SECONDS", "120"),
        "vision_max_pages": os.getenv("PAPERLESS_PREVIEW_VISION_MAX_PAGES", "1"),
        "vision_tag_name": os.getenv("PAPERLESS_PREVIEW_VISION_TAG_NAME", "KI Vision"),
        "vision_tag_color": os.getenv("PAPERLESS_PREVIEW_VISION_TAG_COLOR", "#d97706"),
    }


def default_provider_config() -> dict[str, str]:
    default_local_ocr_url = os.getenv("PAPERLESS_PROVIDER_LOCAL_OCR_URL", "http://127.0.0.1:8091")
    return {
        "active_ollama_provider": "local",
        "local_ollama_url": OLLAMA_URL,
        "remote_ollama_url": "",
        "active_ocr_provider": "local",
        "local_ocr_url": default_local_ocr_url,
        "remote_ocr_url": "",
    }


def load_provider_config() -> dict[str, str]:
    config = default_provider_config()
    path = Path(PROVIDER_CONFIG_PATH)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid provider config: {exc}") from exc
        if isinstance(loaded, dict):
            for key in config:
                value = loaded.get(key)
                if value is not None and str(value).strip():
                    config[key] = str(value).strip()
    return config


def save_provider_config(payload: dict) -> tuple[int, dict]:
    allowed = default_provider_config()
    current = load_provider_config()
    for key in allowed:
        value = str(payload.get(key, "")).strip()
        if value:
            current[key] = value
    path = Path(PROVIDER_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 200, {"status": "ok"}


def default_model_config() -> dict[str, object]:
    return {
        "library_json": json.dumps(
            [
                {
                    "name": "qwen3.5:9b",
                    "role": "paperless_primary",
                    "provider": "ollama_local",
                    "homepage": "https://ollama.com/library/qwen3.5:9b",
                },
                {
                    "name": "qwen3.5:0.8b",
                    "role": "paperless_fallback",
                    "provider": "ollama_local",
                    "homepage": "https://ollama.com/library/qwen3.5:0.8b",
                },
            ],
            ensure_ascii=False,
            indent=2,
        )
    }


def load_model_config() -> dict[str, object]:
    config = default_model_config()
    path = Path(MODEL_CONFIG_PATH)
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid model config: {exc}") from exc
        if isinstance(loaded, dict):
            library_json = loaded.get("library_json")
            if library_json is not None and str(library_json).strip():
                config["library_json"] = str(library_json)
    return config


def save_model_config(payload: dict) -> tuple[int, dict]:
    current = load_model_config()
    library_json = str(payload.get("library_json", "")).strip()
    if library_json:
        try:
            json.loads(library_json)
        except json.JSONDecodeError as exc:
            return 400, {"error": f"Ungueltiges JSON: {exc}"}
        current["library_json"] = library_json
    path = Path(MODEL_CONFIG_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return 200, {"status": "ok"}


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
        "tag_rules_force": env_map.get("PAPERLESS_AI_TAG_RULES_FORCE", "false"),
        "review_min_confidence": env_map.get("PAPERLESS_AI_REVIEW_MIN_CONFIDENCE", "0.8"),
        "review_tag_name": env_map.get("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen"),
        "review_tag_color": env_map.get("PAPERLESS_AI_REVIEW_TAG_COLOR", "#7dd3fc"),
        "tag_allowlists_json": tag_allowlists_json,
        "tag_rules_json": tag_rules_json,
    }


def read_preview_config() -> tuple[int, dict]:
    return 200, load_preview_config()


def read_provider_config() -> tuple[int, dict]:
    return 200, load_provider_config()


def read_model_config() -> tuple[int, dict]:
    return 200, load_model_config()


def provider_healthcheck(url: str, path: str = "/api/tags", timeout: int = 10) -> dict:
    target = str(url or "").strip()
    if not target:
        return {"ok": False, "error": "keine URL gesetzt"}
    full_url = f"{target.rstrip('/')}{path}"
    try:
        req = urllib.request.Request(full_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status, "url": full_url, "body_excerpt": body[:300]}
    except Exception as exc:
        return {"ok": False, "url": full_url, "error": str(exc)}


def test_provider_config() -> tuple[int, dict]:
    config = load_provider_config()
    return 200, {
        "local_ollama": provider_healthcheck(config.get("local_ollama_url", ""), "/api/tags"),
        "remote_ollama": provider_healthcheck(config.get("remote_ollama_url", ""), "/api/tags"),
        "local_ocr": provider_healthcheck(config.get("local_ocr_url", ""), "/healthz"),
        "remote_ocr": provider_healthcheck(config.get("remote_ocr_url", ""), "/healthz"),
    }


def install_local_model(model_name: str) -> tuple[int, dict]:
    name = str(model_name or "").strip()
    if not name:
        return 400, {"error": "Kein Modellname angegeben"}
    result = subprocess.run(
        ["ollama", "pull", name],
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        200 if result.returncode == 0 else 500,
        {
            "model": name,
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        },
    )


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
        "tag_rules_force": "PAPERLESS_AI_TAG_RULES_FORCE",
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


def render_pdf_preview_image_bytes(pdf_bytes: bytes, max_pages: int = 1) -> list[bytes]:
    pdftoppm = "/usr/bin/pdftoppm"
    if not Path(pdftoppm).is_file():
        raise RuntimeError("pdftoppm is not installed on the host")
    with tempfile.TemporaryDirectory(prefix="paperless-ai-paddleocr-") as tmpdir:
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
        return [path.read_bytes() for path in image_paths]


def build_multipart_form(field_name: str, filename: str, content: bytes, content_type: str = "application/octet-stream") -> tuple[bytes, str]:
    boundary = f"----paperlessAiBoundary{uuid.uuid4().hex}"
    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        (
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    body.extend(content)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), boundary


def call_paddleocr_preview(image_bytes: bytes, filename: str, base_url: str, timeout: float) -> dict:
    payload, boundary = build_multipart_form("file", filename, image_bytes, "image/jpeg")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/ocr",
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_paddleocr_preview(document_id: int, document: dict, preview_config: dict[str, str]) -> tuple[dict, dict]:
    original_name = str(document.get("original_file_name") or "").lower()
    if not original_name.endswith(".pdf"):
        raise RuntimeError("PaddleOCR preview is currently only enabled for PDF documents")
    page_count = int(document.get("page_count") or 0)
    max_pages = positive_int(preview_config.get("paddleocr_max_pages"), 1)
    if page_count and page_count > max_pages:
        raise RuntimeError(f"PaddleOCR uebersprungen: {page_count} Seiten, Limit ist {max_pages}")
    pdf_bytes, content_type = fetch_paperless_document_binary(document_id)
    if "pdf" not in (content_type or "").lower():
        raise RuntimeError(f"unexpected content type for PaddleOCR preview: {content_type or '-'}")
    images = render_pdf_preview_image_bytes(pdf_bytes, max_pages=1)
    started = time.time()
    result = call_paddleocr_preview(
        images[0],
        f"document-{document_id}-page-1.jpg",
        preview_config.get("paddleocr_api_url", "http://127.0.0.1:8091"),
        float(preview_config.get("paddleocr_timeout_seconds", "90") or "90"),
    )
    return result, {
        "seconds": round(time.time() - started, 2),
        "lines": int(result.get("line_count") or 0),
        "pages": len(images),
    }


def build_install_plan() -> tuple[int, dict]:
    script_path = Path(PADDLEOCR_API_INSTALL_SCRIPT)
    repo_dir = script_path.parent.parent if script_path.name == "install-paddleocr-api.sh" else script_path.parent
    return 200, {
        "available": script_path.name == "install-paddleocr-api.sh",
        "script": str(script_path),
        "commands": [
            f"cd {repo_dir}",
            f"sudo bash {script_path}",
        ],
        "notes": [
            "Der Installationspfad nutzt plain Docker und benoetigt kein docker compose.",
            "Standardport ist 8091 und kann spaeter in der Preview-Konfiguration angepasst werden.",
            "Nach der Installation kann die Vorschau OCR-Quelle auf PaddleOCR oder Hybrid gestellt werden.",
        ],
    }


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
    num_ctx = ollama_preview_num_ctx()
    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"num_thread": num_thread, "num_ctx": num_ctx},
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
    paperless_ocr_text = str(document.get("content") or "")
    ocr_source = preview_config.get("ocr_source", "paperless").strip().lower() or "paperless"
    effective_ocr_text = paperless_ocr_text
    paddle_ocr_text = ""
    paddle_meta: dict[str, object] = {}
    paddle_error = ""
    if ocr_source in {"paddleocr", "hybrid"}:
        try:
            paddle_result, paddle_meta = fetch_paddleocr_preview(document_id, document, preview_config)
            paddle_ocr_text = str(paddle_result.get("text") or "").strip()
            if paddle_ocr_text:
                if ocr_source == "paddleocr":
                    effective_ocr_text = paddle_ocr_text
                else:
                    effective_ocr_text = "\n\n".join(
                        part for part in (
                            "PADDLEOCR SEITE 1:\n" + paddle_ocr_text,
                            "PAPERLESS OCR:\n" + paperless_ocr_text if paperless_ocr_text else "",
                        ) if part
                    )
        except Exception as exc:
            paddle_error = str(exc)
            effective_ocr_text = paperless_ocr_text
            ocr_source = "paperless"
    ocr_view = build_structured_ocr_view(effective_ocr_text)
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
    proposal["_ocr_source"] = ocr_source
    proposal["_paddle_ocr_used"] = bool(paddle_ocr_text)
    proposal["_paddle_ocr_seconds"] = paddle_meta.get("seconds", "")
    proposal["_paddle_ocr_excerpt"] = paddle_ocr_text[:2200]
    proposal["_paddle_ocr_error"] = paddle_error
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


def _paperless_api_request(path: str, method: str = "GET", payload: dict | None = None, timeout: int = 120) -> dict:
    env_map = load_paperless_env()
    api_url = env_map.get("PAPERLESS_API_URL")
    token = env_map.get("PAPERLESS_API_TOKEN")
    if not api_url or not token:
        raise RuntimeError("Paperless API configuration is incomplete")
    data = None
    headers = {"Accept": "application/json", "Authorization": f"Token {token}"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}{path}",
        headers=headers,
        data=data,
        method=method,
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8") if response.length != 0 else ""
        return json.loads(raw) if raw else {}


def list_all_paperless_documents(page_size: int = 100) -> list[dict]:
    documents: list[dict] = []
    next_url = f"/api/documents/?page_size={max(1, min(page_size, 200))}&ordering=id"
    while next_url:
        payload = _paperless_api_request(next_url, timeout=180)
        for item in payload.get("results", []):
            if isinstance(item, dict):
                documents.append(item)
        absolute_next = payload.get("next")
        if absolute_next:
            parsed = urllib.parse.urlparse(str(absolute_next))
            next_url = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        else:
            next_url = ""
    return documents


def clear_review_tag_assignments() -> tuple[int, dict]:
    paperless_env = load_paperless_env()
    review_tag_name = paperless_env.get("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen")
    tags_payload = _paperless_api_request("/api/tags/?page_size=200", timeout=120)
    review_tag = None
    for item in tags_payload.get("results", []):
        if isinstance(item, dict) and str(item.get("name", "")) == review_tag_name:
            review_tag = item
            break
    if not review_tag:
        return 200, {"tag_name": review_tag_name, "updated_documents": 0, "deleted_tag": False}
    review_tag_id = int(review_tag.get("id"))
    documents = list_all_paperless_documents()
    updated = 0
    for item in documents:
        tags = item.get("tags") or []
        current_ids = [int(tag["id"]) for tag in tags if isinstance(tag, dict) and tag.get("id") is not None]
        if review_tag_id not in current_ids:
            continue
        new_ids = [tag_id for tag_id in current_ids if tag_id != review_tag_id]
        _paperless_api_request(f"/api/documents/{int(item['id'])}/", method="PATCH", payload={"tags": new_ids}, timeout=180)
        updated += 1
    try:
        _paperless_api_request(f"/api/tags/{review_tag_id}/", method="DELETE", timeout=120)
        deleted_tag = True
    except Exception:
        deleted_tag = False
    return 200, {"tag_name": review_tag_name, "updated_documents": updated, "deleted_tag": deleted_tag}


def _save_backfill_state() -> None:
    payload = {
        "latest_job_id": BACKFILL_LATEST_JOB_ID,
        "jobs": BACKFILL_JOBS,
    }
    path = Path(BACKFILL_STATE_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _load_backfill_state() -> None:
    global BACKFILL_LATEST_JOB_ID
    path = Path(BACKFILL_STATE_PATH)
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    jobs = payload.get("jobs")
    latest_job_id = payload.get("latest_job_id")
    if isinstance(jobs, dict):
        BACKFILL_JOBS.clear()
        for key, value in jobs.items():
            if isinstance(key, str) and isinstance(value, dict):
                BACKFILL_JOBS[key] = value
    if isinstance(latest_job_id, str):
        BACKFILL_LATEST_JOB_ID = latest_job_id


def _discover_latest_backfill_job_from_logs() -> dict | None:
    candidates = sorted(Path("/tmp").glob("paperless-ai-backfill-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    log_path = candidates[0]
    job_id = log_path.stem.replace("paperless-ai-backfill-", "", 1)
    text = _tail_text_file(str(log_path), max_chars=40000)
    lines = text.splitlines()
    started_at = ""
    document_count = 0
    status = "running"
    returncode = None
    for line in lines:
        if "Starting job" in line and line.startswith("[") and "]" in line:
            started_at = line[1:].split("]", 1)[0]
        if "Selected " in line and " document(s)" in line:
            match = re.search(r"Selected (\d+) document\(s\)", line)
            if match:
                document_count = int(match.group(1))
        if "Job finished with returncode " in line:
            match = re.search(r"returncode (-?\d+)", line)
            if match:
                returncode = int(match.group(1))
                status = "done" if returncode == 0 else "error"
    job = {
        "id": job_id,
        "status": status,
        "started_at": started_at,
        "log_path": str(log_path),
        "document_count": document_count,
    }
    if returncode is not None:
        job["returncode"] = returncode
    return job


def store_backfill_job(job_id: str, payload: dict) -> None:
    global BACKFILL_LATEST_JOB_ID
    with BACKFILL_JOBS_LOCK:
        BACKFILL_JOBS[job_id] = payload
        BACKFILL_LATEST_JOB_ID = job_id
        _save_backfill_state()


def read_backfill_job(job_id: str) -> dict | None:
    with BACKFILL_JOBS_LOCK:
        if not BACKFILL_JOBS:
            _load_backfill_state()
        return BACKFILL_JOBS.get(job_id)


def read_latest_backfill_job() -> dict | None:
    with BACKFILL_JOBS_LOCK:
        if not BACKFILL_JOBS:
            _load_backfill_state()
        if not BACKFILL_LATEST_JOB_ID:
            discovered = _discover_latest_backfill_job_from_logs()
            if discovered:
                BACKFILL_JOBS[discovered["id"]] = discovered
                _save_backfill_state()
                return discovered
            return None
        job = BACKFILL_JOBS.get(BACKFILL_LATEST_JOB_ID)
        if job is not None:
            return job
        discovered = _discover_latest_backfill_job_from_logs()
        if discovered:
            BACKFILL_JOBS[discovered["id"]] = discovered
            return discovered
        return None


def list_backfill_jobs() -> list[dict]:
    with BACKFILL_JOBS_LOCK:
        if not BACKFILL_JOBS:
            _load_backfill_state()
        discovered = _discover_latest_backfill_job_from_logs()
        if discovered and discovered["id"] not in BACKFILL_JOBS:
            BACKFILL_JOBS[discovered["id"]] = discovered
            _save_backfill_state()
        jobs = [dict(value) for value in BACKFILL_JOBS.values() if isinstance(value, dict)]
    def _sort_key(job: dict) -> tuple[str, str]:
        return (str(job.get("started_at") or ""), str(job.get("id") or ""))
    jobs.sort(key=_sort_key, reverse=True)
    return jobs


def cancel_backfill_job(job_id: str) -> tuple[int, dict]:
    job = read_backfill_job(job_id)
    if job is None:
        return 404, {"error": "Backfill job not found"}
    payload = dict(job)
    status = str(payload.get("status") or "")
    pid = payload.get("pid")
    if status not in {"running", "starting"}:
        return 400, {"error": "Job ist nicht mehr aktiv"}
    if not _process_alive(pid):
        payload["status"] = "error"
        payload["error"] = "Hintergrundprozess laeuft nicht mehr"
        payload["error_reason"] = "Hintergrundprozess laeuft nicht mehr"
        payload["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        store_backfill_job(job_id, payload)
        return 200, {"job": payload, "message": f"Job {job_id} war bereits beendet."}
    try:
        os.kill(int(pid), 15)
    except OSError as exc:
        return 500, {"error": f"Job konnte nicht abgebrochen werden: {exc}"}
    payload["status"] = "error"
    payload["error"] = "Manuell abgebrochen"
    payload["error_reason"] = "Manuell abgebrochen"
    payload["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    log_path = payload.get("log_path")
    if log_path:
        with Path(str(log_path)).open("a", encoding="utf-8") as handle:
            handle.write(f"[{payload['finished_at']}] Job manuell abgebrochen\n")
    store_backfill_job(job_id, payload)
    return 200, {"job": payload, "message": f"Job {job_id} wurde abgebrochen."}


def delete_backfill_job(job_id: str) -> tuple[int, dict]:
    global BACKFILL_LATEST_JOB_ID
    with BACKFILL_JOBS_LOCK:
        if not BACKFILL_JOBS:
            _load_backfill_state()
        job = BACKFILL_JOBS.get(job_id)
        if job is None:
            return 404, {"error": "Backfill job not found"}
        status = str(job.get("status") or "")
        if status in {"running", "starting"} and _process_alive(job.get("pid")):
            return 400, {"error": "Aktive Jobs bitte erst abbrechen"}
        log_path = str(job.get("log_path") or "")
        deleted_log = False
        if log_path:
            try:
                Path(log_path).unlink(missing_ok=True)
                deleted_log = True
            except Exception:
                deleted_log = False
        BACKFILL_JOBS.pop(job_id, None)
        if BACKFILL_LATEST_JOB_ID == job_id:
            BACKFILL_LATEST_JOB_ID = next(iter(BACKFILL_JOBS.keys()), None)
        _save_backfill_state()
    return 200, {"deleted": True, "deleted_log": deleted_log, "message": f"Job {job_id} wurde entfernt."}


def _read_cpu_times() -> tuple[int, int]:
    line = Path("/proc/stat").read_text(encoding="utf-8", errors="replace").splitlines()[0]
    parts = [int(value) for value in line.split()[1:]]
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    total = sum(parts)
    return total, idle


def _read_cpu_percent(sample_seconds: float = 0.15) -> float:
    try:
        total_1, idle_1 = _read_cpu_times()
        time.sleep(sample_seconds)
        total_2, idle_2 = _read_cpu_times()
    except Exception:
        return 0.0
    total_delta = max(total_2 - total_1, 1)
    idle_delta = max(idle_2 - idle_1, 0)
    busy = max(total_delta - idle_delta, 0)
    return round((busy / total_delta) * 100, 1)


def _bytes_to_human(value: int) -> str:
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(value, 0))
    for suffix in suffixes:
        if size < 1024 or suffix == suffixes[-1]:
            if suffix == "B":
                return f"{int(size)} {suffix}"
            return f"{size:.1f} {suffix}"
        size /= 1024
    return f"{value} B"


def read_system_metrics() -> tuple[int, dict]:
    cpu_percent = _read_cpu_percent()
    try:
        load_avg = os.getloadavg()
        load_average = ", ".join(f"{value:.2f}" for value in load_avg)
    except Exception:
        load_average = "-"
    meminfo = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            meminfo[key.strip()] = value.strip()
    except Exception:
        meminfo = {}
    mem_total_kb = int((meminfo.get("MemTotal", "0 kB").split() or ["0"])[0])
    mem_available_kb = int((meminfo.get("MemAvailable", "0 kB").split() or ["0"])[0])
    mem_used_kb = max(mem_total_kb - mem_available_kb, 0)
    mem_percent = round((mem_used_kb / mem_total_kb) * 100, 1) if mem_total_kb else 0.0
    stat = os.statvfs("/")
    disk_total = stat.f_frsize * stat.f_blocks
    disk_free = stat.f_frsize * stat.f_bavail
    disk_used = max(disk_total - disk_free, 0)
    disk_percent = round((disk_used / disk_total) * 100, 1) if disk_total else 0.0
    gpu_devices = []
    render_devices = []
    dri_root = Path("/dev/dri")
    if dri_root.exists():
        for child in sorted(dri_root.iterdir()):
            gpu_devices.append(child.name)
            if child.name.startswith("renderD"):
                render_devices.append(child.name)
    gpu_available = bool(render_devices)
    gpu_note = ""
    if gpu_devices and not render_devices:
        gpu_note = "Grafikgeraet sichtbar, aber keine nutzbare Render-Schnittstelle"
    if not gpu_devices:
        try:
            lspci = subprocess.run(
                ["lspci"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            gpu_note = "Keine nutzbare GPU in der VM sichtbar"
            lines = [line.strip() for line in lspci.stdout.splitlines() if any(token in line.lower() for token in ("vga", "3d controller", "display"))]
            if lines:
                gpu_note = "Nur allgemeiner Video-Adapter sichtbar"
        except Exception:
            gpu_note = "Keine nutzbare GPU in der VM sichtbar"
    payload = {
        "cpu_percent": cpu_percent,
        "load_average": load_average,
        "memory_total_human": _bytes_to_human(mem_total_kb * 1024),
        "memory_used_human": _bytes_to_human(mem_used_kb * 1024),
        "memory_percent": mem_percent,
        "disk_total_human": _bytes_to_human(disk_total),
        "disk_used_human": _bytes_to_human(disk_used),
        "disk_free_human": _bytes_to_human(disk_free),
        "disk_percent": disk_percent,
        "gpu": {
            "available": gpu_available,
            "devices": gpu_devices,
            "render_devices": render_devices,
            "label": "Nutzbare GPU / iGPU erkannt" if gpu_available else "",
            "note": gpu_note,
        },
    }
    return 200, payload


def _tail_text_file(path: str, max_chars: int = 12000) -> str:
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return text[-max_chars:]


def _process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _extract_backfill_completion(log_text: str) -> tuple[str | None, int | None]:
    status = None
    returncode = None
    match = re.search(r"Job finished with returncode (-?\d+)", log_text)
    if match:
        returncode = int(match.group(1))
        status = "done" if returncode == 0 else "error"
    elif "Job failed before completion:" in log_text:
        status = "error"
        returncode = -1
    return status, returncode


def _extract_backfill_log_details(log_text: str) -> dict:
    details: dict[str, object] = {}
    selected_match = re.search(r"Selected (\d+) document\(s\)", log_text)
    if selected_match:
        details["document_count"] = int(selected_match.group(1))
    processed = re.findall(r"\[paperless-ai-backfill\] Processing document (\d+)", log_text)
    if processed:
        details["last_document_id"] = int(processed[-1])
    analyzed = re.findall(
        r"\[paperless-ai\] LLM analyzed document (\d+) in ([0-9.]+)s using ([^;]+)(?:; tag_review=([^\n]+))?",
        log_text,
    )
    if analyzed:
        doc_id, seconds, model_name, tag_model = analyzed[-1]
        details["last_analyzed_document_id"] = int(doc_id)
        details["last_duration_seconds"] = float(seconds)
        details["last_model"] = model_name.strip()
        if tag_model:
            details["last_tag_review_model"] = tag_model.strip()
    error_reason = ""
    failure_match = re.search(r"Job failed before completion:\s*(.+)", log_text)
    if failure_match:
        error_reason = failure_match.group(1).strip()
    elif "Hintergrundprozess laeuft nicht mehr" in log_text:
        error_reason = "Hintergrundprozess laeuft nicht mehr"
    if error_reason:
        details["error_reason"] = error_reason
    activity_lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    if activity_lines:
        details["last_activity"] = activity_lines[-1]
    return details


def read_backfill_job_payload(job_id: str) -> tuple[int, dict]:
    job = read_backfill_job(job_id)
    if job is None:
        return 404, {"error": "Backfill job not found"}
    payload = dict(job)
    log_path = payload.get("log_path")
    if log_path:
        full_tail = _tail_text_file(str(log_path), max_chars=40000)
        payload["tail"] = full_tail[-12000:]
        payload.update(_extract_backfill_log_details(full_tail))
        completion_status, returncode = _extract_backfill_completion(full_tail)
        if completion_status:
            payload["status"] = completion_status
        elif payload.get("status") == "running" and not _process_alive(payload.get("pid")):
            payload["status"] = "error"
            payload["error"] = "Hintergrundprozess laeuft nicht mehr"
            payload.setdefault("error_reason", "Hintergrundprozess laeuft nicht mehr")
        if returncode is not None:
            payload["returncode"] = returncode
        store_backfill_job(job_id, payload)
    return 200, payload


def read_latest_backfill_job_payload() -> tuple[int, dict]:
    job = read_latest_backfill_job()
    if job is None:
        return 200, {}
    payload = dict(job)
    log_path = payload.get("log_path")
    if log_path:
        full_tail = _tail_text_file(str(log_path), max_chars=40000)
        payload["tail"] = full_tail[-12000:]
        payload.update(_extract_backfill_log_details(full_tail))
        completion_status, returncode = _extract_backfill_completion(full_tail)
        if completion_status:
            payload["status"] = completion_status
        elif payload.get("status") == "running" and not _process_alive(payload.get("pid")):
            payload["status"] = "error"
            payload["error"] = "Hintergrundprozess laeuft nicht mehr"
            payload.setdefault("error_reason", "Hintergrundprozess laeuft nicht mehr")
        if returncode is not None:
            payload["returncode"] = returncode
        store_backfill_job(str(payload["id"]), payload)
    return 200, payload


def render_backfill_bootstrap() -> tuple[str, str]:
    job = read_latest_backfill_job()
    if not job:
        return "Noch kein Lauf gestartet.", "Bereit."
    status = str(job.get("status") or "unbekannt")
    job_id = str(job.get("id") or "-")
    document_count = int(job.get("document_count") or 0)
    prefix = f"{document_count} Dokumente" if document_count > 0 else "Backfill-Job"
    if status == "running":
        status_text = f"{prefix}: Hintergrundlauf aktiv ({job_id})."
    elif status == "done":
        status_text = f"{prefix}: abgeschlossen ({job_id})."
    elif status == "error":
        status_text = f"{prefix}: Fehler ({job_id})."
    else:
        status_text = f"{prefix}: {status} ({job_id})."
    lines = [f"Job-ID: {job_id}"]
    if job.get("started_at"):
        lines.append(f"Gestartet: {job['started_at']}")
    if job.get("finished_at"):
        lines.append(f"Beendet: {job['finished_at']}")
    if job.get("log_path"):
        lines.append(f"Log: {job['log_path']}")
    if job.get("clear_summary"):
        lines.append(f"Vorbereitung: {job['clear_summary']}")
    tail = _tail_text_file(str(job.get("log_path") or ""))
    if tail:
        lines.extend(["", tail])
    return status_text, "\n".join(lines)


def render_html_page() -> bytes:
    status_text, log_text = render_backfill_bootstrap()
    page = HTML.replace("__BACKFILL_STATUS__", html.escape(status_text)).replace(
        "__BACKFILL_LOG__", html.escape(log_text)
    )
    return page.encode("utf-8")


def build_backfill_command_and_env(payload: dict) -> tuple[list[str], dict[str, str]]:
    if not Path(PAPERLESS_BACKFILL).is_file():
        raise RuntimeError(f"Backfill script not found: {PAPERLESS_BACKFILL}")
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
    return cmd, child_env


def launch_detached_backfill_process(job_id: str, cmd: list[str], child_env: dict[str, str], log_path: str) -> int:
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    Path(log_path).write_text(
        f"[{started}] Starting job {job_id}\nCommand: {' '.join(cmd)}\n\n",
        encoding="utf-8",
    )
    quoted_cmd = " ".join(shlex.quote(part) for part in cmd)
    quoted_log = shlex.quote(log_path)
    wrapper = (
        "set -o pipefail; "
        "{ "
        f"{quoted_cmd} 2>&1 | while IFS= read -r line; do "
        f"printf '[%s] %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" \"$line\"; "
        f"done >> {quoted_log}; "
        "}; "
        "rc=${PIPESTATUS[0]}; "
        f"printf '\\n[%s] Job finished with returncode %s\\n' \"$(date '+%Y-%m-%d %H:%M:%S')\" \"$rc\" >> {quoted_log}; "
        "exit 0"
    )
    process = subprocess.Popen(
        ["/bin/bash", "-lc", wrapper],
        env=child_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        text=False,
    )
    return process.pid


def start_paperless_backfill(payload: dict) -> tuple[int, dict]:
    cmd, child_env = build_backfill_command_and_env(payload)
    job_id = uuid.uuid4().hex
    started = time.strftime("%Y-%m-%d %H:%M:%S")
    review_tag_name = load_paperless_env().get("PAPERLESS_AI_REVIEW_TAG_NAME", "KI Nachpruefen")
    log_path = f"/tmp/paperless-ai-backfill-{job_id}.log"
    job = {
        "id": job_id,
        "status": "starting",
        "started_at": started,
        "log_path": log_path,
        "document_count": len(payload.get("document_ids", []) or []),
        "review_tag_name": review_tag_name,
        "mode": str(payload.get("mode") or ""),
    }
    if payload.get("clear_review_tags_first"):
        status, summary = clear_review_tag_assignments()
        if status != 200:
            return status, summary
        job["clear_summary"] = f"{summary.get('updated_documents', 0)} Dokumente bereinigt"
    pid = launch_detached_backfill_process(job_id, cmd, child_env, log_path)
    job["pid"] = pid
    job["status"] = "running"
    store_backfill_job(job_id, job)
    return 200, {"job": job}


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/" or self.path == "/index.html":
            self._send(200, render_html_page(), "text/html; charset=utf-8")
            return
        if self.path.startswith("/api/paperless/preview-jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            payload = read_preview_job(job_id)
            if payload is None:
                self._send(404, json.dumps({"error": "Preview job not found"}).encode("utf-8"), "application/json")
                return
            self._send(200, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/paperless/backfill-jobs/latest":
            try:
                status, payload = read_latest_backfill_job_payload()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/paperless/backfill-jobs":
            try:
                status, payload = 200, {"jobs": list_backfill_jobs()}
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path.startswith("/api/paperless/backfill-jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            try:
                status, payload = read_backfill_job_payload(job_id)
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/system/metrics":
            try:
                status, payload = read_system_metrics()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
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
        if self.path == "/api/providers/config":
            try:
                status, payload = read_provider_config()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/models/config":
            try:
                status, payload = read_model_config()
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        if self.path == "/api/paddleocr/install-plan":
            try:
                status, payload = build_install_plan()
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

    def do_DELETE(self) -> None:
        if self.path.startswith("/api/paperless/backfill-jobs/"):
            job_id = self.path.rsplit("/", 1)[-1]
            try:
                status, payload = delete_backfill_job(job_id)
            except Exception as exc:
                status, payload = 500, {"error": str(exc)}
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")
            return
        self._send(404, b"Not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if self.path.startswith("/api/paperless/backfill-jobs/") and self.path.endswith("/cancel"):
            job_id = self.path.rsplit("/", 2)[-2]
            try:
                status, response = cancel_backfill_job(job_id)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
            self._send(status, json.dumps(response).encode("utf-8"), "application/json")
            return
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
        if self.path not in (
            "/api/chat",
            "/api/paperless/backfill",
            "/api/paperless/model",
            "/api/paperless/config",
            "/api/preview/config",
            "/api/providers/config",
            "/api/models/config",
            "/api/providers/test",
            "/api/models/install",
            "/api/paperless/prompt",
            "/api/paperless/review-tags/clear",
        ):
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
        elif self.path == "/api/providers/config":
            try:
                status, response = save_provider_config(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/models/config":
            try:
                status, response = save_model_config(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/providers/test":
            try:
                status, response = test_provider_config()
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/models/install":
            try:
                status, response = install_local_model(payload.get("model"))
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/paperless/prompt":
            try:
                status, response = save_paperless_prompt(payload.get("prompt"))
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        elif self.path == "/api/paperless/review-tags/clear":
            try:
                status, response = clear_review_tag_assignments()
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        else:
            try:
                if payload.get("dry_run"):
                    status, response = run_paperless_backfill(payload)
                else:
                    status, response = start_paperless_backfill(payload)
            except Exception as exc:
                status, response = 500, {"error": str(exc)}
        self._send(status, json.dumps(response).encode("utf-8"), "application/json")

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Ollama web listening on http://{HOST}:{PORT}", flush=True)
    httpd.serve_forever()
