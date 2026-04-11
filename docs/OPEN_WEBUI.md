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

Portainer-Hinweis:

- `open-webui` laeuft auch in `Portainer` grundsaetzlich als Stack-Dienst
- wegen `build:`-Nutzung, Wrapper-Image und optionalen Host-Mounts ist der Dienst im normalen `docker compose`-Betrieb aber die verlässlichere Referenz
- fuer `Portainer` gilt daher: moeglich, aber nicht der bevorzugte Test- und Releasepfad dieses Repos

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
- `LOCAL Task Router`
- `LOCAL Code Fast`
- `LOCAL Code Deep`
- `LOCAL Legal Research`
- `LOCAL Paperless Tagger`
- `LOCAL OCR Vision`

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

Und fuer die globalen Action-Buttons:

```text
scripts/openwebui/install_image_actions.py
scripts/openwebui/install_project_path_actions.py
```

Damit ist das Repo die Quelle der Wahrheit und nicht irgendein manueller Zustand im laufenden Container.

Wichtig fuer Coding-Profile:

- die lokalen Code-Profile sind auf `function_calling=native` gesetzt
- zusaetzlich gibt es den kombinierten Tool-Call `init_project_context(project_path)`, damit ein Projektpfad in einem Schritt gesetzt und direkt gelistet wird
- das reduziert Antworten, die Tool-Calls nur als Text ausgeben
- fuer Upload-Dateien (`txt`, `md`, `pdf`, `doc`, `docx`, `ppt`, `pptx` ...) gibt es dokumentorientierte Extraktions-Tools:
  - `extract_project_document`
  - `extract_workspace_document`

## Routing-Plan (Vulkan)

Empfohlene Profile je Aufgabe:

- Coding schnell: `LOCAL Code Fast` (`qwen2.5-coder:7b`)
- Coding tief: `LOCAL Code Deep` (`qwen2.5:14b-instruct`)
- Komplexe Recht-/Rechercheaufgaben: `LOCAL Legal Research` (`qwen2.5:14b`)
- OCR-Tagging/Korrespondenz: `LOCAL Paperless Tagger` (`qwen2.5:3b`)
- Vision/OCR aus Scan/Bild: `LOCAL OCR Vision` (`deepseek-ocr:3b`)
- Einstieg/Verteilung: `LOCAL Task Router`

Pragmatischer Start:

1. Chat mit `LOCAL Task Router` starten.
2. Bei Coding-Projekten direkt im ersten Satz den Pfad nennen, z. B. `Projektpfad: project/ebay`.
3. Bei Datei-Analyse Datei hochladen und klar sagen: `Bitte Datei analysieren und Kernpunkte extrahieren.`

## Datei-Upload und Verarbeitung

Der Compose-Stack setzt Upload/RAG-Defaults fuer produktiven Betrieb:

- `USER_PERMISSIONS_CHAT_FILE_UPLOAD=true`
- `USER_PERMISSIONS_CHAT_WEB_UPLOAD=true`
- `RAG_FILE_MAX_SIZE=209715200` (200 MB)
- `RAG_FILE_MAX_COUNT=40`
- `RAG_ALLOWED_FILE_EXTENSIONS=txt,md,pdf,doc,docx,rtf,csv,xls,xlsx,ppt,pptx,json,xml,html`

Dadurch koennen typische Dokumentformate direkt in Open WebUI hochgeladen und verarbeitet werden.

## Sichtbarer Workspace fuer UGREEN

Wenn du willst, dass `Open WebUI`, der Agent und dein UGREEN-Dateimanager dieselben Dateien sehen,
nutze einen sichtbaren Share als Workspace-Hostpfad statt eines internen Docker-/Repo-Pfads.

Empfehlung fuer dieses Setup:

- `OPEN_WEBUI_WORKSPACE_HOST_PATH=/volume4/AI-TEST/workspace`
- `OPEN_WEBUI_WORKSPACE_ROOT=/workspace/project`

Dann gilt:

- der Agent arbeitet innerhalb von `/workspace/project`
- dieser Pfad zeigt im Container auf `/volume4/AI-TEST/workspace`
- du kannst denselben Inhalt direkt im UGREEN-Dateimanager ansehen

Neuer Projektpfad-Workflow (pro Nutzer):

1. Im Chat den Zielpfad schreiben, z.B. `project/ebay`
2. Action `Workspace Project Actions` -> `Set Path From Message` ausfuehren
3. Der Agent kann dann die neuen Tool-Funktionen nutzen:
   - `init_project_context`
   - `get_project_path`
   - `list_project_files`
   - `read_project_file`
   - `write_project_file`
   - `replace_project_text`
   - `search_project_text`

