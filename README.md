# Paperless Ollama Integration

Deutsch. For English, see [README.en.md](README.en.md).

Lokale Integration von `paperless-ngx` mit `Ollama` fuer KI-gestuetzte Nachbearbeitung von Dokumenten.

## Kurzuebersicht

### Native VM / Server

- erkennt `/opt/paperless/paperless.conf`
- installiert Hook, Prompt und Backfill nach `/opt/paperless`
- aktualisiert `paperless.conf`
- kann optional die Port-`3000`-Webkonsole installieren

### Docker / Compose

- erkennt typische Compose-Dateien
- erstellt `paperless-ai.env`
- erstellt `docker-compose.override.yml`
- bindet Hook, Prompt und Backfill per Volume Mount ein

### Was du bereithalten solltest

- Paperless API URL
- Paperless API Token
- Ollama URL
- Primaermodell
- optionales Fallback-Modell
- bei Docker: Compose-Datei und Service-Name

Der aktuelle Stand dieses Projekts bildet eine funktionierende Installation mit folgenden Bausteinen ab:

- `paperless-ngx` als native Systemd-Installation
- `Ollama` lokal auf `127.0.0.1:11434`
- konfigurierbare lokale Modelle in `Ollama`
- produktiv erprobte Varianten:
  - `qwen3.5:9b` fuer maximale Qualitaet
  - `qwen3.5:4b` als CPU-Kompromiss
  - `qwen2.5:7b-instruct` als robuste Referenz
- Hook nach erfolgreichem Dokumentimport
- automatische Vergabe von:
  - Titel
  - Korrespondenz
  - Dokumenttyp
  - Tags
- Review- und Steueroberflaeche auf Port `3000`

## Projektinhalt

- `hooks/ai_enrich.py`
  - produktiver Hook fuer Paperless
  - unterstuetzt Modell-Fallback, konfigurierbare Timeouts und `Qwen 3.5` mit deaktiviertem Thinking
- `prompts/ai_enrich_prompt.txt`
  - externer Prompt, getrennt vom Python-Code
- `web/server.py`
  - lokale Weboberflaeche fuer:
    - Chat mit lokalen Modellen
    - Paperless-Konfiguration
    - Prompt-Bearbeitung
    - Review einzelner Dokumente
    - Backfill fuer Bestandsdokumente
- `systemd/paperless-scheduler.service`
  - korrigierte Scheduler-Unit auf `celery beat`
- `systemd/ollama-web.service`
  - Systemd-Unit fuer die lokale Weboberflaeche
- `scripts/paperless-ai-admin`
  - Root-Helfer fuer Prompt, Konfiguration und Worker-Neustarts
- `scripts/paperless-set-ollama-model`
  - Hilfsskript zum Umschalten des aktiven Paperless-Modells
- `scripts/install-paperless-ai.sh`
  - gefuehrter Installer fuer native und Docker-basierte Paperless-Setups
- `scripts/configure-paperless-ai-ollama.sh`
  - Konfigurationshilfe fuer `paperless.conf`
- `docs/`
  - Installations-, Betriebs- und Sicherheitsdokumentation

## Architektur

1. `paperless-ngx` importiert ein Dokument.
2. OCR/Textinhalt und Metadaten stehen in der Paperless-API bereit.
3. `PAPERLESS_POST_CONSUME_SCRIPT` startet `hooks/ai_enrich.py`.
4. Der Hook liest das Dokument per API.
5. `Ollama` erzeugt eine strukturierte JSON-Antwort.
6. Der Hook schreibt Titel, Korrespondenz, Dokumenttyp und Tags zurueck.

## Schnellstart

Empfohlener Einstieg:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh
```

Erst pruefen, was gemacht wuerde:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh --dry-run
```

Der Installer:

- erkennt typische native und Docker-Setups
- sagt frueh, welche Zugangsdaten und Pfade benoetigt werden
- fragt die noetigen Werte interaktiv ab
- schreibt die passenden Dateien fuer den gewaehlten Modus
 
## Aktueller Workflow

### Neue Dokumente

1. Dokument in `paperless-ngx` hochladen oder in den `consume`-Ordner legen.
2. `paperless-ngx` importiert das Dokument und erzeugt OCR.
3. `PAPERLESS_POST_CONSUME_SCRIPT` startet `ai_enrich.py`.
4. Der Hook liest Dokumentinhalt und Metadaten ueber die Paperless-API.
5. Das konfigurierte `Ollama`-Modell erzeugt einen JSON-Vorschlag.
6. Der Hook schreibt das Ergebnis direkt in `paperless-ngx` zurueck.

### Bestehende Dokumente

- Port `3000` bietet einen `Review Workspace` fuer Einzeldokumente:
  - Dokument suchen
  - OCR und aktuelle Metadaten ansehen
  - KI-Vorschau erzeugen
  - Vorschlag uebernehmen oder verwerfen
- Port `3000` bietet einen `Backfill` fuer Bestandsdokumente:
  - nur fehlende Metadaten
  - alle Dokumente
  - nur ausgewaehlte Dokumente

## Wichtige Pfade im produktiven Aufbau

- Hook: `/opt/paperless/ai_enrich.py`
- Prompt: `/opt/paperless/ai_enrich_prompt.txt`
- Paperless-Konfiguration: `/opt/paperless/paperless.conf`
- Ollama-API: `http://127.0.0.1:11434`
- lokale Weboberflaeche: `http://<host>:3000`

## Wichtige Funktionen

- konfigurierbarer Prompt ohne Codeaenderung
- konfigurierbarer OCR-Kontext und Timeout
- Fallback-Modell fuer `Ollama`
- Schutz vor halluzinierten Personentags
- `Qwen 3.5`-Unterstuetzung mit standardmaessig deaktiviertem Thinking
- Review-Workflow vor dem Schreiben fuer einzelne Dokumente

## Dokumentation

- [ROADMAP](ROADMAP.md)
- [CONFIG_EXAMPLES](docs/CONFIG_EXAMPLES.md)
- [INSTALL](docs/INSTALL.md)
- [OPERATIONS](docs/OPERATIONS.md)
- [ARCHITECTURE](docs/ARCHITECTURE.md)
- [PROMPTS](docs/PROMPTS.md)
- [SECURITY](docs/SECURITY.md)
- [WEB_UI](docs/WEB_UI.md)
- [UI_NOTES](docs/UI_NOTES.md)
- [TROUBLESHOOTING](docs/TROUBLESHOOTING.md)

## Hinweise

- Dieses Repository enthaelt keine Tokens oder geheimen Schluessel.
- Host-spezifische Benutzer, Ports und Pfade koennen je nach System angepasst werden.
- Der Prompt ist bewusst als Textdatei ausgelagert, damit er ohne Codeaenderung angepasst werden kann.
