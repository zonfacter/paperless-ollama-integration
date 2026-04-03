# Open WebUI

## Ziel

`Open WebUI` ist in diesem Projekt ein optionaler Chat- und Modellzugriff fuer das NAS.

Es ersetzt nicht:

- `paperless-ai-web`
- Review
- Task Manager
- Backfill-Steuerung

Sondern ergaenzt den Stack um:

- direkten Chat mit lokalen Modellen
- manuelle Modellvergleiche
- spaeter optional den Zugriff auf eine zweite Runtime wie `llama.cpp`

## Compose-Profil

Der Dienst ist absichtlich optional und wird ueber ein eigenes Profil gestartet:

```bash
sudo docker compose --profile chat-ui up -d --build open-webui
```

Die Basisversion wird bewusst nicht ueber `latest`, sondern ueber eine feste Variable gesteuert:

```dotenv
OPEN_WEBUI_IMAGE_TAG=v0.8.12
```

Das macht Updates reproduzierbar und Rollbacks einfacher.

Zusatz fuer dieses Repo:

- `open-webui` wird bewusst als kleines Wrapper-Image gebaut
- dieses Wrapper-Image patched beim Start die benoetigte Open-WebUI-Feature-Logik
- repo-gepflegte Profile und Tools werden beim Start automatisch wieder installiert
- dadurch bleibt auch ein `recreate` reproduzierbar und verliert keine projektkritischen Anpassungen

Default-Port:

- `http://HOST:8081`

## Persistenz

Die Daten liegen bewusst auf dem Host:

```text
./data/open-webui:/app/backend/data
```

Damit bleiben erhalten:

- lokale Einstellungen
- Benutzer
- Verbindungsdaten
- Chat-Historie

Wichtig fuer Updates:

- `./data/open-webui` darf nicht geloescht werden
- `OPEN_WEBUI_SECRET_KEY` muss stabil bleiben

Dann bleiben Chats und Einstellungen auch nach einem Container-Update erhalten.

## Repo-gepflegte Profile

Custom-Model-Profile sollten nicht nur manuell in `webui.db` gepflegt werden.

Dafuer liegt jetzt ein kleines Repo-Skript bereit:

```text
scripts/openwebui/install_model_profiles.py
```

Aktuell verwaltet es mindestens:

- `LOCAL Image Assistant`
- `LOCAL Photo Assistant`
- `LOCAL Illustration Assistant`

Ziel:

- Bildanfragen nicht als nacktes Ollama-Basismodell laufen lassen
- stattdessen ein dediziertes Open-WebUI-Profil mit aktivierter Bildfunktion nutzen
- den funktionierenden NAS-Stand reproduzierbar halten
- fuer das Bildprofil ein leichtes Nicht-Thinking-Modell wie `qwen2.5:3b` nutzen, damit nach dem Tool-Call keine internen Reasoning-Texte im Chat landen

Die Profile werden beim Start des `open-webui`-Containers automatisch aus dem Repo in `webui.db` geschrieben.

Dasselbe gilt fuer das Tool-Installationsskript:

```text
scripts/openwebui/install_workspace_agent_tools.py
```

Damit ist das Repo die Quelle der Wahrheit und nicht irgendein manueller Zustand im laufenden Container.

## Standardpfad: `ollama`

Im Compose-Default spricht `Open WebUI` gegen den lokalen `ollama`-Dienst:

- `OPEN_WEBUI_ENABLE_OLLAMA_API=true`
- `OPEN_WEBUI_OLLAMA_BASE_URL=http://ollama:11434`

Das ist der erste empfohlene Betriebsmodus.

## Bildgenerierung

`Open WebUI` unterstuetzt Bildgenerierung getrennt vom normalen Chat-Backend.

Im Repo sind dafuer diese Schalter vorbereitet:

- `OPEN_WEBUI_ENABLE_IMAGE_GENERATION`
- `OPEN_WEBUI_ENABLE_IMAGE_PROMPT_GENERATION`
- `OPEN_WEBUI_IMAGE_GENERATION_ENGINE`
- `OPEN_WEBUI_IMAGE_GENERATION_MODEL`
- `OPEN_WEBUI_IMAGE_SIZE`
- `OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL`
- `OPEN_WEBUI_IMAGES_OPENAI_API_KEY`
- `OPEN_WEBUI_AUTOMATIC1111_BASE_URL`
- `OPEN_WEBUI_AUTOMATIC1111_API_AUTH`
- `OPEN_WEBUI_COMFYUI_BASE_URL`
- `OPEN_WEBUI_COMFYUI_API_KEY`
- `OPEN_WEBUI_COMFYUI_WORKFLOW`
- `OPEN_WEBUI_COMFYUI_WORKFLOW_FILE`
- `OPEN_WEBUI_COMFYUI_WORKFLOW_NODES_FILE`

Empfohlener Standard fuer dieses Repo ist jetzt:

- ein externer OpenAI-kompatibler Bilddienst
- `Open WebUI` spricht diesen Dienst ueber `OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL` an
- der lokale AMD-Pfad bleibt optional und experimentell

Grund:

- der externe Bildpfad ist fuer Neuinstallationen reproduzierbarer
- lokale Bildpfade auf `gfx906/MI50` waren in diesem Projektstand mit `ROCm/ComfyUI` nicht stabil genug
- so bleibt die Standardanleitung einfach und wartbar

Minimalbeispiel fuer den Standardpfad:

