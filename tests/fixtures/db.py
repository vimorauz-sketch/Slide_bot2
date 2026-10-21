import tempfile
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.connection import Base


async def make_test_session_factory():
    """
    Creates an isolated SQLite database in a temp directory so tests never
    touch the real slidelab.db used by the running bot.
    """
    tmp_dir = tempfile.mkdtemp(prefix="slidelab_test_")
    db_path = os.path.join(tmp_dir, "test.db")
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


def make_test_storage_dir():
    return tempfile.mkdtemp(prefix="slidelab_test_storage_")
