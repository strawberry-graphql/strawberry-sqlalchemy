from typing import Any

import pytest
import strawberry
from sqlalchemy import Column, Integer, String
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import sessionmaker
from strawberry import relay
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper, connection, StrawberrySQLAlchemyLoader
from strawberry_sqlalchemy_mapper.relay import KeysetConnection


@pytest.fixture
def fruit_table(base: Any):
    class Fruit(base):
        __tablename__ = "fruit"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String(50), nullable=False)
        color = Column(String(50), nullable=False)

    return Fruit


def test_query_empty(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query {
      fruits {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    result = schema.execute_sync(query)
    assert result.data == {"fruits": {"edges": []}}


def test_query(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query {
      fruits {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        session.commit()

        result = schema.execute_sync(query)
        assert result.errors is None
        expected_fruits = [f1, f2, f3]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


@pytest.mark.asyncio
async def test_query_async(
    base: Any,
    async_engine: AsyncEngine,
    async_sessionmaker,
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=async_sessionmaker
        )

    schema = strawberry.Schema(query=Query)

    query = """\
    query {
      fruits {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    async with async_sessionmaker(expire_on_commit=False) as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        await session.commit()

        result = await schema.execute(query)
        assert result.errors is None
        expected_fruits = [f1, f2, f3]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


@pytest.mark.asyncio
async def test_query_async_with_first(
    base: Any,
    async_engine: AsyncEngine,
    async_sessionmaker,
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=async_sessionmaker
        )

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int) {
      fruits(first: $first) {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    async with async_sessionmaker(expire_on_commit=False) as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        await session.commit()

        result = await schema.execute(query, {"first": 2})
        assert result.errors is None
        expected_fruits = [f1, f2]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


def test_query_with_first(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int) {
      fruits(first: $first) {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        session.commit()

        result = schema.execute_sync(query, {"first": 2})
        assert result.errors is None

        expected_fruits = [f1, f2]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


def test_query_with_first_and_after(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int $after: String) {
      fruits(first: $first after: $after) {
        edges {
          node {
            id
            name
            color
          }
        }
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
            query, {"first": 2, "after": relay.to_base64("arrayconnection", 0)}
        )
        assert result.errors is None

        expected_fruits = [f2, f3]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


def test_query_with_last(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($last: Int) {
      fruits(last: $last) {
        edges {
          node {
            id
            name
            color
          }
        }
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        session.add_all([f1, f2, f3])
        session.commit()

        result = schema.execute_sync(query, {"last": 2})
        assert result.errors is None

        expected_fruits = [f2, f3]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


def test_query_with_last_and_before(
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
        fruits: relay.ListConnection[Fruit] = connection(
            sessionmaker=sessionmaker)

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int $before: String) {
      fruits(first: $first before: $before) {
        edges {
          node {
            id
            name
            color
          }
        }
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
            query, {"first": 1, "before": relay.to_base64(
                "arrayconnection", 2)}
        )
        assert result.errors is None

        expected_fruits = [f2]
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "node": {
                            "id": relay.to_base64("Fruit", f.id),
                            "name": f.name,
                            "color": f.color,
                        }
                    }
                    for f in expected_fruits
                ]
            }
        }


def test_query_keyset(
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
        name: str

    @strawberry.type
    class Query:
        fruits: KeysetConnection[Fruit] = connection(
            sessionmaker=sessionmaker,
            keyset=(fruit_table.name,),
        )

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int, $after: String) {
      fruits(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          hasPreviousPage
          startCursor
          endCursor
        }
        edges {
          cursor
          node {
            name
          }
        }
      }
    }
    """

    with sessionmaker() as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        f4 = fruit_table(name="Mango", color="Orange")
        f5 = fruit_table(name="Grape", color="Purple")
        session.add_all([f1, f2, f3, f4, f5])
        session.commit()

        result = schema.execute_sync(query)
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Apple",
                        "node": {"name": "Apple"},
                    },
                    {
                        "cursor": ">s:Banana",
                        "node": {"name": "Banana"},
                    },
                    {
                        "cursor": ">s:Grape",
                        "node": {"name": "Grape"},
                    },
                    {
                        "cursor": ">s:Mango",
                        "node": {"name": "Mango"},
                    },
                    {
                        "cursor": ">s:Orange",
                        "node": {"name": "Orange"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Orange",
                    "hasNextPage": False,
                    "hasPreviousPage": False,
                    "startCursor": ">s:Apple",
                },
            }
        }

        result = schema.execute_sync(query, {"first": 2})
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Apple",
                        "node": {"name": "Apple"},
                    },
                    {
                        "cursor": ">s:Banana",
                        "node": {"name": "Banana"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Banana",
                    "hasNextPage": True,
                    "hasPreviousPage": False,
                    "startCursor": ">s:Apple",
                },
            }
        }

        result = schema.execute_sync(query, {"first": 2, "after": ">s:Banana"})
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Grape",
                        "node": {"name": "Grape"},
                    },
                    {
                        "cursor": ">s:Mango",
                        "node": {"name": "Mango"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Mango",
                    "hasNextPage": True,
                    "hasPreviousPage": True,
                    "startCursor": ">s:Grape",
                },
            }
        }


