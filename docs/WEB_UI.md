# Web UI

## Ueberblick

Die Weboberflaeche auf Port `3000` ist keine reine Chat-Seite mehr, sondern eine lokale Steuerkonsole fuer:

- Chat mit installierten `Ollama`-Modellen
- Paperless-Modellstrategie
- Prompt-Bearbeitung
- Review einzelner Dokumente
- Backfill fuer Bestandsdokumente

## Arbeitsbereiche

### Review Workspace

Der Standardbereich fuer den Alltag.

Funktionen:

- Dokumente suchen
- Dokumente mehrfacht auswaehlen
- aktuelle Metadaten ansehen
- OCR-Vorschau anzeigen
- KI-Vorschlag erzeugen
- Vorschlag uebernehmen oder verwerfen
- Einzeldokument oder Batch neu pruefen

### Steuerung

Fuer die eigentliche Konfiguration.

Funktionen:

- Primaermodell auswaehlen
- Fallback aktivieren oder deaktivieren
- Fallback-Modell setzen
- Timeout setzen
- OCR-Zeichen setzen
- Mindest-Confidence setzen
- Prompt laden, aendern und speichern

### Chat

Direkter Testbereich fuer Modelle ohne Paperless-Lauf.

Geeignet fuer:

- kurzer Modellvergleich
- Prompt-Tests
- einfache Funktionschecks

## Layout

Die UI unterstuetzt zwei Modi:

- `Sidebar`
- `Top Tabs`

Der Layout-Modus wird im Browser gespeichert. Dadurch kann derselbe Host auf grossem Monitor und kleinerem Laptop unterschiedlich genutzt werden.

## Typische Nutzung

### Neues Dokument automatisch

- Dokument in `paperless-ngx` importieren
- Hook laeuft automatisch
- nur bei Bedarf im `Review Workspace` nacharbeiten

### Einzelnes Dokument korrigieren

1. Dokument im `Review Workspace` suchen
2. Dokument anklicken
3. OCR und aktuelle Metadaten ansehen
4. `Nur dieses Dokument Vorschau`
5. Vorschlag pruefen
6. `Vorschlag uebernehmen`

### Bestandsdokumente nachziehen

1. Backfill-Modus waehlen
2. optional `Query`, `Limit` oder Dokumentauswahl setzen
3. erst `Vorschau`
4. dann `Backfill starten`

## Technischer Hintergrund

- die UI wird durch `web/server.py` ausgeliefert
- sensible Aenderungen laufen ueber:
  - `paperless-ai-admin`
  - `paperless-set-ollama-model`
- die UI spricht fuer Lesen und Schreiben mit:
  - der Paperless-API
  - dem lokalen `Ollama`
  - den Helper-Skripten
