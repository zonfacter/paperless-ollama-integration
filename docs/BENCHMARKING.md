# MI50 Benchmarking

Ziel: reproduzierbare Benchmarks fuer lokale Modelle und Power-Caps erzeugen und als Artefakte im Repository ablegen.

## Voraussetzungen

- laufender Stack mit `paperless-ollama` und `paperless-ai-web`
- funktionierende API-Endpunkte:
  - Ollama: `http://127.0.0.1:11434`
  - Web/API: `http://127.0.0.1:3000`
- Python 3 auf dem Host

## Benchmark-Skript

Pfad:

```bash
scripts/nas/run_ollama_benchmark.py
```

Das Skript schreibt drei Ausgaben:

- JSON fuer die Website: `data/mi50-benchmark-results.json`
- CSV fuer Auswertung: `data/mi50-benchmark-results.csv`
- Markdown fuer Repo: `docs/BENCHMARK_RESULTS.md`

## Standardlauf

Aus dem Repo-Root:

```bash
python3 scripts/nas/run_ollama_benchmark.py \
  --models "qwen3.5:4b,qwen3.5:9b,qwen2.5-coder:14b" \
  --power-models "qwen3.5:4b,qwen3.5:9b" \
  --power-levels "90,120,150,170,190" \
  --num-predict 160 \
  --temperature 0.2 \
  --ollama-url "http://127.0.0.1:11434" \
  --web-url "http://127.0.0.1:3000"
```

## Schnelllauf (Smoke Test)

```bash
python3 scripts/nas/run_ollama_benchmark.py \
  --models "qwen3.5:4b" \
  --power-levels "120" \
  --num-predict 96
```

## Verifikation

- JSON existiert und ist valide:

```bash
python3 -m json.tool data/mi50-benchmark-results.json >/dev/null
```

- Website liest den Stand:

```bash
curl -sS http://127.0.0.1:3000/api/system/metrics | head
```

Hinweis: Die Benchmark-Tabelle in der UI nutzt `data/mi50-benchmark-results.json`.

## Fuer Veroeffentlichung im Repository

Nach einem Lauf:

```bash
git add data/mi50-benchmark-results.json data/mi50-benchmark-results.csv docs/BENCHMARK_RESULTS.md
git commit -m "bench(mi50): update model and power benchmark results"
```

Empfehlung:

- bei jedem groesseren Treiber-/Ollama-/Model-Update neuen Lauf erzeugen
- immer dieselben Prompt- und `num_predict`-Werte fuer Vergleichbarkeit nutzen
