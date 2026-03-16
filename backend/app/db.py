from sqlalchemy import text
from sqlmodel import SQLModel, create_engine, Session
from .settings import settings

# SQLite specific: check_same_thread=False for FastAPI async
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=settings.app_env == "dev"  # Log SQL in dev mode
)


def _sqlite_table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _ensure_sqlite_column(conn, table_name: str, column_name: str, definition: str) -> None:
    columns = _sqlite_table_columns(conn, table_name)
    if column_name not in columns:
        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


def _run_sqlite_migrations() -> None:
    """Add backward-compatible columns for existing SQLite databases."""
    with engine.begin() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }

        if "visit_events" in tables:
            _ensure_sqlite_column(
                conn,
                "visit_events",
                "person_type",
                "VARCHAR(20) NOT NULL DEFAULT 'CUSTOMER'",
            )
            _ensure_sqlite_column(conn, "visit_events", "employee_id", "INTEGER")
            _ensure_sqlite_column(conn, "visit_events", "face_match_score", "FLOAT")
            _ensure_sqlite_column(conn, "visit_events", "recognition_source", "VARCHAR(50)")
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_visit_events_person_type "
                    "ON visit_events (person_type)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_visit_events_employee_id "
                    "ON visit_events (employee_id)"
                )
            )


def init_db() -> None:
    """Initialize database tables"""
    SQLModel.metadata.create_all(engine)
    if settings.database_url.startswith("sqlite"):
        _run_sqlite_migrations()

def get_session():
    """Get database session for dependency injection"""
    with Session(engine) as session:
        yield session
