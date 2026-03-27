# Paperless Ollama Integration

English version. For the German version, see [README.md](README.md).

Local integration of `paperless-ngx` with `Ollama` for AI-assisted document post-processing.

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

## Project Contents

- `hooks/ai_enrich.py`
  - production hook for Paperless
  - supports model fallback, configurable timeouts, and `Qwen 3.5` with thinking disabled
- `prompts/ai_enrich_prompt.txt`
  - external prompt, separated from Python code
- `web/server.py`
  - local web console for:
    - chat with local models
    - Paperless configuration
    - prompt editing
    - single-document review
    - backfill for existing documents
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

## Architecture

1. `paperless-ngx` imports a document.
2. OCR text and metadata become available through the Paperless API.
3. `PAPERLESS_POST_CONSUME_SCRIPT` starts `hooks/ai_enrich.py`.
4. The hook reads the document through the API.
5. `Ollama` generates a structured JSON response.
6. The hook writes title, correspondent, document type, and tags back to Paperless.

## Current Workflow

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
- fallback model support for `Ollama`
- protection against hallucinated person tags
- `Qwen 3.5` support with thinking disabled by default
- review workflow before writing metadata for single documents

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

## Notes

- This repository does not contain tokens or secret keys.
- Host-specific users, ports, and paths may need to be adapted.
- The prompt is intentionally stored as a text file so it can be adjusted without changing code.
