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

Ergaenzend zu dieser Ziel-Roadmap gibt es reale NAS-Laufzeitbefunde in:

- [NAS_RUNTIME_FINDINGS.md](NAS_RUNTIME_FINDINGS.md)

Diese Datei beschreibt also:

- was gebaut werden soll

und `NAS_RUNTIME_FINDINGS.md` beschreibt:

- was auf der Intel-Iris-Xe-Realhardware bereits verifiziert wurde

## Leitprinzipien

- Alles containerisiert, soweit sinnvoll.
- Lokale Modelle bleiben lokal.
- Keine persoenlichen Tags, Namen, Orte oder API-Tokens in Git.
- Konfiguration ueber `.env`, JSON-Config, Volumes und Weboberflaeche.
- Secrets getrennt von Beispielkonfiguration halten.
- Dienste klar trennen:
  - Dokumentenverwaltung
  - OCR
  - LLM
  - Review-/Admin-UI
  - Hintergrundjobs
- Erst reproduzierbare Basis, dann Optimierung.
- Scanner-Ingest und Archiv-Pfade von Anfang an sauber planen.
- Keine Annahme, dass Host-Pfade aus der VM 1:1 auf dem NAS existieren.
- Modellverwaltung muss fuer Nicht-Programmierer ueber die Weboberflaeche erreichbar sein.
- Lokale und externe KI-Dienste muessen als gleichwertige Quellen gedacht werden.
- Kein Docker-Socket in der Weboberflaeche als stillschweigende Abkuerzung.
- Restore-Faehigkeit ist genauso wichtig wie Backup.
- Containerrechte, UID/GID und Dateibesitzer werden als eigenes Thema behandelt, nicht als spaeterer Nachtrag.

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
    +-- open-webui (:8081, optional)
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

Wichtiger Realitaetspunkt fuer das NAS:

- `ollama` bleibt Pflichtbestandteil
- aber die Architektur darf nicht davon ausgehen, dass groessere GPU-Modelle auf Intel Vulkan ueber `ollama` stabil laufen
- deshalb sollte von Anfang an Platz fuer eine zweite lokale Runtime bestehen

### 2b. Externe KI-Quellen

Das Zielsystem darf nicht nur lokale `ollama`-Container voraussetzen.

Es muss spaeter auch unterstuetzen:

- externes `ollama` auf einem anderen Host
- andere Docker-Dienste mit eigener KI-/OCR-API
- spaeter optional Cloud-Provider

Das heisst:

- der KI-Layer braucht ein Provider-Modell
- nicht nur einen fest verdrahteten lokalen Container

### 2c. Zweite lokale Runtime

Fuer das NAS sollte ein optionaler zweiter lokaler Runtime-Pfad mitgedacht werden:

- `llama.cpp`

Begruendung:

- auf der Intel Iris Xe war `llama.cpp` mit kompatiblen externen GGUFs bereits technisch erfolgreich
- dieser Pfad kann fuer GPU-Modelle relevant werden, die in `ollama` auf Intel Vulkan instabil sind

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

### 3b. Optionaler Chat-Layer

- `open-webui`
- Port `8081`
- Aufgabe:
  - direkter Modellchat
  - manueller Modellvergleich
  - spaeter optionaler Zugriff auf `llama.cpp` als OpenAI-kompatiblen Provider

Wichtig:

- `open-webui` ersetzt nicht `paperless-ai-web`
- Review, Regelverwaltung, Backfill und Task Manager bleiben im Projekt bewusst getrennt

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
- `open-webui`
- `paddleocr-api`

### Nicht in den Container-Images fest verdrahten

- persoenliche Tag-Regeln
- konkrete lokale JSON-Listen
- API-Tokens
- produktive Prompts mit privaten Beispielen

Diese Werte muessen in Volumes oder `.env` liegen.

## Modell- und Provider-Management in der Weboberflaeche

Das ist ein Pflichtteil des NAS-Zielbilds.

### Ziel

Die Weboberflaeche muss spaeter ueber eine eigene Seitenleiste / Menuepunkte verfuegen fuer:

- aktive Modelle
- Modellstrategie
- Modellquellen
- Installationshilfen
- externe Provider / externe Docker-Dienste

