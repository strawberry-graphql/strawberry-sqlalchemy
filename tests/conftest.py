"""
    conftest.py for strawberry_sqlalchemy_mapper.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""

import contextlib
import functools
import logging
import platform
import socket
from typing import Callable

import pytest
import sqlalchemy
from packaging import version
from sqlalchemy import orm
from sqlalchemy.engine import Engine
from sqlalchemy.ext import asyncio
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from testing.postgresql import Postgresql, PostgresqlFactory

SQLA_VERSION = version.parse(sqlalchemy.__version__)
SQLA2 = SQLA_VERSION >= version.parse("2.0")


def _pick_unused_port():
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def postgresql_factory() -> PostgresqlFactory:
    factory = PostgresqlFactory(cache_initialized_db=True, port=_pick_unused_port())
    yield factory
    factory.clear_cache()


@pytest.fixture
def postgresql(postgresql_factory) -> Postgresql:
    db = postgresql_factory()
    yield db
    db.stop()


if platform.system() == "Windows":
    # Our windows test pipeline doesn't play nice with postgres because
    # Github Actions doesn't support containers on windows.
    # It would probably be nicer if we chcked if postgres is installed
    logging.info("Skipping postgresql tests on Windows OS")
    SUPPORTED_DBS = []
else:
    SUPPORTED_DBS = ["postgresql"]  # TODO: Add sqlite and mysql.


@pytest.fixture(params=SUPPORTED_DBS)
def engine_factory(request) -> Engine:
    if request.param == "postgresql":
        url = (
            request.getfixturevalue("postgresql")
            .url()
            .replace("postgresql://", "postgresql+psycopg://")
        )
    else:
        raise ValueError("Unsupported database: %s", request.param)
    kwargs = {}
    if not SQLA2:
        kwargs["future"] = True
    return functools.partial(sqlalchemy.create_engine, url, **kwargs)


@pytest.fixture
def engine(engine_factory) -> Engine:
    return engine_factory()


@pytest.fixture
def sessionmaker(engine) -> orm.sessionmaker:
    return orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(params=SUPPORTED_DBS)
def async_engine_factory(request) -> Callable[[], AsyncEngine]:
    """Needed to benchmark async code which can't share engines across threads."""
    if request.param == "postgresql":
        url = (
            request.getfixturevalue("postgresql")
            .url()
            .replace("postgresql://", "postgresql+psycopg://")
        )
    else:
        raise ValueError("Unsupported database: %s", request.param)
    kwargs = {}
    if not SQLA2:
        kwargs["future"] = True
    return functools.partial(create_async_engine, url, **kwargs)


@pytest.fixture
def async_engine(async_engine_factory) -> AsyncEngine:
    return async_engine_factory()


@pytest.fixture
def async_sessionmaker(async_engine) -> asyncio.async_sessionmaker:
    return asyncio.async_sessionmaker(async_engine)


@pytest.fixture
def base():
    class Base(AsyncAttrs, orm.DeclarativeBase):
        pass

    return Base
