# Sicherheit

## Grundsaetze

- `Ollama` selbst sollte lokal auf `127.0.0.1:11434` gebunden bleiben.
- Nur die Weboberflaeche auf Port `3000` wird bei Bedarf nach aussen freigegeben.
- Tokens und API-Schluessel gehoeren nicht ins Repository.
- Root-Rechte fuer die Weboberflaeche nur ueber minimale Helper-Skripte vergeben.

## Empfohlene Firewall-Haltung

- eingehend standardmaessig `deny`
- explizit nur benoetigte Ports freigeben
- `11434/tcp` nicht nach aussen freigeben
- `5432` und `6379` nur lokal binden

## Lokale Admin-Helfer

Die UI auf Port `3000` aendert sensible Werte nicht direkt selbst, sondern ueber:

- `paperless-ai-admin`
- `paperless-set-ollama-model`

Empfehlung:

- `sudoers` nur auf diese Einzelbefehle begrenzen
- keinen generischen Shell-Zugriff per `sudo` erlauben
- Helper-Skripte nur root-schreibbar halten

## Repository-Hinweis

Dieses Projekt ist fuer ein privates Repository gedacht, weil es:

- Infrastrukturpfade beschreibt
- produktionsnahe Unit-Dateien enthaelt
- Automatisierung fuer einen realen Dokumentenworkflow abbildet

Trotzdem:

- keine Tokens committen
- keine personenbezogenen Testdokumente committen
- keine lokalen Backups oder `.env`-Dateien committen