### Minimale Menuepunkte

Im NAS-Zielbild sollte die linke Navigation mindestens diese Bereiche haben:

- `Review`
- `Task Manager`
- `Modelle`
- `Provider`
- `OCR`
- `Steuerung`
- `Chat`
- optional zusaetzlich klar getrennt:
  - `Open WebUI`

### Bereich `Modelle`

Dort muss spaeter moeglich sein:

- installierte Modelle anzeigen
- aktives Paperless-Modell setzen
- Fallback-Modell setzen
- Preview-/Review-Modelle setzen
- Modellbeschreibung anzeigen
- Modell loeschen oder deaktivieren
- Installationsstatus sehen

### Bereich `Provider`

Dort muss spaeter moeglich sein:

- lokales `ollama` aktivieren
- lokales `llama.cpp` aktivieren
- externes `ollama` per URL eintragen
- alternative KI-Docker-Dienste eintragen
- Healthcheck / Verbindungstest ausfuehren
- zwischen Providern umschalten

Fuer den optionalen Chat-Layer sollte zusaetzlich moeglich sein:

- `Open WebUI` gegen lokales `ollama` betreiben
- `Open WebUI` spaeter gegen `llama.cpp` als OpenAI-kompatiblen Dienst richten

### Bereich `System / Updates`

Dort muss spaeter moeglich sein:

- aktuelle lokale Version anzeigen
- verfuegbare neue Version erkennen
- Changelog/Release-Hinweis anzeigen
- kontrolliertes Update ueber den Docker-Compose-Dienst anstossen
- vor dem Update auf Backup/Restore-Hinweis aufmerksam machen
- nach dem Update klar zeigen, ob:
  - Container neu gestartet wurden
  - Konfiguration erhalten blieb
  - Migrationen erfolgreich liefen

### Installationsmoeglichkeiten fuer Modelle

Das System soll spaeter mehrere Wege unterstuetzen:

1. direktes Ziehen ueber Modellname
   - Beispiel: `qwen3.5:9b`
2. Installation ueber externen Modell-Link
   - Beispiel: Verweis auf offizielle Modellseite
3. Installationshilfe / One-click-Vorlage
   - Beispiel: `ollama pull ...`
4. spaeter optional:
   - importierte Modelfiles
   - vorkonfigurierte Provider-Presets

### Wichtige Designregel

Die Weboberflaeche muss fuer Nutzer verstaendlich machen:

- wo ein Modell wirklich laeuft
  - lokal im NAS-Docker
  - extern in anderem Docker
  - extern auf anderem Host
- welches Modell aktuell fuer welchen Schritt genutzt wird
  - Import
  - Preview
  - Tag-Review
  - Chat
  - OCR-Zusatzpfad

## Provider-Abstraktion

Das NAS-Zielbild muss von Anfang an so gebaut werden, dass nicht alles an einen einzelnen lokalen `ollama`-Container gekoppelt ist.

### Provider-Typen

Mindestens vorbereiten:

- `ollama_local`
- `ollama_remote`
- `ocr_api_local`
- `ocr_api_remote`
- spaeter optional `openai_compatible`

### Beispielhafte externe Ziele

- anderer Docker-Host im NAS
- anderer Server im LAN
- spezialisierter OCR-Docker
- spaeter Cloud-API

### Konsequenz fuer die Architektur

Die Weboberflaeche darf nicht voraussetzen:

- dass Modellinstallation immer lokal passiert
- dass alle Modelle im selben Container liegen
- dass `ollama pull` der einzige Weg ist

Stattdessen braucht es:

- Provider-Konfiguration
- Modell-Metadaten
- Healthchecks
- Zuweisung von Rolle -> Provider -> Modell

## Update- und Versionskonzept

Das NAS-Zielbild braucht einen sauberen Update-Pfad.

### Ziel

Ein Nutzer soll spaeter in der Weboberflaeche sehen koennen:

- welche Version lokal laeuft
- ob es eine neuere Version gibt
- ob ein Update nur das Web-UI betrifft oder den gesamten Stack

### Image-Distribution

