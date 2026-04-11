# MI50 ROCm Fork Plan

## Ziel

Ein eigener Fork fuer MI50/ROCm, damit experimentelle Ollama-Anpassungen getrennt vom stabilen Standardpfad entwickelt und getestet werden koennen.

## Branch-Strategie

1. `main`
- stabiler Referenzpfad fuer allgemeine Nutzer.

2. `rocm-stable-mi50`
- konservativer Stand fuer produktive MI50-Nutzung.
- Beispiel: `ollama/ollama:0.12.3-rocm`, `OLLAMA_VULKAN=0`.

3. `rocm-next-mi50`
- Experimentierpfad fuer neuere Ollama-/ROCm-Versionen und Patches.
- keine Produktivgarantie.

## Testmatrix (Pflicht vor Merge)

1. Lang-Chat-Stabilitaet
- mindestens 30 Minuten Konversation ohne Hangs.
- kein stiller Abbruch in OpenWebUI/OpenClaw.

2. Modellwechsel
- mindestens 10 Wechsel zwischen 2 Modellen.
- pruefen, ob altes Modell entladen wird.

3. VRAM-Freigabe
- nach Modellwechsel sinkt belegter VRAM reproduzierbar.
- kein stetiges Vollaufen ueber mehrere Wechsel.

4. Parallelbetrieb
- zwei Nutzer/Chats mit verschiedenen Modellen.
- Verhalten bei Lastspitzen dokumentieren.

5. Recovery
- Ollama-Runner-Reset aus Web-UI.
- danach wieder erfolgreiche Requests ohne manuelle Host-Eingriffe.

## Messwerte pro Lauf

- Ollama-Version + Image-Tag
- Modellname, Quantisierung, Kontextgroesse
- Token/s
- GPU Temp, Power, Busy, VRAM%
- Fehlerbild (Timeout, Hang, OOM, Treiber-Reset)

## Merge-Regeln

- nur nach bestandenem Pflichtset in die `rocm-stable-mi50`.
- `main` bekommt nur gehaertete, dokumentierte Aenderungen.
- experimentelle Flags bleiben in `rocm-next-mi50`.

