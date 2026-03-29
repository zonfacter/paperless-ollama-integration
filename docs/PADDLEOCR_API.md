# PaddleOCR API

## Ziel

Dieses Projekt enthaelt optional einen kleinen `PaddleOCR`-API-Container, damit OCR nicht nur als lokaler Einzelskript-Test, sondern als separater Dienst bereitsteht.

Der Fokus ist:

- einfacher HTTP-Zugriff
- CPU-Betrieb
- begrenzte Thread-Zahl fuer Hybrid-CPUs und VMs
- spaetere Anbindung an `paperless-ngx` oder die Port-`3000`-Review-Oberflaeche

## Pfad

```text
docker/paddleocr-api/
```

Enthalten:

- `Dockerfile`
- `requirements.txt`
- `app.py`
- `docker-compose.example.yml`

## API

### Health

```bash
curl -sS http://127.0.0.1:8091/healthz
```

### OCR

```bash
curl -sS -F "file=@/path/to/page.jpg" http://127.0.0.1:8091/ocr
```

Antwort:

- `text`
- `items`
- `line_count`
- `seconds`
- `filename`

## Konfiguration

Wichtige Umgebungsvariablen:

```dotenv
PADDLEOCR_LANG=german
PADDLEOCR_DEVICE=cpu
PADDLEOCR_CPU_THREADS=4
PADDLEOCR_ENABLE_MKLDNN=true
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=true
```

## Warum eigener Container

Die Tests auf der lokalen VM haben gezeigt:

- `PaddleOCR` ist fachlich interessant
- direkte Host-Installation und generische Slim-Container koennen an Runtime-Details scheitern
- deshalb ist ein eigener, reproduzierbarer API-Container sinnvoller als lose Einzelbefehle

## Hinweise

- Das ist bewusst eine optionale Komponente.
- Sie ersetzt die bestehende Tesseract-/Paperless-OCR nicht automatisch.
- Sie ist zunaechst als separater Dienst fuer Vergleich, spaetere Integration und OCR-Experimente gedacht.
