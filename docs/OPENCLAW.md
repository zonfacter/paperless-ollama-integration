# OpenClaw

## Ziel

OpenClaw ist im Stack der Agent-Layer fuer Coding-, Analyse- und Automationsaufgaben auf dem lokalen Workspace.

## Vulkan-Modellrouting (MI50)

- `code-fast` -> `qwen2.5-coder:7b`
- `code-pro` -> `qwen2.5-coder:14b`
- `research-legal` -> `qwen2.5:14b`
- `paperless-tagger` -> `qwen2.5:3b`
- `vision-ocr` -> `deepseek-ocr:3b`

## Wichtige Tools/Policy

- `tools.profile: "full"` als Baseline (stabiler fuer Session-/Slash-Steuerung und gemischte Aufgaben)
- Session-Sichtbarkeit: `tools.sessions.visibility: "tree"`
- Inline-Attachments fuer `sessions_spawn` aktiviert
  - `maxTotalBytes: 25 MB`
  - `maxFiles: 20`
  - `maxFileBytes: 5 MB`
- MCP `filesystem` als Default fuer Workspace-Dateizugriff

Hinweis:

- Inline-Attachments gelten fuer Subagent-Spawn (`sessions_spawn`, runtime `subagent`).
- Fuer groessere Dokumente ist der robuste Pfad: Datei in den Workspace legen und dann mit Coding-/Research-Agent analysieren.

## Schneller Start

1. Chat mit `code-fast` starten.
2. Erste Nachricht mit Projektpfad senden, z. B. `Projektpfad: project/ebay`.
3. Danach konkrete Aufgabe stellen, z. B. `Analysiere logs/ auf Invalid request und schlage Patch vor.`

## Zusammenspiel mit OpenWebUI

- OpenWebUI bleibt der beste Upload-/RAG-Einstieg fuer `txt/md/pdf/doc/docx`.
- OpenClaw uebernimmt danach agentische Umsetzung, Dateioperationen und Codeaenderungen auf dem Workspace.
