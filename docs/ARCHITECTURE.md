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

### Prompt-Schicht

- `prompts/ai_enrich_prompt.txt`
  - enthaelt die fachlichen Regeln fuer die Klassifikation
  - ist absichtlich vom Code getrennt
  - kann ohne Python-Aenderung angepasst werden

### Ollama

- lokaler API-Server auf `127.0.0.1:11434`
- Modell z. B. `qwen2.5:3b-instruct`
- keine direkte Internetnutzung durch das Modell selbst

### Browser-Zugriff

- `web/server.py`
  - leichter lokaler Proxy und Chat-Frontend fuer `Ollama`
- `systemd/ollama-web.service`
  - startet die Weboberflaeche auf Port `3000`

## Datenfluss

```text
Dokument -> Paperless Consume -> OCR/Text -> Document gespeichert
        -> POST_CONSUME_SCRIPT -> ai_enrich.py
        -> Prompt + OCR + Metadaten
        -> Ollama
        -> JSON-Antwort
        -> Paperless API PATCH
```

## Sicherheitsmodell

- `Ollama` bleibt lokal auf `127.0.0.1:11434`
- nur die Weboberflaeche auf `3000/tcp` wird bei Bedarf nach aussen freigegeben
- API-Token liegt in `paperless.conf`, nicht im Repository

## Bekannte Grenzen

- CPU-only, daher keine Hochleistungs-Inferenz
- kurze bis mittlere Prompts sind gut nutzbar, lange Laeufe sind spuerbar langsamer
- Prompt-Qualitaet bestimmt stark die Qualitaet der Tags und Titel
