from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings


def normalize_db_url(url: str):
    """DATABASE_URL as Railway/Heroku give it (postgres://…) -> an asyncpg URL for SQLAlchemy.
    Returns (url, connect_args)."""
    url = (url or "").strip() or "sqlite+aiosqlite:///slidelab.db"
    connect_args = {}
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break
    if url.startswith("postgresql+asyncpg://"):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        if sslmode in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = "require"
        url = urlunsplit(parts._replace(query=urlencode(query)))
    elif url.startswith("sqlite:///"):
        url = "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
    return url, connect_args


DB_URL, _connect_args = normalize_db_url(settings.DATABASE_URL)
IS_POSTGRES = DB_URL.startswith("postgresql")
_engine_kwargs = {"echo": False, "connect_args": _connect_args}
if IS_POSTGRES:
    _engine_kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)
engine = create_async_engine(DB_URL, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# Columns added to existing tables after the initial release. Base.metadata.create_all()
# only creates missing TABLES, not missing COLUMNS on tables that already exist -- this is a
# minimal, idempotent, Alembic-free migration step for that case (SQLite and PostgreSQL).
_PENDING_COLUMN_MIGRATIONS = {
    "payment_transactions": [
        ("provider_trans_id", "VARCHAR(100)"),
        ("state", "INTEGER"),
        ("cancel_reason", "INTEGER"),
        ("provider_create_time", "BIGINT"),
        ("provider_perform_time", "BIGINT"),
        ("provider_cancel_time", "BIGINT"),
    ],
    "users": [
        ("is_blocked", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("blocked_reason", "VARCHAR(255)"),
        ("bot_blocked", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("last_seen_at", "TIMESTAMP"),
    ],
    "presentation_orders": [
        ("paid_at", "TIMESTAMP"),
        ("paid_by", "VARCHAR(30)"),
        ("bill_id", "VARCHAR(64)"),
        ("payment_url", "TEXT"),
        ("bill_expires_at", "TIMESTAMP"),
        ("paid_amount", "INTEGER"),
        ("fee_amount", "INTEGER"),
        ("payment_provider", "VARCHAR(30)"),
        ("delivered_at", "TIMESTAMP"),
        ("content_json", "TEXT"),
        ("language", "VARCHAR(10)"),
    ],
}


async def _apply_pending_column_migrations(conn):
    def existing(sync_conn, table):
        insp = inspect(sync_conn)
        if not insp.has_table(table):
            return None
        return {c["name"] for c in insp.get_columns(table)}

    for table, columns in _PENDING_COLUMN_MIGRATIONS.items():
        have = await conn.run_sync(existing, table)
        if have is None:
            continue
        for column_name, column_type in columns:
            if column_name not in have:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"))


async def init_db():
    import database.models  # noqa: F401 - registers the tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_pending_column_migrations(conn)
