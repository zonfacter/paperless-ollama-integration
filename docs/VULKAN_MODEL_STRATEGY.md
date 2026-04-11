# Vulkan Model Strategy (MI50)

Stand: Vulkan-first auf MI50 (`ollama/ollama:0.20.3`, `OLLAMA_LLM_LIBRARY=vulkan`).

## Zielbild

- Ein stabiler lokaler Modell-Satz fuer:
  - Coding/Agents
  - komplexe Textanalyse (inkl. Recht/Recherche)
  - OCR/Vision
  - schnelles Tagging fuer Paperless
- Einheitliche Modellrollen fuer `paperless-ai`, `open-webui` und `openclaw`.

## Empfohlene Modelle je Aufgabe

- Coding schnell:
  - `qwen2.5-coder:7b`
- Coding tief/architektonisch:
  - `qwen2.5-coder:14b`
- Komplexe Sach-/Rechtstexte, lange Zusammenhaenge:
  - `qwen2.5:14b`
- Schnelles OCR-Tagging/Korrespondenz:
  - `qwen2.5:3b`
- Vision/OCR aus Scan/Bild:
  - `deepseek-ocr:3b`

## Warum diese Auswahl

- `qwen3.5:*` zeigte unter ROCm Runner-Abstuerze.
- Unter Vulkan laufen `qwen3.5:*` zwar, produzieren aber in mehreren Faellen unerwuenschte Thinking-Ausgaben statt direkter Nutzantwort.
- `kwmcglon/gemma-4-e4b-it` war im Praxistest nicht stabil/zuverlaessig genug als Standardprofil.
- `qwen2.5-*` war im Test stabiler und reproduzierbarer fuer Agent-Workflows.

## Paperless-Defaults

Diese Defaults sind als robuste Baseline sinnvoll:

- `PAPERLESS_AI_OLLAMA_MODEL=qwen2.5:14b`
- `PAPERLESS_AI_FALLBACK_MODEL=qwen2.5:3b`
- `PAPERLESS_AI_TAG_OLLAMA_MODEL=qwen2.5:3b`
- `PAPERLESS_AI_TAG_FALLBACK_MODEL=qwen2.5:3b`
- `PAPERLESS_PREVIEW_OCR_MODEL=qwen2.5:3b`
- `PAPERLESS_PREVIEW_VISION_MODEL=deepseek-ocr:3b`

## OpenClaw-Agents (Empfehlung)

- `code-fast` -> `ollama/qwen2.5-coder:7b`
- `code-pro` -> `ollama/qwen2.5-coder:14b`
- `research-legal` -> `ollama/qwen2.5:14b`
- `paperless-tagger` -> `ollama/qwen2.5:3b`
- `vision-ocr` -> `ollama/deepseek-ocr:3b`

## Routing-Matrix (OpenWebUI + OpenClaw)

- Coding-Auftrag mit Projektpfad/Logs:
  - OpenWebUI: `LOCAL Code Fast` oder `LOCAL Code Deep`
  - OpenClaw: `code-fast` oder `code-pro`
- Lange rechtliche/strukturierte Analyse:
  - OpenWebUI: `LOCAL Legal Research`
  - OpenClaw: `research-legal`
- OCR-Tags/Korrespondenz aus Text:
  - OpenWebUI: `LOCAL Paperless Tagger`
  - OpenClaw: `paperless-tagger`
- Scan/Bild/visuelle Extraktion:
  - OpenWebUI: `LOCAL OCR Vision`
  - OpenClaw: `vision-ocr`
- Unklarer Einstieg:
  - OpenWebUI: `LOCAL Task Router`

## Zusammenspiel Paperless + OpenClaw

- `paperless` uebernimmt Ingestion, OCR-Pipeline und Metadatenpersistenz.
- `openclaw` uebernimmt projektartige Aufgaben:
  - Validierung von OCR-Ergebnissen
  - Regel-/Tag-Qualitaetspruefung
  - Batch-Analyse von Problemfaellen
  - Code-/Integrationsaufgaben gegen Workspace
- Der gemeinsame Nenner ist der gleiche lokale Ollama-Endpunkt und ein konsistenter Modellsatz.

## Vision-Autopilot fuer Paperless (Scan-Verstaendnis)

Der Hook kann optional automatisch den Hybrid-Pfad (OCR + Vision) verwenden:

- bevorzugt bei scanlastigen PDFs mit wenig OCR-Text
- oder bei unsicherem Erstresultat (niedrige Confidence / fehlende Kernfelder)
- nutzt den bestehenden `paperless-ai-web` Preview-/Hybrid-Endpunkt und uebernimmt dessen Vorschlag in den Hook-Flow

Wichtige ENV-Schalter:

- `PAPERLESS_AI_VISION_AUTOPILOT_ENABLED=true`
- `PAPERLESS_AI_WEB_URL=http://paperless-ai-web:3000`
- `PAPERLESS_AI_VISION_AUTOPILOT_MAX_PAGES=2`
- `PAPERLESS_AI_VISION_AUTOPILOT_OCR_MIN_CHARS=1800`
- `PAPERLESS_AI_VISION_AUTOPILOT_MIN_CONFIDENCE=0.8`