Fuer den NAS-Betrieb soll von Anfang an mitgedacht werden, woher Container-Images kommen.

Moegliche Wege:

- Build lokal auf dem NAS
- Build ueber GitHub Actions
- Push nach Docker Hub
- spaeter optional GHCR

Pragmatische Empfehlung:

- reproduzierbare Builds ueber GitHub
- veroeffentlichte Images in Docker Hub oder GHCR
- lokaler NAS-Build nur als Ausnahme oder Testpfad

So kann die Weboberflaeche spaeter auch klar unterscheiden:

- welche Version lokal deployed ist
- aus welcher Registry das Image stammt
- ob ein Update aus GitHub Release, Docker Hub Tag oder lokalem Build kommt

### Mindestanforderungen

- lokale Versionsinfo aus einem klaren Build-/Release-Merkmal
- Remote-Versionscheck gegen GitHub Releases oder ein spaeteres Release-Manifest
- Update nicht blind im Hintergrund, sondern bewusst bestaetigt
- Hinweis, welche Container betroffen sind
- Hinweis, ob ein DB-/Media-/Config-Backup empfohlen oder Pflicht ist

### Wichtige Designregel

Ein Update darf nie davon abhaengen, dass Konfiguration im Container selbst liegt.

Deshalb muessen erhalten bleiben:

- Dokumente und Archivdaten auf Host-Volumes
- Prompt-Dateien auf Host-Volumes
- JSON-Konfiguration fuer:
  - Preview
  - Tag-Regeln
  - Provider
  - Modelle
- Jobstatus-/Task-Manager-Daten
- optionale OCR-/PaddleOCR-Caches nur, wenn gewuenscht

### Update-Zielbild

Die Weboberflaeche darf spaeter ein Compose-Update anstossen, aber nur unter klaren Bedingungen:

- nur fuer den definierten NAS-Stack
- kein generischer Docker-Socket-Vollzugriff
- bevorzugt ueber einen schmalen, klar begrenzten Update-Worker oder NAS-spezifischen Update-Helfer
- mit Rueckmeldung zu:
  - Pull erfolgreich
  - Container neu erstellt
  - Healthchecks wieder gruen

### Nicht verwechseln

- Container-Image aktualisieren
- Konfiguration aktualisieren
- Daten migrieren

sind drei getrennte Dinge und muessen in UI und Doku auch getrennt kommuniziert werden.

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
- Provider-/Modell-JSON
- Prompt-Dateien
- OCR-Zwischencache nur, wenn bewusst begrenzt und aufraeumbar
- Versions-/Update-State

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
  data/
    consume/
    media/
    export/
  secrets/
    paperless_api_token
    postgres_password
    optional_remote_provider_token
