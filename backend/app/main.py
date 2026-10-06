import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from sqlmodel import Session, select

from app.category_config import invalidate as invalidate_category_config
from app.db import engine, init_db
from app.models import Category, Profile
from app import onboarding as onboarding_service
from app.routers import admin, auth, claims, dashboard, mailbox, manage, onboarding, pricing, profiles, search, taxonomy
from app.routers.admin import reset_demo_data
from app.seed import seed_demo
from app.seed_taxonomy import seed_taxonomy

from agent.db import init_agent_db
from agent.extraction import extract_fields
from agent.routes import router as agent_router

# This is a demo: by default every backend start begins from a clean, freshly seeded database
# (all earlier edits, claims, emails and agent conversations are wiped). Set
# RESET_ON_STARTUP=false to keep data across restarts — and never leave it on anywhere real
# data lives. Note `uvicorn --reload` restarts the app on every code change, which resets too.
RESET_ON_STARTUP = os.environ.get("RESET_ON_STARTUP", "true").strip().lower() in ("1", "true", "yes", "on")

app = FastAPI(title="ClearRank API")

# The product layer never imports the agent; main.py hands it the one agent function it needs.
onboarding_service.set_extractor(extract_fields)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(profiles.router)
app.include_router(mailbox.router)
app.include_router(taxonomy.router)
app.include_router(claims.router)
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(dashboard.router)
app.include_router(manage.router)
app.include_router(pricing.router)
app.include_router(admin.router)
app.include_router(agent_router)


@app.on_event("startup")
def on_startup():
    if RESET_ON_STARTUP:
        reset_demo_data()
        return
    # Keep existing data: create any missing tables and seed only what is empty.
    init_db()
    init_agent_db()
    with Session(engine) as session:
        needs_taxonomy = session.exec(select(Category)).first() is None
        needs_profiles = session.exec(select(Profile)).first() is None
    # Seed only after the sessions above are closed: they hold read locks that a TRUNCATE would wait on.
    if needs_taxonomy:
        with Session(engine) as session:
            seed_taxonomy(session)
        invalidate_category_config()
    if needs_profiles:
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
