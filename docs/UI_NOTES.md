# UI Notes

## Zweck

Diese Notiz beschreibt die beabsichtigte visuelle und funktionale Richtung der Port-`3000`-Oberflaeche. Sie ersetzt keine Screenshots, hilft aber spaeter bei Nachbau, Politur oder echter UI-Dokumentation.

## Grundidee

Die UI ist keine allgemeine Chat-App, sondern eine lokale Arbeitskonsole fuer Paperless.

Deshalb gelten diese Prioritaeten:

1. Review vor Chat
2. Dokumentfokus vor Modellspielerei
3. klares Arbeiten vor maximaler Funktionsdichte

## Aufbau

### Hero

- kurze Einordnung des Systems
- keine lange Marketingflaeche
- schnelle Orientierung fuer den aktuellen Arbeitsmodus

### Navigation

- wenige Hauptbereiche
- geeignet fuer Sidebar oder Top-Tabs
- nicht doppelt mit Branding oder Erklaertext ueberladen

### Review Workspace

Der wichtigste Bereich.

Soll visuell den Charakter eines echten Arbeitsbereichs haben:

- links oder oben: Suche und Dokumentauswahl
- rechts oder darunter: aktueller Stand, OCR, Vorschlag
- klare Aktionstraeger:
  - Vorschau
  - erneut pruefen
  - uebernehmen
  - verwerfen

### Steuerung

Funktional, aber nicht dominant.

- Modellwahl
- Fallback
- Timeout
- OCR-Zeichen
- Prompt

### Chat

Nebensache, aber nuetzlich fuer schnelle Modelltests.

## Monitor-Hinweise

### Ultrawide

Auf breiten Monitoren sollte die zusaetzliche Breite nicht nur leeren Raum erzeugen.

Sinnvoll:

- mehrspaltiger Review-Bereich
- klare Trennung von Liste und Detail
- Navigation nicht ueber dem Content schweben lassen

### Kleinere Displays

- Umschaltung auf Top-Tabs oder einspaltige Darstellung
- keine Pflicht zur Sidebar

## Stilprinzipien

- helles, sachliches Arbeitslayout statt Dark-Showcase
- klare Karten statt schwerer Panels
- moderne Abstaende und Radien, aber keine verspielte UI
- Status und Aktionen muessen schnell auffindbar sein
