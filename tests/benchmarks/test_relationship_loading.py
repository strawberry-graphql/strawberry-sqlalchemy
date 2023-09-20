from typing import List

import pytest
import sqlalchemy as sa
import sqlalchemy.orm
import strawberry
import strawberry_sqlalchemy_mapper
from asgiref.sync import async_to_sync
from pytest_codspeed.plugin import BenchmarkFixture
from strawberry.types import Info


@pytest.mark.benchmark
def test_load_many_relationships(
    benchmark: BenchmarkFixture, engine, base, sessionmaker
):
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

    mapper = strawberry_sqlalchemy_mapper.StrawberrySQLAlchemyMapper()

    @mapper.type(Parent)
    class StrawberryParent:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        @staticmethod
        async def parents(info: Info) -> List[StrawberryParent]:
            return info.context["session"].execute(sa.select(Parent)).all()

    mapper.finalize()
    base.metadata.create_all(engine)

    schema = strawberry.Schema(Query)

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

    async def execute():
        with sessionmaker() as session:
            # Notice how we use a sync session but call Strawberry's async execute.
            # This is not an ideal combination, but it's certainly a common one that
            # we need to support efficiently.
            await schema.execute(
                """
                query {
                    parents {
                        a { edges { node { id } } },
                        b { edges { node { id } } },
                        c { edges { node { id } } },
                        d { edges { node { id } } },
                        e { edges { node { id } } },
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

    benchmark(async_to_sync(execute))
