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
- Scanner-Ingest und Archiv-Pfade von Anfang an sauber planen.
- Keine Annahme, dass Host-Pfade aus der VM 1:1 auf dem NAS existieren.

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

Wichtig:

- `paperless_consume` ist der Eingangsordner fuer neue Scans.
- `paperless_media` ist das eigentliche Dokumentenarchiv.
- beide muessen bewusst geplant werden, damit Scanner, Backup und Container sauber zusammenpassen.

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

## Scanner- und NFS-Konzept

Das muss fuer das NAS ausdruecklich mitgedacht werden.

### Ziel

Ein Scanner soll direkt in einen durch `paperless` konsumierten Ordner schreiben koennen, ohne Shell-Nacharbeit.

### Empfohlene Struktur

```text
/srv/paperless-ai/data/
  consume/
  media/
  export/
  scratch/
```

### Empfehlung fuer den Scanner

Am besten schreibt der Scanner auf einen NAS-lokalen Freigabeordner, der dann als `paperless_consume` in den Container gemountet wird.

Bevorzugt:

- Scanner schreibt auf einen NAS-Ordner
- Docker bind-mountet genau diesen Ordner in den `consume`-Pfad

Weniger gut:

- ein Container greift auf einen extern gemounteten Netzwerkpfad zu, dessen Verhalten bei Dateievents unklar ist

### Wenn NFS trotzdem genutzt wird

Dann muss beachtet werden:

- Dateirechte muessen zum Container-User passen
- der Scanner sollte Dateien moeglichst atomar fertigschreiben
- ideal:
  - zuerst temporaer schreiben
  - danach rename auf finalen Dateinamen
- keine halbfertigen PDFs im Consume-Ordner liegen lassen

### Wichtig fuer Paperless

Vor dem NAS-Betrieb pruefen:

- welcher Container-User schreibt/liest
- welche UID/GID genutzt wird
- ob der Scanner-/NFS-Pfad fuer diesen User lesbar ist
- ob der Ingest auf dem NAS mit grossen PDFs stabil bleibt

## Lessons Learned aus der VM

Diese Punkte muessen im NAS-Docker-Konzept ausdruecklich beruecksichtigt werden.

### 1. Hintergrundjobs duerfen nicht am Webdienst haengen

In der VM sind erste Backfills faktisch abgebrochen, weil sie am Lebenszyklus des Webdienstes hingen.

Konsequenz fuer NAS:

- Hintergrundjobs muessen entkoppelt sein
- Jobstatus muss persistent gespeichert werden
- Webservice-Neustarts duerfen Backfills nicht verlieren

### 2. Task Manager ist Pflicht

Benutzer arbeiten nicht auf Shell oder Konsole.

Konsequenz fuer NAS:

- Jobliste
- Loganzeige
- Abbrechen
- Entfernen
- Fehlergrund
- letzte Aktivitaet

muessen in der Weboberflaeche bleiben.

### 3. OCR ist kein Einzelschalter

Wir hatten reale Unterschiede zwischen:

- `skip`
- `redo`
- `force`
- Tesseract Standarddaten
- `tessdata_best`

Konsequenz fuer NAS:

- OCR-Einstellungen muessen bewusst dokumentiert werden
- fuer problematische PDFs darf OCR konfigurierbar bleiben
- `PaddleOCR` bleibt Zusatzpfad, nicht unbedacht globaler Ersatz

### 4. Logs muessen menschenlesbar sein

Ein Log ohne Zeitstempel oder ohne letzte Aktivitaet hilft in der Praxis zu wenig.

Konsequenz fuer NAS:

- Zeitstempel pro Logzeile
- Fehlergrund
- letzte Dokument-ID
- Jobstatus persistent

### 5. GPU-Erkennung darf nicht schoenreden

Ein sichtbares Grafikgeraet ist noch keine nutzbare KI-GPU.

Konsequenz fuer NAS:

- nur `renderD*` oder ein klar belegbarer GPU-Pfad zaehlt als nutzbar
- ansonsten weiter CPU-only annehmen

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
5. Consume-/Media-/Export-/Backup-Pfade festlegen.
6. Scanner-/NFS-Pfad und Rechte pruefen.
7. `paperless` ohne KI zuerst stabil starten.

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
5. bewusst pruefen, ob nutzbare GPU-/Render-Devices im Container sichtbar sind.

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
4. Task Manager mit persistentem Jobstatus zuerst absichern.

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
5. Logdateien und Statusdateien in persistentem Volume halten.

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
6. Scanner-Ingest inkl. NFS-/Rechte-Test im Realbetrieb pruefen.

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

### 2b. NFS-/Scanner-Ingest

Wenn der Scanner direkt auf einen freigegebenen Ordner schreibt:

- koennen halbfertige Dateien konsumiert werden
- koennen Rechteprobleme entstehen
- koennen Event-/Polling-Unterschiede auftreten

Deshalb muss dieser Pfad frueh und real getestet werden.

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
- der Scanner/NFS-Ingest mit echten PDFs stabil im Consume-Ordner landet
- Containerrechte fuer Consume und Media sauber funktionieren

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
- `docs/SCANNER_INGEST.md`

## Kurzfazit

Das Zielbild fuer das NAS ist klar:

- `paperless` als Docker-Basis
- `ollama` als lokaler Modell-Dienst
- `paperless-ai-web` als zentrale Steuerung
- `PaddleOCR` spaeter optional
- alles reproduzierbar, lokal und git-sauber
