# NAS Deployment

## Ziel

Diese Datei beschreibt den ersten sauberen NAS-Start fuer den Docker-MVP:

- `paperless-ngx`
- `ollama`
- `paperless-ai-web` als naechste Stufe ueber Compose-Profil `ui`
- optional spaeter `paddleocr-api`

## Empfohlener Host-Pfad

```text
/volume1/docker/paperless-ai/paperless-ollama-integration
```

## Vorbereitung

1. Projekt nach `/volume1/docker/paperless-ai/` kopieren oder dort klonen.
2. Beispielkonfigurationen kopieren:

```bash
cp .env.example .env
cp compose.override.example.yml compose.override.yml
cp config/paperless.conf.example config/paperless-ai.env
cp config/preview_config.example.json config/preview_config.json
cp config/tag_allowlists.example.json config/tag_allowlists.json
cp config/tag_rules.example.json config/tag_rules.json
cp config/providers.example.json config/providers.json
cp config/models.example.json config/models.json
cp config/version.example.json config/version.json
```

3. Verzeichnisse anlegen:

```bash
mkdir -p \
  data/paperless/consume \
  data/paperless/media \
  data/paperless/export \
  data/paperless/data \
  data/redis \
  data/db \
  data/ollama \
  data/paperless-ai-web \
  data/paddleocr-cache \
  config/tessdata-best
```

4. `.env` anpassen:
   - Passwoerter
   - Secret Key
   - Zeitzone
   - Paperless-URL
   - Host-Ports
   - API-Token spaeter nach erstem Admin-Login

Empfohlener Start auf diesem NAS:

- `PAPERLESS_PUBLIC_PORT=18000`
- `PAPERLESS_AI_WEB_PUBLIC_PORT=3000`
- `OLLAMA_BIND_HOST=127.0.0.1`
- `PADDLEOCR_BIND_HOST=127.0.0.1`

Grund:

- `8000` ist auf diesem NAS bereits durch `portainer` belegt
- `ollama` und `paddleocr-api` sollen nicht unnoetig direkt ins LAN exponiert werden

## Erster Start

Zunaechst nur Paperless-Core und Ollama:

```bash
sudo docker compose up -d broker db gotenberg tika webserver consumer task-queue scheduler ollama
```

Danach pruefen:

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 webserver
sudo docker compose logs --tail=100 consumer
sudo docker compose logs --tail=100 ollama
```

## Zweiter Schritt

Wenn Paperless stabil laeuft, kann die Webkonsole als naechster Schritt zugeschaltet werden:

```bash
sudo docker compose --profile ui up -d paperless-ai-web
```

Dann pruefen:

```bash
curl -sS http://127.0.0.1:3000/ | head
```

## Optionaler OCR-Zusatz

```bash
sudo docker compose --profile ocr-extra up -d paddleocr-api
```

## Wichtige Hinweise

- `consume`, `media`, `export`, `config` und `data` muessen auf Host-Volumes bleiben.
- Keine produktive Einstellung darf nur im Container-Filesystem liegen.
- `paperless-ai-web` ist in diesem ersten NAS-Stand bewusst getrennt ueber ein Profil aktiviert, damit Phase 1 und 2 nicht von spaeteren UI-Helfern abhaengen.
- Vor spaeteren Updates:
  - DB sichern
  - Media sichern
  - Config sichern
- `ollama` sollte auf diesem NAS zuerst CPU-only und mit klaren Thread-Limits gedacht werden.
