# ROCm Profile Switch (MI50)

## Ziel

Schnell zwischen einem konservativen MI50-Setup und einem experimentellen neueren Ollama-Setup umschalten, ohne manuell mehrere `.env`-Werte zu editieren.

## Profile

1. `rocm-stable`
- `OLLAMA_IMAGE_TAG=0.12.3-rocm`
- `OLLAMA_VULKAN=0`
- `OLLAMA_KEEP_ALIVE=2m`
- `OLLAMA_MAX_LOADED_MODELS=1`
- `OLLAMA_NUM_PARALLEL=1`

2. `rocm-next`
- `OLLAMA_IMAGE_TAG=0.20.2`
- `OLLAMA_VULKAN=0`
- `OLLAMA_KEEP_ALIVE=10m`
- `OLLAMA_MAX_LOADED_MODELS=2`
- `OLLAMA_NUM_PARALLEL=2`

## Umschalten

Im Repo-Root:

```bash
./scripts/set-ollama-rocm-profile.sh rocm-stable .env
```

oder

```bash
./scripts/set-ollama-rocm-profile.sh rocm-next .env
```

Danach Ollama neu erstellen:

```bash
docker compose up -d --force-recreate ollama
```

Optional abhängige Dienste neu starten:

```bash
docker compose --profile ui up -d paperless-ai-web webserver
docker compose --profile chat-ui up -d open-webui
```

## Verifikation

```bash
docker exec paperless-ollama ollama --version
docker inspect paperless-ollama --format '{{json .Config.Env}}' | tr ',' '\n' | grep -E 'OLLAMA_VULKAN|OLLAMA_NUM_PARALLEL|OLLAMA_KEEP_ALIVE'
```

