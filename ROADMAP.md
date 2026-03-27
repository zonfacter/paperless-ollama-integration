# Roadmap

## Zielbild

Die lokale Paperless-KI soll nicht nur Metadaten setzen, sondern einen stabilen Review- und Korrektur-Workflow fuer den Alltag bieten.

## Naechste sinnvolle Ausbaustufen

### 1. Review-Workspace weiter fokussieren

- Dokumentliste und Detailbereich noch staerker fuer breite Monitore optimieren
- Priorisierung fuer problematische Dokumente:
  - keine Korrespondenz
  - keine Tags
  - niedrige Confidence
- direkte Sprungfilter fuer typische Problemfaelle

### 2. Bessere Modelltransparenz

- sichtbare Anzeige, welches Modell den letzten Vorschlag erzeugt hat
- Anzeige, ob Fallback verwendet wurde
- Vergleich zweier Modellvorschlaege fuer dasselbe Dokument

### 3. Qualitaetskontrolle

- optionaler Dry-Run-Modus fuer neue Prompt-Versionen
- kleine Vergleichsberichte fuer Dokumentsets
- mehr Heuristiken gegen schwache Tags und falsche Korrespondenz

### 4. Betriebsfunktionen

- Statuskarten fuer:
  - wartende Dokumente
  - zuletzt gepruefte Dokumente
  - letzte Fehler
- klarere Fehlermeldungen direkt in der UI
- gezielte Neustart-Funktionen fuer Worker

### 5. Taxonomie und Fachregeln

- optionale feste interne Tag-Taxonomie
- getrennte Regelsets fuer:
  - Rechnungen
  - juristische Dokumente
  - medizinische Dokumente
  - Behoerdenpost

## Nicht priorisiert

- GPU-spezifische Optimierung innerhalb dieser VM
- direkte Internetanbindung fuer Modelle
- komplexe Mehrbenutzerfunktionen in der Port-3000-UI
