# Troubleshooting

## `Qwen 3.5` laeuft in Timeouts

Typische Ursache:

- Thinking ist aktiv

Loesung:

- sicherstellen, dass `PAPERLESS_AI_QWEN35_THINK=false` gesetzt ist
- der Hook schaltet `think=false` fuer `qwen3.5:*` standardmaessig selbst

Pruefen:

```bash
grep PAPERLESS_AI_QWEN35_THINK /opt/paperless/paperless.conf
```

## Modell antwortet im Chat, aber Paperless ist langsam

Typische Ursachen:

- paralleler Chat belegt denselben `Ollama`-Dienst
- OCR-Kontext ist zu gross
- Dokument ist lang und das Modell CPU-lastig

Loesung:

- lange Chat-Antworten auslaufen lassen oder stoppen
- `PAPERLESS_AI_CONTENT_CHARS` pruefen
- kleineres Modell oder Fallback verwenden

## Personentag wurde falsch erzeugt

Beispiel:

- aus `Anna Meier` wird `Anja Meier`

Schutz im aktuellen Stand:

- neue Personentags werden nicht blind angelegt
- Personen werden nur wiederverwendet, wenn:
  - der Tag bereits existiert
  - der Name exakt im OCR-Inhalt vorkommt

## Fallback greift nicht

Pruefen:

```dotenv
PAPERLESS_AI_FALLBACK_ENABLED=true
PAPERLESS_AI_FALLBACK_MODEL=qwen3.5:4b
PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true
```

Wichtig:

- wenn `PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true` gesetzt ist, wird nur bei Timeout umgeschaltet
- bei anderen Fehlern bleibt der Lauf beim Primaermodell stehen

## Weboberflaeche speichert Prompt oder Modell nicht

Typische Ursachen:

- Helper-Skripte nicht installiert
- `sudoers`-Dateien fehlen
- `ollama-web.service` hat keinen Zugriff auf die erlaubten Root-Helfer

Pruefen:

```bash
ls -l /usr/local/sbin/paperless-ai-admin /usr/local/sbin/paperless-set-ollama-model
ls -l /etc/sudoers.d/paperless-ai-admin /etc/sudoers.d/paperless-model
```

## `paperless-scheduler.service` fehlerhaft

Bekannter Fix in diesem Projekt:

- alte `qcluster`-Unit nicht weiterverwenden
- stattdessen `celery beat`

Siehe:

- `systemd/paperless-scheduler.service`

## Port `3000` zeigt alte Version

Loesung:

```bash
sudo systemctl restart ollama-web.service
```

danach Browser hart neu laden.

## Modelle vergleichen

Direkter Test gegen `Ollama`:

```bash
curl -sS http://127.0.0.1:11434/api/chat -d '{
  "model": "qwen3.5:4b",
  "stream": false,
  "think": false,
  "messages": [
    {"role": "system", "content": "Antworte kurz."},
    {"role": "user", "content": "Antworte nur mit OK"}
  ]
}'
```

Hinweis: Das neue Gemma 4-Modell `kwmcglon/gemma-4-E4B-it` liefert hochaufloesende Resultate, benoetigt aber eine Ollama-Version >= 0.20.2. Wenn beim `ollama pull` eine `412`-Antwort kommt, ist der Container-Stack noch zu alt und muss auf `ollama/ollama:0.20.2` oder neuer gebracht werden.

Direkter Docker-Check:

```bash
sudo docker exec paperless-ollama ollama --version
sudo docker inspect paperless-ollama --format '{{.Config.Image}}'
```

## `llama.cpp`: `unknown model architecture: 'gemma4'`

Ursache:

- der `llama-cpp`-Container wurde gegen einen zu alten `llama.cpp`-Stand gebaut
- dadurch kann `gemma-4-E4B-it` (GGUF) nicht geladen werden

Fix:

1. Sicherstellen, dass in `.env` ein gemma4-faehiger Commit gesetzt ist:

```bash
LLAMA_CPP_COMMIT=3fc65063d9c356510b86fc2f15ca8aea711bfc47
```

2. `llama-cpp` ohne Cache neu bauen und starten:

```bash
sudo docker compose --profile llama-cpp build --no-cache llama-cpp
sudo docker compose --profile llama-cpp up -d llama-cpp
sudo docker logs --tail=120 paperless-llama-cpp
```

3. Health pruefen:

```bash
curl -fsS http://127.0.0.1:18080/health
```

## OCR-/Vision-Modell ist korrekt angebunden, aber trotzdem unbrauchbar langsam

Typische Ursachen:

- CPU-only VM
- Bild + OCR-Kontext werden zusammen an ein multimodales Modell gesendet
- der Testpfad ist technisch korrekt, aber fuer interaktive Laufzeiten zu schwer

Typische Beobachtung:

- Modell laesst sich ziehen und antwortet grundsaetzlich
- der kombinierte Dokumenttest laeuft trotzdem in Timeouts

Pragmatische Loesung:

- textbasierten OCR-/Strukturpfad als produktiven Default beibehalten
- Vision nur fuer kurze PDFs oder seltene Review-Faelle aktivieren
- kleinere OCR-Kontexte fuer Vision-Tests verwenden
- staerkere Vision-/OCR-Modelle erst mit GPU-Passthrough oder externer Rechenleistung erneut bewerten
## `dependency failed to start: ... ollama-rocm has no healthcheck configured`

Ursache:

- ein abhaengiger Dienst nutzt `depends_on: condition: service_healthy`
- der laufende Ollama-Dienst ist aber `ollama-rocm` ohne `healthcheck`

Fix:

1. Im aktiven Compose-Setup fuer den Ollama-Dienst einen Healthcheck setzen:

```yaml
services:
  ollama-rocm:
    healthcheck:
      test: ["CMD-SHELL", "ollama list >/dev/null 2>&1"]
      interval: 30s
      timeout: 10s
      retries: 10
```

2. Stack neu starten:

```bash
docker compose up -d --force-recreate ollama-rocm
docker compose up -d paperless-ai-web webserver open-webui
```

Alternative:

- Wenn kein Healthcheck gewuenscht ist, in den Abhaengigkeiten `condition: service_started` verwenden.
