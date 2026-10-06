import os

# Point the app at a separate database BEFORE any app module is imported, so tests can drop and
# rebuild tables without touching the development data. Create it once with:
#   psql -d postgres -c "CREATE DATABASE clearrank_test OWNER clearrank"
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://clearrank:clearrank@localhost:5432/clearrank_test"
)
os.environ["RESET_ON_STARTUP"] = "false"
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app.category_config import invalidate as invalidate_category_config  # noqa: E402
from app.db import engine, init_db  # noqa: E402
from agent import models as _agent_models  # noqa: E402, F401  (registers the agent tables)
from app.seed import seed_demo  # noqa: E402
from app.seed_taxonomy import seed_taxonomy  # noqa: E402


def rebuild():
    """Drop every table and seed the taxonomy and demo profiles again."""
    SQLModel.metadata.drop_all(engine)
    init_db()
    with Session(engine) as session:
        seed_taxonomy(session)
    invalidate_category_config()
    seed_demo()


@pytest.fixture(scope="session")
def seeded_db():
    """A freshly built database with the taxonomy and demo profiles seeded, shared by the session."""
    rebuild()
    yield engine


@pytest.fixture(scope="module")
def mutates_db(seeded_db):
    """For test modules that change shared seed data (claims, sign-ins): put a fresh seed back after."""
    yield
    rebuild()


@pytest.fixture()
def session(seeded_db):
    with Session(seeded_db) as s:
        yield s


@pytest.fixture(autouse=True)
def _scrape_in_the_foreground(monkeypatch):
    """Production reads pages in a background thread; tests want the result before the call returns."""
    from app import onboarding
    monkeypatch.setattr(onboarding, "SCRAPE_IN_BACKGROUND", False)
