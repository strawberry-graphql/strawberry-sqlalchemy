import asyncio
import time
from typing import List
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
import sqlalchemy.orm
import strawberry
import strawberry_sqlalchemy_mapper
from pytest_codspeed.plugin import BenchmarkFixture
from sqlalchemy import orm
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info


@pytest.fixture
def populated_tables(engine, base, sessionmaker):
    class A(base):
        __tablename__ = "a"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    class B(base):
        __tablename__ = "b"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    class C(base):
        __tablename__ = "c"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    class D(base):
        __tablename__ = "d"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    class E(base):
        __tablename__ = "e"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)

    class Parent(base):
        __tablename__ = "parent"
        id = sa.Column(sa.Integer, autoincrement=True, primary_key=True)
        a_id = sa.Column(sa.Integer, sa.ForeignKey("a.id"))
        b_id = sa.Column(sa.Integer, sa.ForeignKey("b.id"))
        c_id = sa.Column(sa.Integer, sa.ForeignKey("c.id"))
        d_id = sa.Column(sa.Integer, sa.ForeignKey("d.id"))
        e_id = sa.Column(sa.Integer, sa.ForeignKey("e.id"))
        a = sa.orm.relationship("A", backref="parents")
        b = sa.orm.relationship("B", backref="parents")
        c = sa.orm.relationship("C", backref="parents")
        d = sa.orm.relationship("D", backref="parents")
        e = sa.orm.relationship("E", backref="parents")

    base.metadata.create_all(engine)
    with sessionmaker() as session:
        for _ in range(1000):
            session.add(A())
            session.add(B())
            session.add(C())
            session.add(D())
            session.add(E())
        session.commit()
        for i in range(10):
            parent = Parent(
                a_id=i * 10 + 1,
                b_id=i * 10 + 1,
                c_id=i * 10 + 2,
                d_id=i * 10 + 3,
                e_id=i * 10 + 4,
            )
            session.add(parent)
        session.commit()

    return A, B, C, D, E, Parent


@pytest.mark.benchmark
def test_load_many_relationships(
    benchmark: BenchmarkFixture, populated_tables, sessionmaker, mocker
):
    A, B, C, D, E, Parent = populated_tables

    mapper = strawberry_sqlalchemy_mapper.StrawberrySQLAlchemyMapper()

    @mapper.type(Parent)
    class StrawberryParent:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        @staticmethod
        async def parents(info: Info) -> List[StrawberryParent]:
            return info.context["session"].scalars(sa.select(Parent)).all()

    mapper.finalize()

    schema = strawberry.Schema(Query)

    # Now that we've seeded the database, let's add some delay to simulate network lag
    # to the database.
    old_execute_internal = orm.Session._execute_internal
    mocker.patch.object(orm.Session, "_execute_internal", autospec=True)

    def sleep_then_execute(self, *args, **kwargs):
        time.sleep(0.01)
        return old_execute_internal(self, *args, **kwargs)

    orm.Session._execute_internal.side_effect = sleep_then_execute

    async def execute():
        with sessionmaker() as session:
            # Notice how we use a sync session but call Strawberry's async execute.
            # This is not an ideal combination, but it's certainly a common one that
            # we need to support efficiently.
            result = await schema.execute(
                """
                query {
                    parents {
                        a { id },
                        b { id },
                        c { id },
                        d { id },
                        e { id },
                    }
                }
                """,
                context_value={
                    "session": session,
                    "sqlalchemy_loader": strawberry_sqlalchemy_mapper.StrawberrySQLAlchemyLoader(
                        bind=session
                    ),
                },
            )
            assert not result.errors
            assert len(result.data["parents"]) == 10

    benchmark(asyncio.run, execute())


@pytest.mark.benchmark
def test_load_many_relationships_async(
    benchmark: BenchmarkFixture, populated_tables, async_sessionmaker, mocker
):
    A, B, C, D, E, Parent = populated_tables

    mapper = strawberry_sqlalchemy_mapper.StrawberrySQLAlchemyMapper()

    @mapper.type(Parent)
    class StrawberryParent:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        @staticmethod
        async def parents(info: Info) -> List[StrawberryParent]:
            async with info.context["async_sessionmaker"]() as session:
                return (await session.scalars(sa.select(Parent))).all()

    mapper.finalize()

    schema = strawberry.Schema(Query)

    # Now that we've seeded the database, let's add some delay to simulate network lag
    # to the database. We can add this lag into the
    old_scalars = AsyncSession.scalars
    mocker.patch.object(AsyncSession, "scalars", autospec=True)

    async def sleep_then_scalars(self, *args, **kwargs):
        await asyncio.sleep(0.01)
        return await old_scalars(self, *args, **kwargs)

    mock = AsyncMock()
    mock.side_effect = sleep_then_scalars
    AsyncSession.scalars.side_effect = mock

    async def execute():
        # Notice how we use a sync session but call Strawberry's async execute.
        # This is not an ideal combination, but it's certainly a common one that
        # we need to support efficiently.
        result = await schema.execute(
            """
            query {
                parents {
                    a { id },
                    b { id },
                    c { id },
                    d { id },
                    e { id },
                }
            }
            """,
            context_value={
                "async_sessionmaker": async_sessionmaker,
                "sqlalchemy_loader": strawberry_sqlalchemy_mapper.StrawberrySQLAlchemyLoader(
                    async_bind_factory=async_sessionmaker
                ),
            },
        )
        assert not result.errors
        assert len(result.data["parents"]) == 10

    benchmark(asyncio.run, execute())
