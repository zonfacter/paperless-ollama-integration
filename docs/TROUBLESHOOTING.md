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