```

Wenn das NAS andere Standards hat, ist die Struktur sinngemaess gleich zu halten.

Wichtig:

- Beispielwerte gehoeren in `.env.example` und `config/*.example.json`.
- echte Tokens und Passwoerter gehoeren in `secrets/` oder NAS-Secrets, nicht in normale Beispiel-Dateien.
- die Weboberflaeche darf produktive Secrets nicht im Klartext aus Git-Beispielen ableiten.

## Pflichtthemen, die in Docker-Projekten oft zu spaet bedacht werden

Diese Punkte muessen vor dem eigentlichen NAS-Start bewusst eingeplant werden.

### 1. Backup **und** Restore

Nicht nur sichern, sondern rueckspielen koennen.

Pflicht:

- `postgres`-Backup
- `paperless_media`
- `paperless_export`
- Prompt-/Config-Dateien
- Jobstatus-/Review-Konfiguration

Pflicht-Nachweis:

- ein Test-Restore in ein zweites Zielverzeichnis oder eine Test-Compose
- danach pruefen:
  - Dokumente sichtbar
  - OCR/Textindex plausibel
  - Review-/Task-Manager-Konfiguration noch vorhanden

### 2. Rechte- und Besitzmodell

Vor dem NAS-Start klar festlegen:

- welcher User/Gruppenkontext in den Containern laeuft
- welche UID/GID auf NAS-Freigaben und NFS-Freigaben gelten
- wer Schreibrechte auf:
  - `consume`
  - `media`
  - `export`
  - `config`
  - `logs`
  hat

Ohne diese Klarheit werden spaeter halbfertige Imports und nicht beschreibbare Config-Dateien die Regel.

### 3. Netzfreigabe und Reverse Proxy

Vorab entscheiden:

- laeuft `paperless-ai-web` direkt auf `:3000`
- oder hinter einem Reverse Proxy des NAS
- oder hinter `https`/LAN-Proxy

Pflicht:

- nur die noetigen Ports nach aussen oeffnen
- interne Container-Kommunikation ueber Docker-Netz
- `ollama` und optionale OCR-APIs nicht unnoetig direkt ins LAN exponieren

### 4. Upgrade-Strategie

Nicht nur den ersten Start planen.

Pflicht:

- feste Image-Tags statt blind `latest`
- definierter Update-Ablauf
- kurze Checkliste fuer Rollback
- Datenbank-Backup vor Image-Upgrades
- sichtbare Versionen in der Weboberflaeche
- kein Updatepfad, der Containerdaten statt Host-Daten vertraut

### 5. Schreibpfade der Weboberflaeche

Die `:3000`-Oberflaeche darf spaeter nicht wieder auf Host-Helfer oder willkuerliche Shell-Skripte angewiesen sein.

Stattdessen:

- Web-UI schreibt nur in klar gemountete Config-/State-Verzeichnisse
- Hintergrundjobs werden ueber definierte Prozesse gestartet
- keine implizite Abhaengigkeit auf `systemd`
- kein stiller Bedarf an Root auf dem Host

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
- optionaler Vorstufen-Ordner:
  - `incoming/`
  - `consume/`
  - erst nach Dateivollstaendigkeit verschieben/umbenennen

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
- wenn noetig, kleinen Staging-/Promote-Mechanismus vorsehen
  - Beispiel:
    - Scanner schreibt nach `incoming/`
    - ein leichter Watcher verschiebt nur abgeschlossene Dateien nach `consume/`

### Wichtig fuer Paperless

Vor dem NAS-Betrieb pruefen:

- welcher Container-User schreibt/liest
- welche UID/GID genutzt wird
- ob der Scanner-/NFS-Pfad fuer diesen User lesbar ist
- ob der Ingest auf dem NAS mit grossen PDFs stabil bleibt
- ob das gewaehlte NAS-Dateisystem/Share-Verhalten Polling statt Events erfordert
- ob der Scanner denselben Dateinamen mehrfach wiederverwendet

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

Zusaetzlich:

- Fortschritt `x / n`
- Start-/Endzeit
- sichtbarer Returncode oder Fehlerklasse
- Jobhistorie mit manueller Bereinigung

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
- OCR-Quelle fuer Review und fuer produktiven Import bewusst trennen
- nicht jede OCR-Experimentierquelle direkt in den Auto-Import haengen

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
  - feste Service-Namen
  - feste Volumes
  - Healthchecks, wo sinnvoll

### Lokal/Host-spezifisch

- `compose.override.yml`
  - Ports
  - Pfade
  - CPU-/RAM-Limits
  - GPU-/iGPU-Mapping spaeter
  - Reverse-Proxy-spezifische Anpassungen
  - NAS-spezifische UID/GID oder Device-Mappings

### Beispielwerte

- `.env.example`
- `preview_config.example.json`
- `tag_allowlists.example.json`
- `tag_rules.example.json`
- `providers.example.json`
- `models.example.json`

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
8. Zeitzone/Locale bewusst setzen.
9. Restore-Test fuer Basisdaten vor KI-Aufbau vorbereiten.
10. Host-Datenpfade so anlegen, dass Updates Container gefahrlos ersetzen duerfen.

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
6. Provider-Struktur so anlegen, dass spaeter auch `ollama_remote` moeglich bleibt.
7. Healthcheck fuer `ollama` im Docker-Netz setzen.

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
5. neue Modell-/Provider-Menuepunkte vorbereiten.
6. keine Docker-Socket-Abhaengigkeit im Webcontainer einbauen.
7. alle Web-Schreibpfade auf Volume-Dateien begrenzen.

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
6. Rollenmodell fuer KI-Schritte festlegen:
   - Import
   - Fallback
   - Preview
   - Tag-Review
   - OCR-Zusatz
7. Abbruch, Neustart und Job-Leichen explizit behandeln.
8. Concurrency festlegen:
   - wie viele Backfills gleichzeitig erlaubt sind
   - ob Preview/Chat waehrend Backfill gedrosselt werden

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
7. Provider-Wechsel und Modell-Neuinstallation ohne Shell pruefen.
8. Upgrade-/Rollback-Playbook festhalten.
9. Restore-Test einmal real durchspielen.
10. Versionscheck und Update-Hinweis in der Weboberflaeche finalisieren.

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
5. vorbereitete Modell-/Provider-Konfiguration
5. spaeter `paddleocr-api`

Nicht Teil des ersten MVP:

- Vision-VLM im Regelbetrieb
- GPU-Tuning
- aufwendige OCR-Fallback-Matrix
- vollautomatische Installation beliebiger Fremdmodelle aus jeder Quelle
- direkter Schreibzugriff der Weboberflaeche auf den Docker-Socket
- vollautomatische unbestaetigte Self-Updates

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
- keine versteckten absoluten Pfade in Prompts, Jobs oder UI-Defaults
- Daten duerfen nie nur im Container-Layer liegen

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

### 4. Zu viele gleichzeitige Rollen fuer ein Modell

Wenn derselbe `ollama`-Dienst gleichzeitig bedienen soll:

- Auto-Import
- Preview
- Chat
- Tag-Review
- OCR-Experimente

dann braucht der NAS-Stack klare Prioritaeten oder Limits.

Sonst drohen:

- Timeouts
- schwer erklaerbare Latenz
- falsche Rueckschluesse auf Modellqualitaet

Deshalb frueh festlegen:

- Thread-Default
- gleichzeitige Jobanzahl
- welche Rollen im Zweifel Vorrang haben

### 5. Migration der bestehenden VM-Daten

Der Umzug auf das NAS ist nicht nur ein Neuaufbau, sondern sehr wahrscheinlich eine Uebernahme des bestehenden Archivs.

Dabei muessen getrennt gedacht werden:

- Datenbank-Inhalt
- `paperless_media`
- `paperless_export`
- OCR-/Index-Stand
- Konfiguration
- Prompt-/Tag-/Provider-Dateien

Pflicht vor dem Umzug:

- entscheiden, ob neu importiert oder migriert wird
- bei Migration:
  - DB und Media immer als zusammengehoeriges Paar behandeln
  - keine Teilmigration nur eines von beiden
- nach dem Restore pruefen:
  - Dokumentanzahl
  - Seitenanzahl plausibel
  - Suchindex
  - consume-Verhalten fuer neue Dokumente

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
- die Weboberflaeche Modellrollen und Provider sichtbar trennt
- lokale und externe KI-Quellen technisch vorbereitet sind
- ein Test-Backup erfolgreich wiederhergestellt wurde
- keine produktive Funktion Root-Zugriff auf dem Host voraussetzt
- Versionsstand und Update-Hinweis in der Weboberflaeche sichtbar sind
- ein Container-Update die Host-Daten und Konfiguration unveraendert beibehaelt

## Datei fuer den Start auf dem NAS

Wenn diese Datei auf das NAS kopiert wird, sollte der naechste Arbeitsauftrag lauten:

> Baue auf diesem NAS einen Docker-MVP fuer `paperless-ngx + ollama + paperless-ai-web` nach `docs/NAS_DOCKER_ROADMAP.md`. Starte mit Phase 1 und Phase 2, ohne persoenliche Daten oder Tokens ins Repo zu schreiben.

## Empfohlene naechste Artefakte auf dem NAS

Diese Dateien sollen als Naechstes entstehen:

- `compose.yml`
- `compose.override.example.yml`
- `.env.example`
- `.secrets.example/`
- `config/paperless.conf.example`
- `config/preview_config.example.json`
- `config/tag_allowlists.example.json`
- `config/tag_rules.example.json`
- `config/providers.example.json`
- `config/models.example.json`
- `config/version.example.json`
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
