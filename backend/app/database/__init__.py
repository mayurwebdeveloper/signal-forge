"""SQLAlchemy database setup."""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    migrate_schema()


def migrate_schema() -> None:
    """Add new columns to existing SQLite tables (create_all does not alter).

    Postgres fresh deploys get full schema from create_all; skip ALTER there.
    """
    if not settings.database_url.startswith("sqlite"):
        return

    from sqlalchemy import inspect, text

    alterations: list[tuple[str, str, str]] = [
        ("ai_predictions", "horizons", "JSON"),
        ("ai_predictions", "reasons", "JSON"),
        ("ai_predictions", "prob_low", "FLOAT"),
        ("ai_predictions", "prob_high", "FLOAT"),
        ("daily_suggestions", "horizon", "VARCHAR(10) DEFAULT '1d'"),
        ("daily_suggestions", "model_probability", "FLOAT"),
        ("daily_suggestions", "prob_low", "FLOAT"),
        ("daily_suggestions", "prob_high", "FLOAT"),
        ("daily_suggestions", "outcome_return_pct", "FLOAT"),
        ("daily_suggestions", "outcome_hit", "BOOLEAN"),
        ("daily_suggestions", "outcome_settled_at", "DATETIME"),
    ]
    with engine.begin() as conn:
        inspector = inspect(conn)
        tables = set(inspector.get_table_names())
        for table, column, coltype in alterations:
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
            # Refresh inspector view for subsequent columns on same table
            inspector = inspect(conn)
            tables = set(inspector.get_table_names())
