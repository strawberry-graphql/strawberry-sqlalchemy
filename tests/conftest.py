"""
    Dummy conftest.py for strawberry_sqlalchemy_mapper.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""
import asyncio
import datetime
from contextlib import asynccontextmanager
from typing import AsyncContextManager, AsyncGenerator, Callable

import pytest
import pytest_asyncio
from model import Model
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

TxManager = Callable[[], AsyncContextManager[AsyncSession]]


def tx_context_manager(engine: AsyncEngine) -> TxManager:
    @asynccontextmanager
    async def context_manager() -> AsyncGenerator[AsyncSession, None]:
        try:
            session = AsyncSession(bind=engine, expire_on_commit=False)
            await session.begin()
            yield session
        finally:
            await session.rollback()
            await session.close()

    return context_manager


def pytest_addoption(parser):
    parser.addoption(
        "--keep-db",
        action="store_true",
        help="Keep test database after the test session",
    )


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_name():
    return f"test_db_{datetime.datetime.now().isoformat()}"


@pytest_asyncio.fixture(scope="session")
async def url(db_name):
    return "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine(url):
    return create_async_engine(url, future=True)


@pytest_asyncio.fixture(scope="session")
async def tables(engine: AsyncEngine, request):
    async with engine.begin() as conn:
        # drop if exists
        await conn.run_sync(Model.metadata.drop_all)
        await conn.run_sync(Model.metadata.create_all)
    yield

    if not request.config.getoption("--keep-db", default=False):
        async with engine.begin() as conn:
            await conn.run_sync(Model.metadata.drop_all)

    # Close all underlying connections
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine, tables):
    context_manager = tx_context_manager(engine)
    async with context_manager() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def transaction(engine: AsyncEngine, tables):
    return tx_context_manager(engine)
