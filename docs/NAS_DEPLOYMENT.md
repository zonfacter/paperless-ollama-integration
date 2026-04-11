# NAS Deployment

## Ziel

Diese Datei beschreibt den ersten sauberen NAS-Start fuer den Docker-MVP:

- `paperless-ngx`
- `ollama`
- `paperless-ai-web` als naechste Stufe ueber Compose-Profil `ui`
- optional `open-webui` als Chat-/Vergleichsdienst ueber Compose-Profil `chat-ui`
- optional spaeter `paddleocr-api`

Ergaenzende reale Laufzeitbefunde fuer dieses NAS stehen in:

- [NAS_RUNTIME_FINDINGS.md](NAS_RUNTIME_FINDINGS.md)

Wichtig:

- diese Datei beschreibt den Betriebs- und Startpfad
- `NAS_RUNTIME_FINDINGS.md` beschreibt die bereits verifizierten Modell- und Runtime-Grenzen auf Intel Iris Xe

## Portainer-Hinweis

Die `compose.yml` ist grundsaetzlich Docker-/Compose-kompatibel und kann auch in `Portainer` als Stack importiert werden.

Wichtige Einschraenkungen:

- `profiles` sind in `Portainer` meist unkomfortabler als im normalen `docker compose`-CLI-Betrieb
- `build:`-basierte Dienste wie das repo-gepflegte `open-webui`-Wrapper-Image oder `comfyui-amd` sind in `Portainer` fehleranfaelliger als vorgebaute Images
- Host-Binds wie `/dev/kfd`, `/dev/dri`, `/sys` oder `/var/run/docker.sock` bleiben hostabhaengig und brauchen in `Portainer` dieselbe Sorgfalt wie auf der CLI
- fuer den stabilen Standardpfad ist die Compose-Datei geeignet, die experimentellen lokalen Bild-Backends sollten in `Portainer` aber nicht als erste Erwartung fuer einen problemlosen One-Click-Stack betrachtet werden

Kurz gesagt:

- ja, die Datei ist weitgehend `Portainer`-kompatibel
- fuer reproduzierbare Erstinstallationen ist der normale `docker compose`-Pfad dennoch die Referenz

## Empfohlener Host-Pfad

```text
/volume1/docker/paperless-ai/paperless-ollama-integration
```

## Vorbereitung

1. Projekt nach `/volume1/docker/paperless-ai/` kopieren oder dort klonen.
2. Zuerst den Bootstrap im Dry-Run laufen lassen:

```bash
./scripts/bootstrap-nas-stack.sh --dry-run
```

3. Dann den Scaffold wirklich ausfuehren:

```bash
./scripts/bootstrap-nas-stack.sh
```

Der Bootstrap:

- legt alle aktuellen Daten- und Konfigurationspfade des Repos an
- kopiert nur fehlende Standarddateien
- validiert den Compose-Stand und die aktivierte Open-WebUI-/Image-Konfiguration
- ersetzt nicht das Bearbeiten von `.env`, nimmt dir aber die fehleranfaellige Grundverdrahtung ab

4. Alternativ kannst du den Vorgang weiter manuell nachvollziehen. Der Bootstrap macht dabei im Wesentlichen genau diese Schritte:

5. Beispielkonfigurationen kopieren:

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

6. Verzeichnisse anlegen:

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
  data/open-webui \
  data/comfyui/models/checkpoints \
  data/comfyui/input \
  data/comfyui/output \
  data/comfyui/custom_nodes \
  data/paddleocr-cache \
  config/tessdata-best
