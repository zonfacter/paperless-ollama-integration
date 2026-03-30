# NAS Docker Roadmap

## Ziel

Diese Datei ist die Arbeitsgrundlage fuer den naechsten Ausbauschritt:

- `paperless-ngx`
- OCR
- `ollama`
- die `:3000` Review-/Admin-Weboberflaeche
- optionale Zusatzdienste wie `PaddleOCR`

sollen als eigenstaendiges, reproduzierbares Docker-Gesamtkonzept auf dem NAS laufen.

Die Datei ist bewusst so geschrieben, dass sie auf das NAS kopiert werden kann und dort als direkte Weiterarbeitsbasis dient.

## Leitprinzipien

- Alles containerisiert, soweit sinnvoll.
- Lokale Modelle bleiben lokal.
- Keine persoenlichen Tags, Namen, Orte oder API-Tokens in Git.
- Konfiguration ueber `.env`, JSON-Config, Volumes und Weboberflaeche.
- Dienste klar trennen:
  - Dokumentenverwaltung
  - OCR
  - LLM
  - Review-/Admin-UI
  - Hintergrundjobs
- Erst reproduzierbare Basis, dann Optimierung.

## Zielarchitektur

```text
NAS
|
+-- docker network: paperless-ai
    |
    +-- paperless-webserver
    +-- paperless-consumer
    +-- paperless-task-queue
    +-- paperless-broker (redis)
    +-- paperless-db (postgres)
    +-- gotenberg
    +-- tika
    +-- ollama
    +-- paperless-ai-web (:3000)
    +-- paddleocr-api (:8091, optional)
```

## Zieldienste

### 1. Paperless-Core

- `postgres`
- `redis`
- `gotenberg`
- `tika`
- `paperless-webserver`
- `paperless-consumer`
- `paperless-task-queue`
- optional `paperless-scheduler`, falls nicht im Image/Stack enthalten

### 2. KI-Core

- `ollama`
- persistenter Modell-Volume
- klar definierte Modelle:
  - Hauptmodell
  - Fallback-Modell
  - Preview-OCR-Modell
  - Vision-/PaddleOCR-Ergaenzung

### 3. Review-/Admin-Layer

- `paperless-ai-web`
- Port `3000`
- Aufgabe:
  - Review
  - Prompt-Verwaltung
  - Modellstrategie
  - Tag-Regeln
  - Preview-Konfiguration
  - Task Manager
  - Backfill-Steuerung

### 4. OCR-Zusatz

- `paddleocr-api` optional
- nur fuer:
  - Vergleich
  - Problemfaelle
  - spaeter evtl. `KI Nachpruefen`

## Container-Grenzen

### Container, die bleiben sollten

- `paperless-ngx` selbst
- `ollama`
- `paperless-ai-web`
- `paddleocr-api`

### Nicht in den Container-Images fest verdrahten

- persoenliche Tag-Regeln
- konkrete lokale JSON-Listen
- API-Tokens
- produktive Prompts mit privaten Beispielen

Diese Werte muessen in Volumes oder `.env` liegen.

## Persistente Volumes

Mindestens:

- `paperless_data`
- `paperless_media`
- `paperless_export`
- `paperless_consume`
- `paperless_db`
- `paperless_redis`
- `ollama_data`
- `paperless_ai_web_data`
- `paddleocr_model_cache` optional

Zusatz fuer die Webkonsole:

- Preview-/Job-Status-Dateien
- lokale UI-Config
- Tag-Allowlist-/Regel-JSON

## Ziel fuer Konfigurationsdateien

Auf dem NAS sollte es einen klaren Konfigurationsbereich geben, z. B.:

```text
/srv/paperless-ai/
  .env
  compose.yml
  compose.override.yml
  config/
    paperless.conf
    preview_config.json
    tag_allowlists.json
    tag_rules.json
  prompts/
    ai_enrich_prompt.txt
  logs/
```

Wenn das NAS andere Standards hat, ist die Struktur sinngemaess gleich zu halten.

## Empfohlene Compose-Gliederung

### Basis

- `compose.yml`
  - komplette Zielarchitektur

### Lokal/Host-spezifisch

- `compose.override.yml`
  - Ports
  - Pfade
  - CPU-/RAM-Limits
  - GPU-/iGPU-Mapping spaeter

### Beispielwerte

- `.env.example`
- `preview_config.example.json`
- `tag_allowlists.example.json`
- `tag_rules.example.json`

## Technische Roadmap

### Phase 1: Docker-Basis auf dem NAS

Ziel:

- sauberes, reproduzierbares Docker-Fundament

Aufgaben:

1. Docker-/Compose-Version auf dem NAS pruefen.
2. Netzwerkmodell festlegen.
3. persistente Verzeichnisse/Volumes anlegen.
4. Basis-`compose.yml` fuer `paperless-ngx` erstellen.
5. `paperless` ohne KI zuerst stabil starten.

Abnahmekriterium:

- Upload, OCR, Suche und Dokumentanzeige in `paperless` funktionieren.

### Phase 2: Ollama als Container

Ziel:

- `ollama` sauber im selben Docker-Netz betreiben

Aufgaben:

1. `ollama`-Container mit persistentem Modell-Volume aufsetzen.
2. interne Erreichbarkeit ueber Servicenamen sicherstellen.
3. Modelle ziehen:
   - Hauptmodell
   - Fallback
   - Preview-/Hilfsmodelle
4. CPU-Thread-Default fuer das NAS setzen.

Abnahmekriterium:

- `ollama` antwortet im Docker-Netz sauber.

### Phase 3: Paperless-AI-Web als Container

Ziel:

