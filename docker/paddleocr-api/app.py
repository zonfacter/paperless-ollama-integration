from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from paddleocr import PaddleOCR


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def build_ocr() -> PaddleOCR:
    return PaddleOCR(
        lang=os.getenv("PADDLEOCR_LANG", "german"),
        device=os.getenv("PADDLEOCR_DEVICE", "cpu"),
        enable_mkldnn=env_bool("PADDLEOCR_ENABLE_MKLDNN", True),
        cpu_threads=int(os.getenv("PADDLEOCR_CPU_THREADS", "4")),
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


app = FastAPI(title="PaddleOCR API", version="0.1.0")
OCR = build_ocr()


def normalize_result(raw: list[Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    plain_text_parts: list[str] = []

    for entry in raw:
        data = getattr(entry, "res", entry)
        rec_texts = data.get("rec_texts") or []
        rec_scores = data.get("rec_scores") or []
        rec_polys = data.get("rec_polys") or []

        for index, text in enumerate(rec_texts):
            score = rec_scores[index] if index < len(rec_scores) else None
            polygon = rec_polys[index] if index < len(rec_polys) else None
            items.append(
                {
                    "text": text,
                    "score": to_jsonable(score),
                    "polygon": to_jsonable(polygon),
                }
            )
            if text:
                plain_text_parts.append(text)

    return {
        "text": "\n".join(plain_text_parts),
        "items": items,
        "line_count": len(items),
    }


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "lang": os.getenv("PADDLEOCR_LANG", "german"),
        "device": os.getenv("PADDLEOCR_DEVICE", "cpu"),
        "cpu_threads": int(os.getenv("PADDLEOCR_CPU_THREADS", "4")),
        "enable_mkldnn": env_bool("PADDLEOCR_ENABLE_MKLDNN", True),
    }


@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)) -> JSONResponse:
    suffix = Path(file.filename or "upload.bin").suffix or ".bin"
    started = time.time()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            content = await file.read()
            temp_file.write(content)
        finally:
            temp_file.flush()

    try:
        raw = OCR.predict(str(temp_path))
        normalized = normalize_result(list(raw))
        normalized["seconds"] = round(time.time() - started, 2)
        normalized["filename"] = file.filename
        return JSONResponse(normalized)
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
