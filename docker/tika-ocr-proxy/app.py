from __future__ import annotations

import os

import fitz  # PyMuPDF
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

app = FastAPI(title="Tika-PaddleOCR Proxy", version="1.0.0")

PADDLEOCR_URL = os.getenv("PADDLEOCR_API_URL", "http://paddleocr-api:8091")
PDF_DPI = int(os.getenv("PROXY_PDF_DPI", "200"))
PDF_MAX_PAGES = int(os.getenv("PROXY_PDF_MAX_PAGES", "50"))


def _pdf_has_text_layer(pdf_bytes: bytes) -> tuple[bool, str]:
    """Return (has_text, extracted_text) for PDFs with an embedded text layer."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            text = page.get_text().strip()
            if text:
                pages.append(text)
        doc.close()
        combined = "\n\n".join(pages)
        return bool(combined), combined
    except Exception:
        return False, ""


def _pdf_to_page_images(pdf_bytes: bytes, dpi: int, max_pages: int) -> list[bytes]:
    """Render each PDF page to a PNG image at the given DPI."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    images: list[bytes] = []
    for i in range(min(len(doc), max_pages)):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        images.append(pix.tobytes("png"))
    doc.close()
    return images


async def _paddleocr_image(client: httpx.AsyncClient, img_bytes: bytes, name: str) -> str:
    try:
        resp = await client.post(
            f"{PADDLEOCR_URL}/ocr",
            files={"file": (name, img_bytes, "image/png")},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json().get("text", "")
    except Exception:
        return ""


async def _extract_pdf(pdf_bytes: bytes) -> str:
    # Fast path: PDF already has a text layer (e.g. processed by Paperless)
    has_text, text = _pdf_has_text_layer(pdf_bytes)
    if has_text:
        return text

    # Slow path: render pages and OCR with PaddleOCR
    images = _pdf_to_page_images(pdf_bytes, PDF_DPI, PDF_MAX_PAGES)
    if not images:
        return ""

    async with httpx.AsyncClient() as client:
        # Health-check PaddleOCR first so we fail fast if it is down
        try:
            health = await client.get(f"{PADDLEOCR_URL}/healthz", timeout=5.0)
            health.raise_for_status()
        except Exception:
            return ""

        parts: list[str] = []
        for idx, img in enumerate(images):
            page_text = await _paddleocr_image(client, img, f"page_{idx + 1}.png")
            if page_text.strip():
                parts.append(page_text)

    return "\n\n".join(parts)


# ── Tika-compatible endpoints ──────────────────────────────────────────────────

@app.put("/tika")
@app.post("/tika")
async def tika_extract(request: Request) -> PlainTextResponse:
    body = await request.body()
    if not body:
        return PlainTextResponse("")

    content_type = request.headers.get("content-type", "").lower()
    is_pdf = "pdf" in content_type or body[:4] == b"%PDF"

    if is_pdf:
        text = await _extract_pdf(body)
        return PlainTextResponse(text)

    # Image sent directly (Open WebUI may send page images too)
    if any(t in content_type for t in ("image/", "png", "jpeg", "jpg", "tiff", "bmp")):
        ext = "jpg" if ("jpeg" in content_type or "jpg" in content_type) else "png"
        async with httpx.AsyncClient() as client:
            text = await _paddleocr_image(client, body, f"image.{ext}")
        return PlainTextResponse(text)

    return PlainTextResponse("")


@app.get("/tika")
async def tika_info() -> dict:
    return {"version": "tika-paddleocr-proxy/1.0", "paddleocr_url": PADDLEOCR_URL}


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}
