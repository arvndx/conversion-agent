"""Two basic test sites for the Conversion Agent, served by FastAPI.

Run one site per port, from the app folder:
    SITE=a uvicorn sites.server:app --port 8001     (localhost:8001, site A)
    SITE=b uvicorn sites.server:app --port 8002     (localhost:8002, site B)

The pages have no widget yet. Both domains belong to the same customer (Spice Garden).
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

SITE = os.environ.get("SITE", "a")
SITES_DIR = Path(__file__).resolve().parent
PAGE_DIR = SITES_DIR / f"site_{SITE}"

app = FastAPI(title=f"Spice Garden test site {SITE}")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    page = PAGE_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail=f"No test site named {SITE!r}")
    return page.read_text(encoding="utf-8")


@app.get("/demo", response_class=HTMLResponse)
def demo() -> str:
    # The same Spice Garden page, with the widget in demo mode: no calls to the chat API, mock replies only.
    return (SITES_DIR / "demo" / "index.html").read_text(encoding="utf-8")


@app.get("/widget.js")
def widget() -> FileResponse:
    return FileResponse(SITES_DIR / "widget" / "widget.js", media_type="application/javascript")


@app.get("/health")
def health() -> dict:
    return {"site": SITE, "status": "ok"}
