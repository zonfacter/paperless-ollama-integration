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
sudo docker compose --profile chat-ui up -d open-webui
```

Die Image-Version wird bewusst nicht ueber `latest`, sondern ueber eine feste Variable gesteuert:

```dotenv
OPEN_WEBUI_IMAGE_TAG=v0.8.12
```

Das macht Updates reproduzierbar und Rollbacks einfacher.

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

## Standardpfad: `ollama`

Im Compose-Default spricht `Open WebUI` gegen den lokalen `ollama`-Dienst:

- `OPEN_WEBUI_ENABLE_OLLAMA_API=true`
- `OPEN_WEBUI_OLLAMA_BASE_URL=http://ollama:11434`

Das ist der erste empfohlene Betriebsmodus.

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
- spaeter optional einen zweiten Runtime-Eintrag fuer `llama.cpp` aktivieren
- keine automatische Koppelung von `Open WebUI` an Import- oder Backfill-Jobs
