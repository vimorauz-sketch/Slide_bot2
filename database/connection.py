from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

# Columns added to existing tables after the initial release. Base.metadata.create_all()
# only creates missing TABLES, not missing COLUMNS on tables that already exist (e.g. a
# slidelab.db from before the Click/Payme webhook support was added) -- this is a minimal,
# idempotent, Alembic-free migration step for that case.
_PENDING_COLUMN_MIGRATIONS = {
    "payment_transactions": [
        ("provider_trans_id", "VARCHAR(100)"),
        ("state", "INTEGER"),
        ("cancel_reason", "INTEGER"),
        ("provider_create_time", "BIGINT"),
        ("provider_perform_time", "BIGINT"),
        ("provider_cancel_time", "BIGINT"),
    ],
}

async def _apply_pending_column_migrations(conn):
    for table, columns in _PENDING_COLUMN_MIGRATIONS.items():
        result = await conn.execute(text(f"PRAGMA table_info({table})"))
        existing_columns = {row[1] for row in result.fetchall()}
        for column_name, column_type in columns:
            if column_name not in existing_columns:
                await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"))

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_pending_column_migrations(conn)
