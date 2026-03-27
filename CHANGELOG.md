# Changelog

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
