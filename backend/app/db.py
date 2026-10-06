import os

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()

# Local-dev default matches the `clearrank` role/database created in the README's setup steps.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://clearrank:clearrank@localhost:5432/clearrank")

# pool_pre_ping: transparently replaces connections the server closed (restarts, idle timeouts).
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def psycopg_conninfo() -> str:
    """The same database as a plain libpq URL, for libraries that use psycopg directly
    (the LangGraph checkpointer) rather than going through SQLAlchemy."""
    return DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
