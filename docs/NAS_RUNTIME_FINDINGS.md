# NAS Runtime Findings

## Ziel

Diese Datei dokumentiert die belastbaren Laufzeit- und Modell-Erkenntnisse fuer das NAS-Setup mit Intel Iris Xe.

Sie soll Architekturentscheidungen begruenden und verhindern, dass dieselben Sackgassen spaeter erneut durchlaufen werden.

## Testumgebung

- Host: UGREEN NAS / UGOS
- CPU/iGPU: Intel Iris Xe (Alder Lake)
- Laufzeit:
  - `ollama` auf dem NAS-Docker-Stack
  - separater `ollama`-CPU-Bench-Container
  - isolierter `llama.cpp`-Vulkan-Testcontainer
- Paperless-Testbestand:
  - importierter Dokumentbestand mit realen Problemfaellen
  - insbesondere:
    - `#113` Schule
    - `#111` Gericht
    - `#31` Medizin

## Belastbare Kernergebnisse

### 1. Modelle waren nicht das Hauptproblem

Mehrere Modelle lieferten auf CPU-only saubere strukturierte JSON-Antworten, obwohl sie auf der iGPU ueber `ollama` unbrauchbar oder instabil waren.

Das betrifft insbesondere:

- `qwen3.5:4b`
- `gemma3:4b`
- `llama3.2:3b`
- `qwen2.5:7b`
- `qwen2.5:14b`

Schluss:

- Prompt und JSON-Kanal sind nicht das Grundproblem
- die Hauptursache sitzt im Intel-Vulkan-/GPU-Pfad

### 2. `ollama` + Intel Vulkan ist fuer groessere Modelle unzuverlaessig

Typische Befunde im NAS-Test:

- Runner-Absturz
- `panic: failed to sample token`
- `model runner has unexpectedly stopped`
- Gibberish-Ausgabe trotz erfolgreichem Start

Besonders problematisch waren:

- `qwen3.5:4b`
- `gemma3:4b`
- `llama3.2:3b`
- `qwen2.5:7b`
- `qwen2.5:14b`
- `mistral:7b`
- `phi4-mini`

### 3. Kleine Modelle funktionieren auf der iGPU deutlich besser

Belastbar brauchbar waren auf der Intel Iris Xe:

- `qwen3.5:0.8b`
- `qwen3.5:2b`

Wichtig:

- diese Modelle sind stabiler
- sie sind aber nicht automatisch die besten Briefversteher
- `2b` war schneller/brauchbarer als viele andere GPU-Kandidaten, aber in echten Brieftests klar unter `4b`

### 4. Mixed CPU/GPU-Offloading war kein Qualitaetsfix

Tests mit `num_gpu` bei `ollama` zeigten:

- technisch kann teilweises Offloading laufen
- die Ausgaben blieben trotzdem kaputt oder fachlich unbrauchbar

Schluss:

- Mixed-Modus stabilisiert teils den Runner
- behebt aber auf diesem NAS die numerischen/qualitativen Fehler nicht

## `llama.cpp` als Alternativ-Runtime

### Was funktioniert

Ein isolierter `llama.cpp`-Vulkan-Container konnte auf dem NAS erfolgreich gebaut und gestartet werden.

Wichtige Punkte:

- Basis `debian:bookworm` war fuer den Vulkan-Build zu alt
- mit `debian:trixie` funktionierte der Build
- fuer Runtime waren zusaetzlich `mesa-vulkan-drivers` noetig
- danach wurde die Intel Iris Xe im Container sauber erkannt

### Was nicht direkt funktioniert

Der von `ollama show --modelfile` referenzierte `qwen3.5:4b`-Blob war nicht direkt zu `llama.cpp` kompatibel.

Fehler:

- `qwen35.rope.dimension_sections` hatte in diesem Blob drei Werte statt vier

Schluss:

- nicht jeder Ollama-Blob ist automatisch ein guter `llama.cpp`-Ersatz
- fuer `llama.cpp` sollten kompatible externe GGUF-Dateien genutzt werden

### Was funktioniert hat

`Qwen3.5-4B-Q4_K_M.gguf` aus einem kompatiblen externen GGUF-Repo konnte in `llama.cpp` auf der Iris Xe geladen und abgefragt werden.

Wichtiger Befund:

- `llama.cpp` war auf dem NAS fuer `Qwen3.5-4B` stabiler als `ollama`
- der Kernunterschied war hier das kompatible GGUF-Artefakt

## Dokumenttests ueber `llama.cpp`

### `Qwen3.5-4B-Q4_K_M`

Auf Dokument `#113`:

- Laufzeit: ca. `18.75s`
- stabile Antwort
- qualitativ brauchbar, aber noch nicht perfekt

Beobachtung:

- gute Geschwindigkeit
- sinnvolle Metadatenstruktur
- Thinking-/Code-Fence-Anteile muessen nachgelagert bereinigt werden

### `Qwen3.5-2B-Q4_K_M`

Auf Dokument `#113`:

- Laufzeit: ca. `18.45s`
- stabil
- fuer echten Briefprompt zu schwach
- driftete in langes Thinking und lieferte im Limit kein sauberes End-JSON

### `Qwen3.5-9B-Q4_K_M`

Auf Dokument `#113`:

- Laufzeit: ca. `30.02s`
- stabile Antwort
- qualitativ brauchbar
- langsamer als `4B`

Praktische Einordnung:

- `4B` blieb der bessere Kompromiss
- `9B` war nicht automatisch klar besser, nur schwerer

## Aktuelle praktische Modellstrategie fuer das NAS

### Fuer stabile Qualitaet

- `qwen3.5:4b` auf CPU-only ueber `ollama`
- alternativ `gemma3:4b` oder `llama3.2:3b` auf CPU-only

### Fuer schnellen lokalen GPU-Vorschlag

- `qwen3.5:2b` auf der iGPU

### Fuer experimentellen GPU-Qualitaetspfad

- `llama.cpp` mit kompatiblem externen GGUF
- bevorzugt:
  - `Qwen3.5-4B-Q4_K_M`
  - optional `Qwen3.5-9B-Q4_K_M`

### Nicht als aktueller Produktivpfad priorisieren

- groessere Modelle ueber `ollama` direkt auf Intel Vulkan
- Mixed-Offloading als Qualitaetsstrategie

## Architekturfolgen

Aus diesen Tests folgt fuer das NAS-Zielbild:

1. `ollama` bleibt sinnvoll fuer:
   - CPU-only-Qualitaetsmodelle
   - kleine GPU-Modelle
2. ein optionaler zweiter Runtime-Pfad sollte mitgedacht werden:
   - `llama.cpp`
   - nur fuer kompatible externe GGUFs
3. die Weboberflaeche sollte spaeter zwischen Runtime-Typen unterscheiden koennen:
   - `ollama_local`
   - `ollama_remote`
   - `llama_cpp_local`
4. Thinking-/Code-Fence-Bereinigung ist Pflicht, sobald `llama.cpp` produktiv genutzt wird

## Offene Punkte

- `llama.cpp` als optionaler Provider in den Stack integrieren
- Thinking gezielt deaktivieren oder serverseitig strippen
- denselben Vergleich fuer `#111` und `#31` noch ueber `llama.cpp` vervollstaendigen
- entscheiden, ob `llama.cpp` nur fuer Review oder spaeter auch fuer Import/Backfill genutzt werden soll