```

7. `.env` anpassen:
   - Passwoerter
   - Secret Key
   - Zeitzone
   - Paperless-URL
   - Host-Ports
   - CPU-/RAM-Limits pro Container
   - API-Token spaeter nach erstem Admin-Login
  - GPU-/iGPU-Defaults pruefen
  - falls Bildgenerierung ueber AMD gewuenscht ist: Checkpoint-Datei nach `data/comfyui/models/checkpoints/` legen

Empfohlener Start auf diesem NAS:

- `PAPERLESS_PUBLIC_PORT=18000`
- `PAPERLESS_AI_WEB_PUBLIC_PORT=3000`
- `OLLAMA_BIND_HOST=127.0.0.1`
- `PADDLEOCR_BIND_HOST=127.0.0.1`

Grund:

- `8000` ist auf diesem NAS bereits durch `portainer` belegt
- `ollama` und `paddleocr-api` sollen nicht unnoetig direkt ins LAN exponiert werden

## Ressourcen-Limits

Dieser Stack setzt bewusst harte Container-Limits. Der Default darf nicht sein,
dass jeder Dienst das gesamte NAS fuer sich beanspruchen kann.

Empfohlene Startwerte aus `.env`:

```dotenv
BROKER_CPUS=0.50
BROKER_MEM_LIMIT=256m
DB_CPUS=1.50
DB_MEM_LIMIT=2g
GOTENBERG_CPUS=2.00
GOTENBERG_MEM_LIMIT=2g
GOTENBERG_SHM_SIZE=1g
TIKA_CPUS=1.00
TIKA_MEM_LIMIT=1g
PAPERLESS_WEBSERVER_CPUS=2.00
PAPERLESS_WEBSERVER_MEM_LIMIT=2g
PAPERLESS_CONSUMER_CPUS=1.50
PAPERLESS_CONSUMER_MEM_LIMIT=1536m
PAPERLESS_TASK_QUEUE_CPUS=2.00
PAPERLESS_TASK_QUEUE_MEM_LIMIT=2g
PAPERLESS_SCHEDULER_CPUS=0.50
PAPERLESS_SCHEDULER_MEM_LIMIT=512m
OLLAMA_CPUS=6.00
OLLAMA_MEM_LIMIT=12g
PAPERLESS_AI_WEB_CPUS=1.00
PAPERLESS_AI_WEB_MEM_LIMIT=1g
OPEN_WEBUI_CPUS=2.00
OPEN_WEBUI_MEM_LIMIT=2g
PADDLEOCR_CPUS=2.00
PADDLEOCR_MEM_LIMIT=2g
```

Einordnung:

- `ollama` bekommt den groessten RAM-/CPU-Anteil.
- `broker`, `scheduler` und `tika` bleiben bewusst klein.
- `gotenberg` bekommt eigenes `shm_size`, weil Chromium/Rendering sonst frueh
  an Speichergrenzen scheitern kann.
- Diese Werte sind Startwerte, keine Dogmen. Auf kleineren NAS-Systemen muessen
  sie reduziert werden, auf groesseren koennen sie gezielt erhoeht werden.
- Fuer die spaetere Web-UI sollte diese Limit-Konfiguration sichtbar und
  aenderbar gemacht werden.

GPU-/iGPU-Hinweis fuer dieses NAS:

- Auf dem UGREEN-Host ist eine Intel-iGPU vorhanden.
- Vor produktiver GPU-Nutzung immer pruefen:

```bash
ls -l /dev/dri
lspci | grep -i -E 'vga|3d|display'
```

- Nur wenn `renderD*` sichtbar ist, gilt die iGPU als wirklich nutzbar.
- Dieser Compose-Stack mappt `/dev/dri` in `ollama` und optional `paddleocr-api`.
- Fuer `ollama` ist das die richtige Voraussetzung fuer Intel-iGPU-/Vulkan-Tests.
- `paddleocr-api` bekommt das Device ebenfalls, bleibt aber standardmaessig auf `cpu`, weil PaddleOCR in diesem Stack auf Intel-iGPU nicht als robuster Default betrachtet werden sollte.

Empfohlene `.env`-Werte:

```dotenv
OLLAMA_INTEL_GPU=1
PADDLEOCR_DEVICE=cpu
```

Wichtige Einordnung:

- die iGPU ist fuer kleine Modelle ueber `ollama` brauchbar
- fuer groessere Modelle war `ollama` auf Intel Vulkan in den Tests oft instabil oder qualitativ kaputt
- fuer stabile Qualitaet bleibt auf diesem NAS CPU-only der Referenzpfad
- wenn spaeter groessere GPU-Modelle lokal genutzt werden sollen, sollte ein optionaler zweiter Runtime-Pfad mit `llama.cpp` vorgesehen werden

## Erster Start

Zunaechst nur Basisdienste plus `webserver`, damit die ersten Migrationen ohne Lock-Konflikte sauber durchlaufen:

```bash
sudo docker compose up -d broker db gotenberg tika webserver ollama
```

Danach pruefen:

```bash
sudo docker compose ps
sudo docker compose logs --tail=100 webserver
sudo docker compose logs --tail=100 ollama
sudo docker exec paperless-ollama ls -l /dev/dri
```

Wenn `webserver` gesund ist, erst die restlichen Paperless-Dienste starten:

```bash
sudo docker compose up -d consumer task-queue scheduler
```

Hinweise:
- `consumer`, `task-queue` und `scheduler` haben in diesem Stack bewusst keine HTTP-Healthchecks.
- Der `paperless-ngx`-Container bringt standardmaessig einen Port-`8000`-Probeweg mit, der fuer diese drei Nicht-Webdienste nur Fehlalarme erzeugen wuerde.
- Der korrekte Laufzustand ist stattdessen:
  - `consumer`: pollt `/usr/src/paperless/consume`
  - `task-queue`: Celery-Worker ist mit Redis verbunden
  - `scheduler`: Celery Beat laeuft
- Der Scheduler nutzt bewusst `--schedule=/tmp/celerybeat-schedule`, um einen bekannten Celery-Beat-Pfadfehler mit persistenten Schedule-Dateien auf diesem Stack zu umgehen.

## Zweiter Schritt

Wenn Paperless stabil laeuft, kann die Webkonsole als naechster Schritt zugeschaltet werden:

```bash
sudo docker compose --profile ui up -d paperless-ai-web
```

Dann pruefen:

```bash
curl -sS http://127.0.0.1:3000/ | head
```

## Optional: Open WebUI

Wenn zusaetzlich ein separater Chat-/Vergleichsdienst fuer lokale Modelle gewuenscht ist:

```bash
sudo docker compose --profile chat-ui up -d --build open-webui
```

Dann pruefen:

```bash
curl -sS http://127.0.0.1:8081/ | head
```

Wichtige Einordnung:

- `Open WebUI` ersetzt nicht `paperless-ai-web`
- `paperless-ai-web` bleibt fuer Review, Task Manager und Backfill zustaendig
- `Open WebUI` ist fuer Chat, Modellvergleich und spaetere optionale zweite Runtime-Anbindung gedacht
- wenn der Agent-Workspace im NAS-Dateimanager sichtbar sein soll, nutze fuer `OPEN_WEBUI_WORKSPACE_HOST_PATH` einen sichtbaren Share
- fuer das hier getestete UGREEN-Setup ist `/volume4/AI-TEST/workspace` der empfohlene sichtbare Arbeitsbereich

Siehe auch:

- [OPEN_WEBUI.md](OPEN_WEBUI.md)

## Optional: AMD-Bildgenerierung fuer Open WebUI

Der lokale AMD-Pfad bleibt im Repo vorhanden, ist aktuell aber experimentell und nicht der empfohlene Standard fuer Neuinstallationen.

Start:

```bash
sudo docker compose --profile chat-ui --profile image-amd up -d --build comfyui-amd open-webui
```

Wichtig:

- ein Bild-Checkpoint muss vorher auf dem Host liegen, z.B. unter:

```text
data/comfyui/models/checkpoints/Deliberate_v2.safetensors
```

- `OPEN_WEBUI_IMAGE_GENERATION_MODEL` muss zum Dateinamen dieses Checkpoints passen
- auf dem hier getesteten `MI50/gfx906`-Host war auch ein `SD 1.5`-Checkpoint noch nicht stabil genug fuer den produktiven Standardpfad
- die Open-WebUI-Workflow-Definition liegt repo-seitig im Wrapper-Image und bleibt dadurch auch nach `recreate` reproduzierbar
- sowohl der AMD- als auch der fruehere Intel-iGPU-Pfad sind damit nur noch experimentell und nicht der empfohlene Hauptpfad dieses Repos

## Empfohlener Bild-Standardpfad

Fuer ein stabiles Setup sollte Open WebUI Bilder standardmaessig ueber einen externen OpenAI-kompatiblen Bilddienst erzeugen.

Minimal:

```dotenv
OPEN_WEBUI_ENABLE_IMAGE_GENERATION=true
OPEN_WEBUI_IMAGE_GENERATION_ENGINE=openai
OPEN_WEBUI_IMAGE_GENERATION_MODEL=gpt-image-1
OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL=<dein-openai-kompatibler-bild-endpunkt>
OPEN_WEBUI_IMAGES_OPENAI_API_KEY=<dein-api-key>
```

## Optionaler OCR-Zusatz

```bash
sudo docker compose --profile ocr-extra up -d paddleocr-api
sudo docker exec paperless-paddleocr-api ls -l /dev/dri
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
- GPU-/iGPU-Mapping ist vorbereitet, aber echte Beschleunigung gilt erst als bestaetigt, wenn die Render-Devices auch im Container sichtbar sind und der Zielruntime-Pfad sie wirklich nutzt.
- fuer den realen Modellbetrieb auf diesem NAS gilt aktuell:
  - `qwen3.5:2b` ist ein brauchbarer lokaler GPU-Kandidat
  - `qwen3.5:4b` ist der praktikable CPU-Qualitaetskandidat
  - `llama.cpp` sollte als optionaler spaeterer GPU-Pfad mit kompatiblen externen GGUFs mitgedacht werden
