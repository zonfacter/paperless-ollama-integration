# Changelog

## 2026-03-28

### Ollama Thread Tuning

- `Ollama`-Anfragen im produktiven Hook standardmaessig auf `4` Threads begrenzt
- denselben `4`-Thread-Deckel fuer Chat, Preview und Vision in der Port-`3000`-Webkonsole aktiviert
- Thread-Zahl als konfigurierbarer Wert ueber `PAPERLESS_AI_OLLAMA_NUM_THREAD` bzw. `OLLAMA_NUM_THREAD` vorbereitet
- CPU-VM auf einen realistischeren Sweet Spot fuer Inferenz statt ungebremster Mehr-Thread-Auslastung abgestimmt

### Hybrid Review, Preview Controls, And UX Clarification

- Port-`3000`-Review von rein synchroner Vorschau auf asynchronen Hybrid-Workflow weiterentwickelt
- OCR-Vorschlag und Vision-Nachpruefung logisch getrennt
- Vision-Review als Hintergrundjob mit Polling-Endpunkt fuer die UI umgesetzt
- neuer API-Endpunkt fuer Preview-Jobs hinzugefuegt
- neue `Preview & Vision`-Konfiguration in der Weboberflaeche eingefuehrt
- getrennte Steuerung fuer:
  - Vorschau-OCR-Modell
  - Vision-Modell
  - Vision-OCR-Zeichen
  - Vision-Timeout
  - Vision-Seitenlimit
  - Vision-Zusatz-Tag und Tag-Farbe
- Vorschau-Regeln aus hart codierten Defaults in eine eigene Webserver-Konfiguration ausgelagert
- Vision bewusst auf kurze PDFs begrenzt, damit laengere Dokumente nicht unnoetig den Review-Flow blockieren
- erfolgreicher Vision-Review kann beim Uebernehmen einen farbigen Zusatz-Tag in Paperless setzen
- UI um erklaerende Hilfetexte fuer Modellstrategie, Paperless-KI-Konfiguration und Preview/Vision erweitert
- Review-Workspace zeigt jetzt getrennt OCR-Modell, Vision-Modell und Hybrid-Status
- Dokumentation fuer Web-UI, UI-Notizen und Readme-Dateien auf den neuen Hybrid-/Preview-Stand gebracht

## 2026-03-27

### Review Workspace And Qwen 3.5 Hardening

- Hook auf konfigurierbare HTTP-Timeouts umgestellt
- Modell-Fallback fuer `Ollama` ergaenzt
- `Qwen 3.5` im Hook standardmaessig mit `think=false` angebunden
- Schutz gegen halluzinierte Personentags eingebaut
- vorhandene Personentags in den Prompt aufgenommen
- Prompt fuer Rechnungen, Korrespondenz und Tag-Qualitaet geschaerft
- Weboberflaeche auf Port `3000` zu einer Paperless-Steuerkonsole ausgebaut
- Review-Workspace fuer Einzeldokumente mit Vorschau und Apply hinzugefuegt
- Backfill fuer Bestandsdokumente in die Weboberflaeche integriert
- Admin-Helfer und `sudoers`-Beispiele fuer Modellwechsel und Prompt-Speicherung hinzugefuegt
- Architektur-, Betriebs-, UI- und Troubleshooting-Dokumentation erweitert

## 2026-03-26

### Initial Integration

- native `paperless-ngx`-Installation mit lokalem `Ollama` verbunden
- automatischer Post-Consume-Hook fuer Titel, Korrespondenz, Dokumenttyp und Tags dokumentiert
- Prompt aus dem Python-Code in eigene Datei ausgelagert
- minimale Weboberflaeche fuer `Ollama` auf Port `3000` dokumentiert
- fehlerhafte `paperless-scheduler.service` von `qcluster` auf `celery beat` korrigiert
- Installations-, Betriebs-, Sicherheits- und Prompt-Dokumentation hinzugefuegt
