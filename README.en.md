# Paperless Ollama Integration

English version. For the German version, see [README.md](README.md).

Local integration of `paperless-ngx` with `Ollama` for AI-assisted document post-processing.

## Quick Overview

### Native VM / Server

- detects `/opt/paperless/paperless.conf`
- installs hook, prompt, and backfill into `/opt/paperless`
- updates `paperless.conf`
- can optionally install the port `3000` web console

### Docker / Compose

- detects common Compose files
- creates `paperless-ai.env`
- creates `docker-compose.override.yml`
- mounts hook, prompt, and backfill into the Paperless container

### What You Should Have Ready

- Paperless API URL
- Paperless API token
- Ollama URL
- primary model
- optional fallback model
- for Docker: Compose file and service name

The current state of this project reflects a working setup with the following building blocks:

- native `paperless-ngx` systemd installation
- local `Ollama` on `127.0.0.1:11434`
- configurable local models in `Ollama`
- proven model options:
  - `qwen3.5:9b` for maximum quality
  - `qwen3.5:4b` as a CPU-friendly compromise
  - `qwen2.5:7b-instruct` as a robust reference
- post-consume hook after document import
- automatic enrichment of:
  - title
  - correspondent
  - document type
  - tags
- review and control UI on port `3000`
- separate preview/vision rules for the review UI
- OCR tuning for scan PDFs with `force`, `deu+eng`, and optional `tessdata_best`

## Project Contents

- `hooks/ai_enrich.py`
  - production hook for Paperless
  - supports model fallback, configurable timeouts, `Qwen 3.5` with thinking disabled, and a bounded Ollama thread count for CPU VMs
- `prompts/ai_enrich_prompt.txt`
  - external prompt, separated from Python code
- `web/server.py`
  - local web console for:
    - chat with local models
    - Paperless configuration
    - dedicated preview and vision configuration for document review
    - prompt editing
    - single-document review
    - backfill for existing documents
  - applies the same Ollama thread cap to chat, preview, and vision requests
- `systemd/paperless-scheduler.service`
  - corrected scheduler unit using `celery beat`
- `systemd/ollama-web.service`
  - systemd unit for the local web console
- `scripts/paperless-ai-admin`
  - privileged helper for prompt updates, configuration changes, and worker restarts
- `scripts/paperless-set-ollama-model`
  - helper script to switch the active Paperless model
- `scripts/install-paperless-ai.sh`
  - guided installer for native and Docker-based Paperless setups
- `scripts/configure-paperless-ai-ollama.sh`
  - configuration helper for `paperless.conf`
- `docs/`
  - installation, operations, architecture, security, and UI documentation
- `docker/paddleocr-api/`
  - optional `PaddleOCR` API container for OCR experiments and later integration

## Architecture

1. `paperless-ngx` imports a document.
2. OCR text and metadata become available through the Paperless API.
3. `PAPERLESS_POST_CONSUME_SCRIPT` starts `hooks/ai_enrich.py`.
4. The hook reads the document through the API.
5. `Ollama` generates a structured JSON response.
6. The hook writes title, correspondent, document type, and tags back to Paperless.

## Quick Start

Recommended entry point:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh
```

Preview first without changing anything:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh --dry-run
```

The installer:

- detects common native and Docker-based setups
- tells you early which credentials and paths are required
- asks for the needed values interactively
- writes the right files for the chosen mode

## Current Workflow

### New Documents

1. Upload a document to `paperless-ngx` or place it in the `consume` folder.
2. `paperless-ngx` imports the document and generates OCR.
3. `PAPERLESS_POST_CONSUME_SCRIPT` starts `ai_enrich.py`.
4. The hook reads document content and metadata through the Paperless API.
5. The configured `Ollama` model generates a JSON proposal.
6. The hook writes the result back to `paperless-ngx`.

### Existing Documents

- Port `3000` provides a `Review Workspace` for single documents:
  - search documents
  - inspect OCR and current metadata
  - generate an AI preview
  - optionally use hybrid `OCR + Vision` for short PDFs
  - apply or discard the proposal
- Port `3000` provides `Backfill` for existing documents:
  - only documents with missing metadata
  - all matching documents
  - only selected documents

## Important Paths In A Production Setup