@pytest.mark.asyncio
async def test_query_keyset_async(
    base: Any,
    async_engine: AsyncEngine,
    sessionmaker: sessionmaker,
    async_sessionmaker,
    fruit_table,
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(fruit_table)
    class Fruit(relay.Node):
        id: relay.NodeID[int]
        name: str

    @strawberry.type
    class Query:
        fruits: KeysetConnection[Fruit] = connection(
            sessionmaker=async_sessionmaker,
            keyset=(fruit_table.name,),
        )

    schema = strawberry.Schema(query=Query)

    query = """\
    query Fruits($first: Int, $after: String) {
      fruits(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          hasPreviousPage
          startCursor
          endCursor
        }
        edges {
          cursor
          node {
            name
          }
        }
      }
    }
    """

    async with async_sessionmaker(expire_on_commit=False) as session:
        f1 = fruit_table(name="Banana", color="Yellow")
        f2 = fruit_table(name="Apple", color="Red")
        f3 = fruit_table(name="Orange", color="Orange")
        f4 = fruit_table(name="Mango", color="Orange")
        f5 = fruit_table(name="Grape", color="Purple")
        session.add_all([f1, f2, f3, f4, f5])
        await session.commit()

        result = await schema.execute(query)
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Apple",
                        "node": {"name": "Apple"},
                    },
                    {
                        "cursor": ">s:Banana",
                        "node": {"name": "Banana"},
                    },
                    {
                        "cursor": ">s:Grape",
                        "node": {"name": "Grape"},
                    },
                    {
                        "cursor": ">s:Mango",
                        "node": {"name": "Mango"},
                    },
                    {
                        "cursor": ">s:Orange",
                        "node": {"name": "Orange"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Orange",
                    "hasNextPage": False,
                    "hasPreviousPage": False,
                    "startCursor": ">s:Apple",
                },
            }
        }

        result = await schema.execute(query, {"first": 2})
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Apple",
                        "node": {"name": "Apple"},
                    },
                    {
                        "cursor": ">s:Banana",
                        "node": {"name": "Banana"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Banana",
                    "hasNextPage": True,
                    "hasPreviousPage": False,
                    "startCursor": ">s:Apple",
                },
            }
        }

        result = await schema.execute(query, {"first": 2, "after": ">s:Banana"})
        assert result.errors is None
        assert result.data == {
            "fruits": {
                "edges": [
                    {
                        "cursor": ">s:Grape",
                        "node": {"name": "Grape"},
                    },
                    {
                        "cursor": ">s:Mango",
                        "node": {"name": "Mango"},
                    },
                ],
                "pageInfo": {
                    "endCursor": ">s:Mango",
                    "hasNextPage": True,
                    "hasPreviousPage": True,
                    "startCursor": ">s:Grape",
                },
            }
        }


# TODO Investigate this test
@pytest.mark.skip("This test is currently failing because the Query with relay.ListConnection generates two DepartmentConnection, which violates the schema's expectations. After investigation, it appears this issue is related to the Relay implementation rather than the secondary table issue. We'll address this later. Additionally, note that the `result.data` may be incorrect in this test.")
@pytest.mark.asyncio
async def test_query_with_secondary_table_with_values_list(
    secondary_tables,
    base,
    async_engine,
    async_sessionmaker
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel = secondary_tables

    @mapper.type(DepartmentModel)
    class Department():
        pass

    @mapper.type(EmployeeModel)
    class Employee():
        pass

    @strawberry.type
    class Query:
        departments: relay.ListConnection[Department] = connection(
            sessionmaker=async_sessionmaker)

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """\
        query {
            departments {
                edges {
                    node {
                        id
                        name
                        employees {                  
                            edges {
                                node {
                                    id
                                    name
                                    role
                                    department {
                                        edges {
                                            node {
                                                id
                                                name
                                            }
                                        }
                                    }
                                }
                            }          
                        }
                    }
                }
            }
        }
    """

    # Create test data
    async with async_sessionmaker(expire_on_commit=False) as session:
        department1 = DepartmentModel(id=10, name="Department Test 1")
        department2 = DepartmentModel(id=3, name="Department Test 2")
        e1 = EmployeeModel(id=1, name="John", role="Developer")
        e2 = EmployeeModel(id=5, name="Bill", role="Doctor")
        e3 = EmployeeModel(id=4, name="Maria", role="Teacher")
        department1.employees.append(e1)
        department1.employees.append(e2)
        department2.employees.append(e3)
        session.add_all([department1, department2, e1, e2, e3])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        assert result.data == {
            "departments": {
                "edges": [
                    {
                        "node": {
                            "id": 10,
                            "name": "Department Test 1",
                            "employees": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": 5,
                                            "name": "Bill",
                                            "role": "Doctor",
                                            "department": {
                                                "edges": [
                                                    {
                                                        "node": {
                                                            "id": 10,
                                                            "name": "Department Test 1"
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    },
                                    {
                                        "node": {
                                            "id": 1,
                                            "name": "John",
                                            "role": "Developer",
                                            "department": {
                                                "edges": [
                                                    {
                                                        "node": {
                                                            "id": 10,
                                                            "name": "Department Test 1"
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    },
                    {
                        "node": {
                            "id": 3,
                            "name": "Department Test 2",
                            "employees": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": 4,
                                            "name": "Maria",
                                            "role": "Teacher",
                                            "department": {
                                                "edges": [
                                                    {
                                                        "node": {
                                                            "id": 3,
                                                            "name": "Department Test 2"
                                                        }
                                                    }
                                                ]
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
