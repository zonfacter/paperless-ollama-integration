#!/usr/bin/env python3
"""
Runs reproducible Ollama benchmarks for MI50/NAS setups and writes:
- JSON compatible with web/server.py benchmark reader
- CSV flat export
- Markdown summary for repository publishing
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PROMPT = (
    "Schreibe eine robuste Python-Funktion parse_nginx_logs(lines), die Combined Log Format Zeilen parst, "
    "Statusklassen zaehlt, die Top-5 Pfade liefert und die mittlere Antwortzeit berechnet. "
    "Gib vollstaendigen Code plus kurze Erklaerung und einfache Tests aus."
)


def _http_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 180.0) -> tuple[int, Any]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            text = raw.decode("utf-8", errors="replace") if raw else ""
            return resp.status, json.loads(text) if text else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        text = raw.decode("utf-8", errors="replace") if raw else ""
        try:
            payload = json.loads(text) if text else {"error": exc.reason}
        except Exception:
            payload = {"error": text or str(exc)}
        return exc.code, payload
    except Exception as exc:
        return 500, {"error": str(exc)}


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _primary_gpu_card(metrics_payload: dict[str, Any]) -> dict[str, Any]:
    gpu = metrics_payload.get("gpu", {}) if isinstance(metrics_payload, dict) else {}
    cards = gpu.get("cards", []) if isinstance(gpu, dict) else []
    if isinstance(cards, list) and cards:
        first = cards[0]
        if isinstance(first, dict):
            return first
    return {}


def _snapshot(base_web_url: str) -> dict[str, Any]:
    status, payload = _http_json(f"{base_web_url}/api/system/metrics", timeout=20)
    if status != 200 or not isinstance(payload, dict):
        return {}
    card = _primary_gpu_card(payload)
    return {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "temperature_c": card.get("temperature_c"),
        "power_watts": card.get("power_watts"),
        "power_cap_watts": card.get("power_cap_watts"),
        "gpu_busy_percent": card.get("gpu_busy_percent"),
        "vram_percent": card.get("vram_percent"),
    }


def _set_power_cap(base_web_url: str, watts: int) -> None:
    status, payload = _http_json(
        f"{base_web_url}/api/system/gpu-power-cap",
        method="POST",
        payload={"watts": watts},
        timeout=30,
    )
    if status != 200:
        raise RuntimeError(f"power-cap set failed ({status}): {payload}")


def _run_once(base_ollama_url: str, model: str, prompt: str, num_predict: int, temperature: float) -> dict[str, Any]:
    started = time.time()
    status, payload = _http_json(
        f"{base_ollama_url}/api/generate",
        method="POST",
        payload={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": temperature},
        },
        timeout=1200,
    )
    wall_s = round(time.time() - started, 2)
    if status != 200 or not isinstance(payload, dict):
        return {
            "model": model,
            "elapsed_wall_s": wall_s,
            "load_s": None,
            "prompt_eval_count": None,
            "prompt_eval_s": None,
            "eval_count": None,
            "eval_s": None,
            "tokens_per_s": None,
            "done_reason": None,
            "text_preview": "",
            "text_chars": 0,
            "error": payload.get("error") if isinstance(payload, dict) else str(payload),
        }
    load_ns = payload.get("load_duration") or 0
    pe_ns = payload.get("prompt_eval_duration") or 0
    e_ns = payload.get("eval_duration") or 0
    eval_count = payload.get("eval_count")
    tokens_per_s = None
    if isinstance(eval_count, int) and e_ns:
        tokens_per_s = round(eval_count / (float(e_ns) / 1_000_000_000.0), 2)
    text = str(payload.get("response") or "")
    return {
        "model": model,
        "elapsed_wall_s": wall_s,
        "load_s": round(float(load_ns) / 1_000_000_000.0, 2) if load_ns else 0.0,
        "prompt_eval_count": payload.get("prompt_eval_count"),
        "prompt_eval_s": round(float(pe_ns) / 1_000_000_000.0, 2) if pe_ns else 0.0,
        "eval_count": eval_count,
        "eval_s": round(float(e_ns) / 1_000_000_000.0, 2) if e_ns else 0.0,
        "tokens_per_s": tokens_per_s,
        "done_reason": payload.get("done_reason"),
        "text_preview": text[:240],
        "text_chars": len(text),
    }


def _write_csv(path: Path, model_sweep: list[dict[str, Any]], power_sweep: list[dict[str, Any]]) -> None:
    _ensure_parent(path)
    rows: list[dict[str, Any]] = []
    for row in model_sweep:
        out = dict(row)
        out["kind"] = "model_sweep"
        out["power_watts"] = row.get("before", {}).get("power_cap_watts") if isinstance(row.get("before"), dict) else None
        rows.append(out)
    for row in power_sweep:
        out = dict(row)
        out["kind"] = "power_sweep"
        rows.append(out)
    fields = [
        "kind",
        "model",
        "power_watts",
        "tokens_per_s",
        "elapsed_wall_s",
        "load_s",
        "prompt_eval_count",
        "prompt_eval_s",
        "eval_count",
        "eval_s",
        "done_reason",
        "text_chars",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _md_table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Modell | Power | tok/s | Wall (s) | Load (s) | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        status = "ok" if not row.get("error") else f"error: {row.get('error')}"
        lines.append(
            f"| {row.get('model','')} | {row.get('power_watts','-')} | {row.get('tokens_per_s','-')} | "
            f"{row.get('elapsed_wall_s','-')} | {row.get('load_s','-')} | {status} |"
        )
    return "\n".join(lines)


def _write_markdown(path: Path, model_sweep: list[dict[str, Any]], power_sweep: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    _ensure_parent(path)
    model_rows = []
    for row in model_sweep:
        model_rows.append(
            {
                "model": row.get("model"),
                "power_watts": row.get("before", {}).get("power_cap_watts") if isinstance(row.get("before"), dict) else "-",
                "tokens_per_s": row.get("tokens_per_s"),
                "elapsed_wall_s": row.get("elapsed_wall_s"),
                "load_s": row.get("load_s"),
                "error": row.get("error"),
            }
        )
    power_rows = []
    for row in power_sweep:
        power_rows.append(
            {
                "model": row.get("model"),
                "power_watts": row.get("power_watts"),
                "tokens_per_s": row.get("tokens_per_s"),
                "elapsed_wall_s": row.get("elapsed_wall_s"),
                "load_s": row.get("load_s"),
                "error": row.get("error"),
            }
        )
    text = (
        f"# Benchmark Results\n\n"
        f"- generated_at: {meta.get('generated_at')}\n"
        f"- ollama_url: {meta.get('ollama_url')}\n"
        f"- web_url: {meta.get('web_url')}\n"
        f"- num_predict: {meta.get('num_predict')}\n"
        f"- temperature: {meta.get('temperature')}\n\n"
        f"## Model Sweep\n\n{_md_table(model_rows)}\n\n"
        f"## Power Sweep\n\n{_md_table(power_rows)}\n"
    )
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ollama MI50 benchmark and write JSON/CSV/Markdown outputs.")
    parser.add_argument("--models", required=True, help="Comma-separated model list for model_sweep")
    parser.add_argument("--power-models", default="", help="Comma-separated model list for power_sweep (default: first model)")
    parser.add_argument("--power-levels", default="90,120,150,170,190", help="Comma-separated watts for power_sweep")
    parser.add_argument("--num-predict", type=int, default=160)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--web-url", default="http://127.0.0.1:3000")
    parser.add_argument("--output-json", default="data/mi50-benchmark-results.json")
    parser.add_argument("--output-csv", default="data/mi50-benchmark-results.csv")
    parser.add_argument("--output-md", default="docs/BENCHMARK_RESULTS.md")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("No models provided", file=sys.stderr)
        return 2
    power_models = [m.strip() for m in args.power_models.split(",") if m.strip()] or [models[0]]
    power_levels = [int(x.strip()) for x in args.power_levels.split(",") if x.strip()]

    model_sweep: list[dict[str, Any]] = []
    for model in models:
        before = _snapshot(args.web_url)
        result = _run_once(args.ollama_url, model, args.prompt, args.num_predict, args.temperature)
        after = _snapshot(args.web_url)
        result["before"] = before
        result["after"] = after
        model_sweep.append(result)
        print(f"model_sweep {model}: tok/s={result.get('tokens_per_s')} wall={result.get('elapsed_wall_s')}s")

    power_sweep: list[dict[str, Any]] = []
    for watts in power_levels:
        try:
            _set_power_cap(args.web_url, watts)
            time.sleep(2)
        except Exception as exc:
            print(f"power_cap {watts} failed: {exc}", file=sys.stderr)
            continue
        for model in power_models:
            before = _snapshot(args.web_url)
            result = _run_once(args.ollama_url, model, args.prompt, args.num_predict, args.temperature)
            after = _snapshot(args.web_url)
            result["power_watts"] = watts
            result["before"] = before
            result["after"] = after
            power_sweep.append(result)
            print(f"power_sweep {model} @{watts}W: tok/s={result.get('tokens_per_s')} wall={result.get('elapsed_wall_s')}s")

    output = {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ollama_url": args.ollama_url,
            "web_url": args.web_url,
            "num_predict": args.num_predict,
            "temperature": args.temperature,
            "models": models,
            "power_models": power_models,
            "power_levels": power_levels,
        },
        "model_sweep": model_sweep,
        "power_sweep": power_sweep,
    }

    out_json = Path(args.output_json)
    out_csv = Path(args.output_csv)
    out_md = Path(args.output_md)
    _ensure_parent(out_json)
    out_json.write_text(json.dumps(output, ensure_ascii=True, indent=2), encoding="utf-8")
    _write_csv(out_csv, model_sweep, power_sweep)
    _write_markdown(out_md, model_sweep, power_sweep, output["meta"])

    print(f"written: {out_json}")
    print(f"written: {out_csv}")
    print(f"written: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

