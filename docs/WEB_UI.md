# Web UI

## Ueberblick

Die Weboberflaeche auf Port `3000` ist keine reine Chat-Seite mehr, sondern eine lokale Steuerkonsole fuer:

- Chat mit installierten `Ollama`-Modellen
- Paperless-Modellstrategie
- getrennte Preview- und Vision-Konfiguration
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
- getrenntes Vorschau-OCR-Modell setzen
- OCR-Quelle fuer die Vorschau zwischen `Paperless OCR`, `PaddleOCR Seite 1` und `Hybrid` umschalten
- `PaddleOCR`-API-URL, Timeout und Seitenlimit setzen
- lokale PaddleOCR-Installationshilfe direkt in der UI laden
- eigenes Vision-Modell fuer die Review-Vorschau setzen
- Vision-Seitenlimit, Vision-Timeout und Vision-Tag konfigurieren
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
5. optional `Hybrid OCR + Vision` aktivieren
6. OCR-Vorschlag pruefen
7. auf Hintergrund-Review warten, wenn Vision aktiv ist
8. `Vorschlag uebernehmen`

### PaddleOCR als zweite OCR-Quelle

1. In `Steuerung` die `OCR-Quelle` fuer die Vorschau auf `PaddleOCR Seite 1` oder `Hybrid` stellen
2. Falls noetig `PaddleOCR Installationshilfe` oeffnen
3. `PaddleOCR API URL` pruefen
4. Dokumentvorschau erneut starten

Dabei gilt:

- `PaddleOCR Seite 1` ersetzt den Preview-OCR-Text fuer die Einzeldokument-Vorschau
- `Hybrid` zeigt `PaddleOCR` und `Paperless OCR` gemeinsam als Basis fuer Strukturierung und KI-Vorschlag
- der normale produktive Paperless-Hook bleibt davon unberuehrt

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

## Hybrid Review

Die Dokumentvorschau kann OCR und Vision kombiniert nutzen, ohne den normalen Paperless-Hook zu veraendern.

Ablauf:

- OCR-Vorschlag zuerst
  - die Vorschau erzeugt zuerst mit dem konfigurierten `Vorschau-OCR-Modell` einen schnellen Entwurf
- Vision-Review danach
  - bei kurzen PDFs kann optional ein zweiter Hintergrundlauf mit einem kleineren Vision-Modell starten
- Hintergrundjob statt Vollblockade
  - die UI zeigt sofort den OCR-Vorschlag und pollt den Vision-Review nach
- bewusst begrenzte Vision
  - ueber `Vision nur bis Seitenzahl` werden laengere Dokumente automatisch bei OCR-only belassen

## Externe OCR- und Vision-Modelle

Die Weboberflaeche ist nicht auf ein einzelnes Modell fest verdrahtet. Sie kann dieselbe Dokumentvorschau mit unterschiedlichen lokalen `Ollama`-Modellen fahren.

Wichtig:

- die technische Anbindung zusaetzlicher OCR-/Vision-Modelle funktioniert ueber denselben Vorschaupfad
- Modelle koennen getrennt fuer Vorschau-OCR, Vision-Review und Tag-Review konfiguriert werden
- Modellvergleiche lassen sich dadurch in derselben UI fahren, ohne den produktiven Hook umzubauen
- mit `PaddleOCR` kann zusaetzlich eine zweite OCR-Quelle per lokaler HTTP-API angebunden werden

Die praktischen Tests auf einer CPU-VM fuehrten aber zu einer klaren Produktentscheidung:

- die Anbindung von Modellen wie `glm-ocr`, `gemma3:4b`, `qwen3-vl:4b` oder `openbmb/minicpm-v2.5:q4_K_S` funktionierte technisch
- derselbe Pfad war fuer interaktive Bild+OCR-Tests auf CPU oft zu langsam
- deshalb bleibt die UI standardmaessig auf textbasierte Review-Stufen ausgerichtet
- Vision wird als optionaler, bewusst begrenzter Zusatzpfad behandelt, nicht als Default fuer jedes Dokument

## Sichtbarkeit In Paperless

Wenn ein Vorschlag mit erfolgreicher Vision-Nachpruefung uebernommen wird, kann die UI zusaetzlich einen eigenen Tag setzen:

- Standardname: `KI Vision`
- Standardfarbe: `#d97706`

Dadurch bleiben vision-unterstuetzte Dokumente in `paperless-ngx` spaeter sichtbar filterbar.
