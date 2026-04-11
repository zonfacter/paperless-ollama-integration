# Major Release Plan (v5)

## Ziel

Das aktuelle Repository ist funktional, aber umfasst inzwischen mehrere Produktzweige.  
Fuer bessere Wartbarkeit soll der naechste Major-Release die Bereiche sauber trennen, ohne den integrierten Betriebspfad zu verlieren.

## Zielstruktur

1. `paperless-core`
- Hook, Prompt, Backfill, Paperless-spezifische Konfiguration.

2. `ai-services`
- Ollama/ROCm, optionale OCR-Dienste, optionale Image-Backends.

3. `control-ui`
- Webkonsole auf Port 3000 inklusive Monitoring, GPU-Steuerung, OpenClaw-MCP-Admin.

4. `agent-runtime`
- OpenClaw Gateway, Workspace-Profile, MCP-Basiskonfiguration.

## Release-Strategie

1. `v5.0.0-rc1`
- Freeze des aktuellen funktionierenden Stands.
- Dokumentation auf reproduzierbare Neuinstallation pruefen.

2. `v5.0.0-rc2`
- Compose-Profile nach Domanen gruppieren (`core`, `ai`, `ui`, `agents`).
- Bootstrap-Skript auf modulare Auswahl erweitern.

3. `v5.0.0`
- Finaler Migrationspfad von v4 nach v5.
- Changelog in Deutsch und Englisch.

## Installationsziele fuer v5

- Einfache Standardinstallation mit einem Befehl (Core + UI).
- Optionale Erweiterungen einzeln aktivierbar (Image, OCR, Agents).
- Keine manuelle Nachpatch-Arbeit fuer den Basisbetrieb.

## Abnahmekriterien

- `docker compose config -q` sauber fuer alle dokumentierten Profile.
- Neuinstallation nach Doku ohne manuelle Dateiedits erfolgreich.
- OpenClaw kann in Standard-Workspace einen Coding-Auftrag mit MCP-Tools ausfuehren.
