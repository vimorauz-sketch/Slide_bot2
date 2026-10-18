"""
Verifies the idempotent, Alembic-free column migration in database/connection.py
(_apply_pending_column_migrations) correctly upgrades a pre-existing (old-schema)
SQLite file -- the shape slidelab.db has if the bot was deployed before the
Click/Payme webhook columns were added -- without losing any existing data.
"""
import os
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from database.connection import Base, _apply_pending_column_migrations
import database.models  # noqa: F401 -- registers ORM tables on Base.metadata


async def _create_old_schema_db(db_path: str):
    """Mimics the pre-migration payment_transactions table shape (no provider_*
    columns) with one real row, independent of the current ORM model."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE payment_transactions (
                id VARCHAR(36) PRIMARY KEY,
                order_id VARCHAR(36) NOT NULL,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                provider VARCHAR(50),
                status VARCHAR(50),
                created_at DATETIME
            )
        """))
        await conn.execute(text(
            "INSERT INTO payment_transactions (id, order_id, user_id, amount, provider, status) "
            "VALUES ('tx-1', 'order-1', 111, 1750, 'MOCK', 'WAITING_PAYMENT')"
        ))
    await engine.dispose()


@pytest.mark.asyncio
async def test_migration_adds_missing_columns_without_dropping_existing_rows(tmp_path):
    db_path = os.path.join(str(tmp_path), "old_schema.db")
    await _create_old_schema_db(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_pending_column_migrations(conn)

        async with engine.begin() as conn:
            result = await conn.execute(text("PRAGMA table_info(payment_transactions)"))
            columns = {row[1] for row in result.fetchall()}
            for expected in ("provider_trans_id", "state", "cancel_reason",
                              "provider_create_time", "provider_perform_time", "provider_cancel_time"):
                assert expected in columns

            # The pre-existing row must survive the migration untouched.
            row = (await conn.execute(text(
                "SELECT id, order_id, amount, status FROM payment_transactions WHERE id = 'tx-1'"
            ))).fetchone()
            assert row == ("tx-1", "order-1", 1750, "WAITING_PAYMENT")

            # New columns on the pre-existing row default to NULL, not an error.
            new_col_row = (await conn.execute(text(
                "SELECT provider_trans_id, state FROM payment_transactions WHERE id = 'tx-1'"
            ))).fetchone()
            assert new_col_row == (None, None)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_is_safe_to_run_twice(tmp_path):
    db_path = os.path.join(str(tmp_path), "old_schema_2.db")
    await _create_old_schema_db(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_pending_column_migrations(conn)
        # Running it again (e.g. bot restarted) must not raise "duplicate column".
        async with engine.begin() as conn:
            await _apply_pending_column_migrations(conn)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_on_a_brand_new_database_is_a_no_op(tmp_path):
    # A fresh install (create_all makes the table with all current columns already
    # present) must not error when the migration step runs right after it.
    db_path = os.path.join(str(tmp_path), "fresh.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _apply_pending_column_migrations(conn)
    finally:
        await engine.dispose()
