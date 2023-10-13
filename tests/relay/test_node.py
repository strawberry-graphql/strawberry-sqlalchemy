from typing import Any, Optional

import pytest
import strawberry
from sqlalchemy import Column, Integer, String
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import sessionmaker
from strawberry import relay
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper, node


@pytest.fixture
def fruit_table(base: Any):
    class Fruit(base):
        __tablename__ = "fruit"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String(50), nullable=False)
        color = Column(String(50), nullable=False)

    return Fruit


def test_node(
    base: Any,
    engine: Engine,
    sessionmaker: sessionmaker,
    fruit_table,
):
    base.metadata.create_all(engine)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]

    @strawberry.type
    class Query:
        fruit: Fruit = node(sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruit($id: GlobalID!) {
      fruit(id: $id) {
        id
        name
        color
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")

        session.add_all([f1, f2, f3])
        session.commit()

        for f in [f1, f2, f3]:
            result = schema.execute_sync(query, {"id": relay.to_base64("Fruit", f.id)})
            assert result.errors is None
            assert result.data == {
                "fruit": {
                    "id": relay.to_base64("Fruit", f.id),
                    "name": f.name,
                    "color": f.color,
                },
            }


@pytest.mark.asyncio
async def test_node_async(
    base: Any,
    async_engine: AsyncEngine,
    async_sessionmaker: async_sessionmaker,
    fruit_table,
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]

    @strawberry.type
    class Query:
        fruit: Fruit = node(sessionmaker=async_sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruit($id: GlobalID!) {
      fruit(id: $id) {
        id
        name
        color
      }
    }
    """

    async with async_sessionmaker(expire_on_commit=False) as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        await session.commit()

        session.add_all([f1, f2, f3])
        session.commit()

        for f in [f1, f2, f3]:
            result = await schema.execute(query, {"id": relay.to_base64("Fruit", f.id)})
            assert result.errors is None
            assert result.data == {
                "fruit": {
                    "id": relay.to_base64("Fruit", f.id),
                    "name": f.name,
                    "color": f.color,
                },
            }


def test_node_none(
    base: Any,
    engine: Engine,
    sessionmaker: sessionmaker,
    fruit_table,
):
    base.metadata.create_all(engine)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]

    @strawberry.type
    class Query:
        fruit: Optional[Fruit] = node(sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruit($id: GlobalID!) {
      fruit(id: $id) {
        id
        name
        color
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")

        session.add_all([f1, f2, f3])
        session.commit()

        result = schema.execute_sync(query, {"id": relay.to_base64("Fruit", -1)})
        assert result.errors is None
        assert result.data == {
            "fruit": None,
        }


def test_nodes(
    base: Any,
    engine: Engine,
    sessionmaker: sessionmaker,
    fruit_table,
):
    base.metadata.create_all(engine)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]

    @strawberry.type
    class Query:
        fruits: list[Fruit] = node(sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruit($ids: [GlobalID!]!) {
      fruits(ids: $ids) {
        id
        name
        color
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")

        session.add_all([f1, f2, f3])
        session.commit()

        result = schema.execute_sync(
            query,
            {
                "ids": [
                    relay.to_base64("Fruit", f1.id),
                    relay.to_base64("Fruit", f2.id),
                ]
            },
        )
        assert result.errors is None
        expected_fruits = [f1, f2]
        assert result.data == {
            "fruits": [
                {
                    "id": relay.to_base64("Fruit", f.id),
                    "name": f.name,
                    "color": f.color,
                }
                for f in expected_fruits
            ],
        }


@pytest.mark.asyncio
async def test_nodes_async(
    base: Any,
    async_engine: AsyncEngine,
    async_sessionmaker: async_sessionmaker,
    fruit_table,
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]

    @strawberry.type
    class Query:
        fruits: list[Fruit] = node(sessionmaker=async_sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruit($ids: [GlobalID!]!) {
      fruits(ids: $ids) {
        id
        name
        color
      }
    }
    """

    async with async_sessionmaker(expire_on_commit=False) as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        await session.commit()

        session.add_all([f1, f2, f3])
        session.commit()

        result = await schema.execute(
            query,
            {
                "ids": [
                    relay.to_base64("Fruit", f1.id),
                    relay.to_base64("Fruit", f2.id),
                ]
            },
        )
        assert result.errors is None
        expected_fruits = [f1, f2]
        assert result.data == {
            "fruits": [
                {
                    "id": relay.to_base64("Fruit", f.id),
                    "name": f.name,
                    "color": f.color,
                }
                for f in expected_fruits
            ],
        }
