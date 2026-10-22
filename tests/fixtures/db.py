import tempfile
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.connection import Base


async def make_test_session_factory():
    """
    Creates an isolated SQLite database in a temp directory so tests never
    touch the real slidelab.db used by the running bot.

    With TEST_DATABASE_URL (e.g. postgres://user@localhost:5433/slidelab_test) the same tests run
    against PostgreSQL instead: the schema is dropped and created again for every test.
    """
    pg = os.getenv("TEST_DATABASE_URL", "")
    if pg:
        from database.connection import normalize_db_url
        import database.models  # noqa: F401
        url, args = normalize_db_url(pg)
        engine = create_async_engine(url, echo=False, connect_args=args)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        return engine, async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    tmp_dir = tempfile.mkdtemp(prefix="slidelab_test_")
    db_path = os.path.join(tmp_dir, "test.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


def make_test_storage_dir():
    return tempfile.mkdtemp(prefix="slidelab_test_storage_")