## Community-Integrationen (empfohlen, optional)

Open WebUI bietet bereits offizielle OpenAPI/MCP-Integrationspfade. Fuer dieses Repo sind besonders sinnvoll:

1. OpenAPI `filesystem` Server (open-webui/openapi-servers)
   - sinnvoll fuer standardisierte Dateizugriffe, falls du spaeter von den repo-eigenen Workspace-Tools weg willst
2. OpenAPI `memory` Server (open-webui/openapi-servers)
   - sinnvoll fuer langfristige Agent-Erinnerungen ueber Chats hinweg
3. OpenAPI `git`/repo-nahe Server aus derselben Referenzsammlung
   - sinnvoll fuer Read-only-Repo-Inspektion als Zusatz zu den lokalen Git-Tools

Hinweis:

- weil dieses Repo bereits `workspace_agent_tools` hat, sind viele Community-Tools funktional ueberlappend
- deshalb als optional behandeln, um Installation/Wartung schlank zu halten

Wichtig:

- das ist am besten als sichtbare Arbeitskopie gedacht
- wenn du dort ein Repo hineinlegst oder hineinkopierst, arbeitet der Agent genau auf dieser Kopie
- fuer UGREEN ist dieser Pfad deutlich praktischer als interne Docker-Verzeichnisse unter `/volume1/docker/...`

## Standardpfad: `ollama`

Im Compose-Default spricht `Open WebUI` gegen den lokalen `ollama`-Dienst:

- `OPEN_WEBUI_ENABLE_OLLAMA_API=true`
- `OPEN_WEBUI_OLLAMA_BASE_URL=http://ollama:11434`

Das ist der erste empfohlene Betriebsmodus.

Wenn mehrere Nutzer unterschiedliche lokale Modelle parallel nutzen sollen, sind diese Ollama-Parameter relevant:

- `OLLAMA_KEEP_ALIVE` (z.B. `15m`): wie lange ein Modell im VRAM geladen bleibt
- `OLLAMA_MAX_LOADED_MODELS` (z.B. `2`): wie viele Modelle pro GPU parallel geladen bleiben duerfen
- `OLLAMA_NUM_PARALLEL` (z.B. `2`): gleichzeitige Requests

Hinweis:

- mehr parallele Modelle/Requests erhoehen VRAM-Druck und koennen bei 16 GB schneller zu Verlangsamung oder Auslagerung fuehren

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
- fuer den ersten Stabilitaetstest sollten konservative Defaults verwendet werden:
  - `OPEN_WEBUI_IMAGE_SIZE=512x512`
  - `COMFYUI_AMD_EXTRA_ARGS=--disable-auto-launch --preview-method none --disable-smart-memory --use-split-cross-attention --fp16-vae`
- `OPEN_WEBUI_IMAGE_GENERATION_MODEL` muss auf eine echte Checkpoint-Datei in `data/comfyui/models/checkpoints/` zeigen
- das Repo liefert absichtlich keinen proprietaeren oder lizenzkritischen Bild-Checkpoint mit
- die Default-Workflow-Datei ist ein einfacher `txt2img`-Pfad mit `CheckpointLoaderSimple`, `KSampler` und `SaveImage`
- `Open WebUI` laedt Workflow und Node-Mapping beim Start aus den Repo-Dateien, auch nach `recreate`
- wenn du diesen Pfad in einem Fork weiterverfolgst, starte am besten mit kleinen Testmodellen und betrachte den MI50-Pfad als Debug-/Tuning-Thema, nicht als garantierte Standardfunktion

## AMD-Pfad mit AUTOMATIC1111

Zusaetzlich gibt es jetzt einen alternativen AMD-Testpfad ueber `AUTOMATIC1111`.

Ziel:

- ein zweiter lokaler AMD-Bildpfad fuer `MI50/gfx906`
- konservative Vega20-/ROCm-Startargs statt des `ComfyUI`-Pfads

Startbeispiel:

```bash
sudo docker compose --profile image-amd-a1111 up -d --build automatic1111-amd
```

Einordnung:

- dieser Pfad ist ebenfalls nicht der repo-weite Standard
- er ist als pragmatischer Alternativtest gedacht, wenn `ComfyUI` auf `gfx906` im `CLIP/text encoder` abstuerzt
- die Default-Args in `.env.example` orientieren sich an bekannten Vega20-/ROCm-Hinweisen wie `--precision full`, `--no-half`, `--no-half-vae` und `HSA_OVERRIDE_GFX_VERSION=9.0.6`

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
