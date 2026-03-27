# Architecture

## Ueberblick

Das System besteht aus drei Hauptteilen:

1. `paperless-ngx`
2. `Ollama`
3. einer lokalen Glue-Logik fuer Metadatenanreicherung

## Komponenten

### Paperless

- `paperless-webserver.service`
  - UI und API
- `paperless-consumer.service`
  - beobachtet den Consume-Ordner
- `paperless-task-queue.service`
  - verarbeitet Celery-Tasks
- `paperless-scheduler.service`
  - fuehrt periodische Tasks via `celery beat` aus

### KI-Hook

- `hooks/ai_enrich.py`
  - wird nach erfolgreichem Import gestartet
  - liest das Dokument ueber die Paperless-API
  - baut aus OCR-Text und Metadaten einen Prompt
  - fragt ein lokales oder externes Modell ab
  - schreibt die vorgeschlagenen Metadaten zurueck
  - kann auf ein Fallback-Modell wechseln
  - schaltet bei `Qwen 3.5` standardmaessig Thinking aus
  - prueft Personentags gegen vorhandene Tags und OCR-Text

### Prompt-Schicht

- `prompts/ai_enrich_prompt.txt`
  - enthaelt die fachlichen Regeln fuer die Klassifikation
  - ist absichtlich vom Code getrennt
  - kann ohne Python-Aenderung angepasst werden
  - enthaelt Platzhalter fuer vorhandene Personentags

### Ollama

- lokaler API-Server auf `127.0.0.1:11434`
- Modell z. B. `qwen3.5:9b`, `qwen3.5:4b` oder `qwen2.5:7b-instruct`
- keine direkte Internetnutzung durch das Modell selbst

### Browser-Zugriff

- `web/server.py`
  - lokaler Proxy und Browser-App fuer:
    - Chat
    - Paperless-Konfiguration
    - Prompt-Bearbeitung
    - Dokument-Review
    - Backfill
- `systemd/ollama-web.service`
  - startet die Weboberflaeche auf Port `3000`
- `scripts/paperless-ai-admin`
  - privilegierter Helfer fuer:
    - Prompt schreiben
    - `paperless.conf` aktualisieren
    - Worker neu starten
- `scripts/paperless-set-ollama-model`
  - schaltet das aktive Paperless-Modell um

## Datenfluss

```text
Dokument -> Paperless Consume -> OCR/Text -> Document gespeichert
        -> POST_CONSUME_SCRIPT -> ai_enrich.py
        -> Prompt + OCR + Metadaten
        -> Ollama
        -> JSON-Antwort
        -> Paperless API PATCH
```

## Review-Datenfluss

```text
Browser :3000 -> web/server.py
        -> Paperless API lesen
        -> Hook-Logik als Preview
        -> Vorschlag anzeigen
        -> optional API PATCH nach Bestaetigung
```

## Sicherheitsmodell

- `Ollama` bleibt lokal auf `127.0.0.1:11434`
- nur die Weboberflaeche auf `3000/tcp` wird bei Bedarf nach aussen freigegeben
- API-Token liegt in `paperless.conf`, nicht im Repository
- Root-Aktionen fuer die Weboberflaeche laufen nur ueber gezielte Helper-Skripte
- `sudoers` gibt nur die benoetigten Einzelbefehle frei

## Bekannte Grenzen

- CPU-only, daher keine Hochleistungs-Inferenz
- kurze bis mittlere Prompts sind gut nutzbar, lange Laeufe sind spuerbar langsamer
- Prompt-Qualitaet bestimmt stark die Qualitaet der Tags und Titel
- paralleler Chat auf demselben `Ollama`-Dienst kann Paperless-Laeufe bremsen