- bisherige `:3000`-Webkonsole als Docker-Dienst

Aufgaben:

1. `paperless-ai-web` Container bauen.
2. Config-Dateien in Volume verlagern.
3. Endpoints fuer:
   - Jobstatus
   - Review
   - Prompt
   - Preview
   - Tag-Regeln
   - Task Manager
   testen.

Abnahmekriterium:

- `:3000` funktioniert komplett ohne Host-spezifische Shell-Skripte.

### Phase 4: Hook-/Backfill-Integration im Container-Modell

Ziel:

- KI-Verarbeitung nicht mehr VM-/Host-gebunden

Aufgaben:

1. Hook-Dateien und Prompt-Dateien in Container-kompatible Pfade bringen.
2. `paperless.conf`-Ersatz oder Container-Env-Modell festlegen.
3. Backfill-Skripte Docker-kompatibel machen.
4. Hintergrundjobs ohne Systemd, nur ueber Webkonsole + Containerprozess.

Abnahmekriterium:

- neue Dokumente laufen automatisch durch die KI.
- Bestands-Backfills laufen ueber `:3000`.

### Phase 5: OCR-Ausbau

Ziel:

- OCR-Stufen sauber trennen

Stufen:

1. Standard:
   - Tesseract/Paperless OCR
2. Optional:
   - `PaddleOCR` als zweite OCR-Quelle
3. Spaeter:
   - Spezialpfad fuer problematische Dokumente

Abnahmekriterium:

- `paperless`-OCR bleibt stabil.
- `PaddleOCR` ist separat zuschaltbar.

### Phase 6: Betriebsmodus fuer das NAS

Ziel:

- alltagstauglicher Dauerbetrieb

Aufgaben:

1. Restart-Strategie festlegen.
2. Healthchecks einbauen.
3. Task Manager finalisieren.
4. Logs/Retention klaeren.
5. Backup-Konzept fuer:
   - DB
   - Media
   - Config
   - Prompts
   - Jobstatus

Abnahmekriterium:

- Neustart des NAS oder einzelner Container zerstoeert keine Laeufe und keine Konfiguration.

## Was wir bewusst **nicht** zuerst bauen

- Cloud-LLM als Pflichtbestandteil
- Vision-Modelle als Standard fuer alle Dokumente
- harte Abhaengigkeit von GPU-Passthrough
- hostgebundene `systemd`-Skripte als zentrale Orchestrierung

Diese Themen sind spaetere Optionen, nicht Startvoraussetzung.

## Geplanter erster NAS-MVP

Der erste sinnvolle Docker-MVP auf dem NAS ist:

1. `paperless-ngx` Containerstack
2. `ollama` Container
3. `paperless-ai-web` Container
4. Backfill + Review + Task Manager
5. spaeter `paddleocr-api`

Nicht Teil des ersten MVP:

- Vision-VLM im Regelbetrieb
- GPU-Tuning
- aufwendige OCR-Fallback-Matrix

## Empfohlene Arbeitsreihenfolge auf dem NAS

1. `paperless` allein stabilisieren
2. `ollama` dazu
3. `paperless-ai-web` dazu
4. Hook/Backfill wieder integrieren
5. erst dann OCR-Zusatzdienste

Das ist wichtig, damit Fehler klar zuordenbar bleiben.

## Risiken

### 1. CPU-only auf dem NAS

Falls keine nutzbare Render-/GPU-Schnittstelle im Container verfuegbar ist:

- `ollama` bleibt CPU-only
- grosse Vision-Modelle bleiben unpraktisch

### 2. Host-Pfade

Wenn Pfade direkt aus der VM-Welt uebernommen werden, wird der Stack unnoetig fragil.

Deshalb:

- alle Pfade neu fuer NAS-Docker denken
- keine `/opt/paperless`-Annahmen im Zielsystem

### 3. Mischkonfiguration

Nicht halb Host, halb Container.

Ziel muss sein:

- Container sprechen per Docker-Netz
- Konfiguration liegt in Volumes
- keine kritischen Shell-Hooks ausserhalb des Stacks

## Definition of Done

Der NAS-Docker-Stand ist dann erreicht, wenn:

- ein neues Dokument importiert wird
- OCR laeuft
- die KI Titel, Korrespondenz, Dokumenttyp und Tags setzt
- die `:3000`-Konsole Review und Backfill steuert
- der Task Manager Hintergrundjobs ohne Shell sichtbar macht
- Konfiguration komplett ueber Dateien/Volumes und Weboberflaeche steuerbar ist

## Datei fuer den Start auf dem NAS

Wenn diese Datei auf das NAS kopiert wird, sollte der naechste Arbeitsauftrag lauten:

> Baue auf diesem NAS einen Docker-MVP fuer `paperless-ngx + ollama + paperless-ai-web` nach `docs/NAS_DOCKER_ROADMAP.md`. Starte mit Phase 1 und Phase 2, ohne persoenliche Daten oder Tokens ins Repo zu schreiben.

## Empfohlene naechste Artefakte auf dem NAS

Diese Dateien sollen als Naechstes entstehen:

- `compose.yml`
- `.env.example`
- `config/paperless.conf.example`
- `config/preview_config.example.json`
- `config/tag_allowlists.example.json`
- `config/tag_rules.example.json`
- `docs/NAS_DEPLOYMENT.md`
- `scripts/bootstrap-nas-stack.sh`

## Kurzfazit

Das Zielbild fuer das NAS ist klar:

- `paperless` als Docker-Basis
- `ollama` als lokaler Modell-Dienst
- `paperless-ai-web` als zentrale Steuerung
- `PaddleOCR` spaeter optional
- alles reproduzierbar, lokal und git-sauber