- `OPEN_WEBUI_ENABLE_IMAGE_GENERATION=true`
- `OPEN_WEBUI_IMAGE_GENERATION_ENGINE=openai`
- `OPEN_WEBUI_IMAGE_GENERATION_MODEL=gpt-image-1`
- `OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL=<dein-openai-kompatibler-bild-endpunkt>`
- `OPEN_WEBUI_IMAGES_OPENAI_API_KEY=<dein-api-key>`

## AMD-Pfad mit ComfyUI

Im Repo ist jetzt ein optionales Compose-Profil `image-amd` vorbereitet.

Zielbild:

- `MI50` uebernimmt Bildgenerierung
- `Open WebUI` nutzt den Engine-Typ `comfyui`
- Workflow und Node-Mapping kommen aus versionierten JSON-Dateien im Wrapper-Image

Relevante Variablen:

- `OPEN_WEBUI_ENABLE_IMAGE_GENERATION=true`
- `OPEN_WEBUI_ENABLE_IMAGE_PROMPT_GENERATION=false`
- `OPEN_WEBUI_IMAGE_GENERATION_ENGINE=comfyui`
- `OPEN_WEBUI_IMAGE_GENERATION_MODEL=<checkpoint-datei>`
- `OPEN_WEBUI_COMFYUI_BASE_URL=http://comfyui-amd:8188`
- `OPEN_WEBUI_COMFYUI_WORKFLOW_FILE=/opt/paperless-open-webui/workflows/comfyui_txt2img_api.json`
- `OPEN_WEBUI_COMFYUI_WORKFLOW_NODES_FILE=/opt/paperless-open-webui/workflows/comfyui_txt2img_nodes.json`
- `COMFYUI_AMD_HSA_OVERRIDE_GFX_VERSION`
- `COMFYUI_AMD_HIP_VISIBLE_DEVICES`
- `COMFYUI_AMD_ROCR_VISIBLE_DEVICES`

Startbeispiel:

```bash
sudo docker compose --profile chat-ui --profile image-amd up -d --build comfyui-amd open-webui
```

Wichtig:

- dieser Pfad ist aktuell experimentell
- auf dem hier getesteten `MI50/gfx906`-Host kam es sowohl mit `SDXL` als auch mit `SD 1.5`-Checkpoints zu reproduzierbaren Abstuerzen im `CLIP/text encoder`
- `OPEN_WEBUI_IMAGE_GENERATION_MODEL` muss auf eine echte Checkpoint-Datei in `data/comfyui/models/checkpoints/` zeigen
- das Repo liefert absichtlich keinen proprietaeren oder lizenzkritischen Bild-Checkpoint mit
- die Default-Workflow-Datei ist ein einfacher `txt2img`-Pfad mit `CheckpointLoaderSimple`, `KSampler` und `SaveImage`
- `Open WebUI` laedt Workflow und Node-Mapping beim Start aus den Repo-Dateien, auch nach `recreate`
- wenn du diesen Pfad in einem Fork weiterverfolgst, starte am besten mit kleinen Testmodellen und betrachte den MI50-Pfad als Debug-/Tuning-Thema, nicht als garantierte Standardfunktion

## Intel-iGPU Pfad mit OpenVINO

Der bisherige Pfad `image-intel` bleibt im Repo nur noch als experimenteller Fork-Punkt erhalten.

Einordnung:

- auf diesem Host exportiert `i915` keine brauchbaren Last-, VRAM- oder Power-Werte fuer die Webdiagnose
- groessere Aufloesungen wie `768x768` oder `1024x1024` haengen im aktuellen OpenVINO-iGPU-Pfad
- deshalb ist dieser Weg fuer das Haupt-Repo nicht mehr der empfohlene Standard

Wer den Intel-Pfad weiterverfolgen moechte, kann das in einem Fork ueber das vorhandene Profil `image-intel` tun.

## Optionaler zweiter Pfad: `llama.cpp`

Falls spaeter ein lokaler `llama.cpp`-Server als OpenAI-kompatibler Dienst laeuft,
kann `Open WebUI` auch dagegen konfiguriert werden.

Vorbereitete Variablen:

- `OPEN_WEBUI_ENABLE_OPENAI_API`
- `OPEN_WEBUI_OPENAI_API_BASE_URL`
- `OPEN_WEBUI_OPENAI_API_KEY`

Beispiel:

```dotenv
OPEN_WEBUI_ENABLE_OPENAI_API=true
OPEN_WEBUI_OPENAI_API_BASE_URL=http://llama-cpp:8080/v1
OPEN_WEBUI_OPENAI_API_KEY=dummy
```

Wichtig:

- das setzt einen separaten `llama.cpp`-Dienst im gleichen Docker-Netz voraus
- dieser Pfad ist in diesem Projekt derzeit vorbereitet, aber noch nicht als Standarddienst verdrahtet

## Architekturhinweis

`Open WebUI` ist ein Bedien- und Vergleichswerkzeug.

Die produktive Paperless-Pipeline bleibt davon getrennt:

- `paperless-ai-web` bleibt die Admin-/Review-Oberflaeche
- Hintergrundjobs und Hook-Pfade sollen nicht an `Open WebUI` haengen
- `Open WebUI` ist fuer Chat, Modellzugriff und manuelle Verifikation gedacht

## Empfehlung fuer das NAS

Aktuell sinnvoll:

- `Open WebUI` an `ollama` anbinden
- Bildgenerierung standardmaessig ueber einen externen OpenAI-kompatiblen Dienst anbinden
- lokale AMD- oder Intel-Bildpfade nur bewusst optional aktivieren
- spaeter optional einen zweiten Runtime-Eintrag fuer `llama.cpp` aktivieren
- keine automatische Koppelung von `Open WebUI` an Import- oder Backfill-Jobs