- hook: `/opt/paperless/ai_enrich.py`
- prompt: `/opt/paperless/ai_enrich_prompt.txt`
- Paperless configuration: `/opt/paperless/paperless.conf`
- Ollama API: `http://127.0.0.1:11434`
- local web console: `http://<host>:3000`

## Key Features

- configurable prompt without code changes
- configurable OCR context and timeout
- OCR tuning for scan PDFs with `force`, `deu+eng`, and `tessdata_best`
- fallback model support for `Ollama`
- protection against hallucinated person tags
- `Qwen 3.5` support with thinking disabled by default
- review workflow before writing metadata for single documents
- asynchronous hybrid preview with OCR first and optional vision follow-up
- separate web configuration for preview OCR model, vision model, page limit, and vision tagging

## Tested Model Integration

This project can cleanly wire multiple local AI models into the same hook, preview, and review pipeline.

Different models can be assigned independently to:

- the normal Paperless hook
- preview OCR
- vision review
- tag review

Successfully integrated and exercised through the same local path were, among others:

- `qwen3.5:4b`
- `qwen3.5:9b`
- `qwen2.5:7b-instruct`
- `qwen2.5:14b-instruct`
- `glm-ocr`
- `glm-ocr:q8_0`
- `gemma3:4b`
- `qwen3-vl:4b`
- `openbmb/minicpm-v2.5:q4_K_S`

The key takeaway is:

- the technical integration works
- practical usability depends heavily on runtime on the target hardware

## OCR Notes

For real scan PDFs, `PAPERLESS_OCR_MODE=force` proved more robust than `redo` in this project once cleanup options such as `clean`, `deskew`, and `rotate-pages` were enabled together.

Recommended OCR baseline for German-heavy scans:

- `PAPERLESS_OCR_LANGUAGE=deu+eng`
- `PAPERLESS_OCR_MODE=force`
- `PAPERLESS_OCR_IMAGE_DPI=300`
- `PAPERLESS_OCR_CLEAN=clean`
- `PAPERLESS_OCR_DESKEW=true`
- `PAPERLESS_OCR_ROTATE_PAGES=true`

If you use `tessdata_best`, the target data path must contain more than just `.traineddata` files.
It also needs the standard Tesseract support files:

- `configs/`
- `tessconfigs/`
- `pdf.ttf`

A language-only directory without those files can cause OCRmyPDF to fail when requesting `hocr` and `txt` output.

## Findings From Vision And OCR Model Testing On CPU VMs

The most important practical findings from the model tests are:

- small to mid-sized text models remain the most usable default for this architecture
- pure text pipelines with OCR cleanup, structure extraction, and rule-based post-processing are much more reliable locally than full multimodal image+OCR prompts
- small vision/OCR models integrated cleanly, but were still often too slow on the tested CPU-only VM for interactive or synchronous review
- a smaller multimodal model does not automatically mean an acceptable document runtime

This project therefore documents two separate layers:

- practical on local CPU:
  - `paperless-ngx` OCR
  - OCR cleanup
  - OCR structure extraction
  - rule-based post-processing
  - text models for title, correspondent, document type, and tags
- practical later or on stronger hardware:
  - dedicated vision/OCR models for rendered document pages
  - GPU passthrough
  - external or cloud-backed review stages

In short:

- the integration path for vision/OCR models works
- the CPU VM is the limiting factor
- the default architecture in this repository therefore stays OCR- and text-centric

## Documentation

- [ROADMAP](ROADMAP.md)
- [CONFIG_EXAMPLES](docs/CONFIG_EXAMPLES.md)
- [INSTALL](docs/INSTALL.md)
- [OPERATIONS](docs/OPERATIONS.md)
- [ARCHITECTURE](docs/ARCHITECTURE.md)
- [PROMPTS](docs/PROMPTS.md)
- [SECURITY](docs/SECURITY.md)
- [WEB_UI](docs/WEB_UI.md)
- [UI_NOTES](docs/UI_NOTES.md)
- [TROUBLESHOOTING](docs/TROUBLESHOOTING.md)
- [PADDLEOCR_API](docs/PADDLEOCR_API.md)

## Notes

- This repository does not contain tokens or secret keys.
- Host-specific users, ports, and paths may need to be adapted.
- The prompt is intentionally stored as a text file so it can be adjusted without changing code.
