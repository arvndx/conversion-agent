import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Profile
from app.routers import admin, dashboard, inbox, manage, pricing, profiles, search
from app.seed import seed_demo

from agent.db import init_agent_db
from agent.routes import router as agent_router

app = FastAPI(title="ClearRank API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(profiles.router)
app.include_router(inbox.router)
app.include_router(dashboard.router)
app.include_router(manage.router)
app.include_router(pricing.router)
app.include_router(admin.router)
app.include_router(agent_router)


@app.on_event("startup")
def on_startup():
    init_db()
    init_agent_db()
    with Session(engine) as session:
        if session.exec(select(Profile)).first() is None:
            seed_demo()


@app.get("/health")
def health():
    return {"status": "ok"}


# Serves the built frontend (backend/static/, produced by `npm run build`) when present,
# so a single process can host both the API and the SPA in production. Registered last so
# it never shadows an /api/* route above. Local dev (no ./static) is unaffected.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
