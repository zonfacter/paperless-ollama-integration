# AI Install Guide

This file is for AI agents, automation tools, and remote operators that need a deterministic installation path for this repository.

## Scope

There are two supported installation paths:

- `scripts/install-paperless-ai.sh`
  - use this for native `paperless-ngx` installs or simple Docker/Compose setups where you only need the Hook, Prompt, Backfill script, and basic Paperless integration
- `scripts/bootstrap-nas-stack.sh`
  - use this for the full repo-managed NAS/Compose stack

Do not mix both paths unless you explicitly know why.

## Default Recommendation

For a fresh NAS or Docker host, use:

```bash
./scripts/bootstrap-nas-stack.sh --dry-run
./scripts/bootstrap-nas-stack.sh
./scripts/bootstrap-nas-stack.sh --validate
```

This is the reference path for:

- `paperless-ngx`
- `ollama`
- `paperless-ai-web`
- optional `open-webui`
- optional `tika-ocr-proxy`
- optional OCR/image sidecars

## Required Behavior For AI Agents

When installing this repository, the agent should:

1. Prefer `bootstrap-nas-stack.sh` for the full stack.
2. Run `--dry-run` first and inspect the warnings.
3. Scaffold the stack.
4. Replace all placeholder values in `.env` before attempting to start services.
5. Run `--validate` after editing `.env`.
6. Only then start containers.

The agent must not assume that copied example files are production-ready.

## Stable Defaults

Unless the user explicitly requests otherwise, keep these defaults:

- image generation disabled or external OpenAI-compatible backend only
- no experimental local image backend as the default
- `docker compose` as the reference deployment path
- `Portainer` only as an optional secondary path

Do not silently enable:

- experimental AMD `ComfyUI` image generation
- experimental Intel `OpenVINO` image generation
- public LAN exposure for internal-only services unless the user asked for it

## Full Stack Procedure

Repository root is assumed.

1. Scaffold:

```bash
./scripts/bootstrap-nas-stack.sh --dry-run
./scripts/bootstrap-nas-stack.sh
```

2. Edit `.env`:

- replace all `CHANGE_ME_*` and `REPLACE_WITH_TOKEN`
- review host ports
- review bind hosts
- review GPU-related defaults
- review image backend settings
- if Open WebUI workspace visibility matters on NAS appliances, set a file-manager-visible host path
  - example for the tested UGREEN setup: `OPEN_WEBUI_WORKSPACE_HOST_PATH=/volume4/AI-TEST/workspace`

3. Validate:

```bash
./scripts/bootstrap-nas-stack.sh --validate
```

4. Start the base stack:

```bash
docker compose up -d broker db gotenberg tika webserver ollama
docker compose up -d consumer task-queue scheduler
```

5. Start optional services only if requested:

```bash
docker compose --profile ui up -d paperless-ai-web
docker compose --profile chat-ui up -d --build open-webui
docker compose --profile ocr-extra up -d paddleocr-api
docker compose --profile llama-cpp up -d llama-cpp
```

6. Only start experimental local image backends if the user explicitly asked:

```bash
docker compose --profile chat-ui --profile image-amd up -d --build comfyui-amd open-webui
docker compose --profile chat-ui --profile image-intel up -d open-webui openvino-image
```

## Hook-Only Procedure

If the task is only to add the Hook integration to an existing Paperless deployment:

```bash
sudo bash scripts/install-paperless-ai.sh --dry-run
sudo bash scripts/install-paperless-ai.sh
```

Use this path for:

- native `/opt/paperless/paperless.conf` installs
- simple Docker setups where a generated override file is sufficient

Do not use it as a substitute for full NAS stack scaffolding.

## Validation Expectations

`bootstrap-nas-stack.sh --validate` should fail if:

- `.env` is missing
- required config files are missing
- placeholders are still present in secrets/passwords
- `OPEN_WEBUI` image backend settings are incomplete
- `ComfyUI` is selected without the referenced checkpoint file

Warnings are acceptable for:

- missing `docker compose` support on the current host
- dry-run projections against files that have not been scaffolded yet

## Documentation References

- [README.md](README.md)
- [README.en.md](README.en.md)
- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/NAS_DEPLOYMENT.md](docs/NAS_DEPLOYMENT.md)
- [docs/OPEN_WEBUI.md](docs/OPEN_WEBUI.md)

## Non-Goals

This repository does not currently promise that:

- `Portainer` is the primary installation path
- local AMD image generation on `MI50/gfx906` is production-stable
- local Intel image generation is the default image path
- one installer covers every native, Docker, and NAS scenario equally
