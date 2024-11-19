from typing import Any, List

import pytest
import strawberry
from sqlalchemy import Column, Integer, String, Table, ForeignKey, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import sessionmaker, relationship, Session
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


@pytest.fixture
def secondary_tables(base):
    EmployeeDepartmentJoinTable = Table(
        "employee_department_join_table",
        base.metadata,
        Column("employee_id", ForeignKey("employee.id"), primary_key=True),
        Column("department_id", ForeignKey(
            "department.id"), primary_key=True),
    )

    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        role = Column(String, nullable=False)
        department = relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
            uselist=False
        )

    return Employee, Department


async def test_query_with_secondary_table(
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
        employees: relay.ListConnection[Employee] = connection(
            sessionmaker=async_sessionmaker)

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """\
        query {
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
                                    employees {
                                        id
                                        name
                                        role
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
        department = DepartmentModel(name="Department Test")
        e1 = EmployeeModel(name="John", role="Developer")
        e2 = EmployeeModel(name="Bill", role="Doctor")
        e3 = EmployeeModel(name="Maria", role="Teacher")
        e1.department.append(department)
        session.add_all([department, e1, e2, e3])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        # breakpoint()
        assert result.data == {
            'employees': {
                'edges': [
                    {
                        'node': {
                            'id': 1,
                            'name': 'John',
                            'role': 'Developer',
                            'department': {
                                    'edges': [
                                        {
                                            'node': {
                                                'id': 1,
                                                'name': 'Department Test',
                                                'employees': {
                                                    'id': 1,
                                                    'name': 'John',
                                                    'role': 'Developer'
                                                }
                                            }
                                        }
                                    ]
                            }
                        }
                    },
                    {
                        'node': {
                            'id': 2,
                            'name': 'Bill',
                            'role': 'Doctor',
                            'department': {
                                    'edges': []
                            }
                        }
                    },
                    {
                        'node': {
                            'id': 3,
                            'name': 'Maria',
                            'role': 'Teacher',
                            'department': {
                                    'edges': []
                            }
                        }
                    }
                ]
            }
        }


async def test_query_with_secondary_table_without_list_connection(
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
        @strawberry.field
        async def employees(self) -> List[Employee]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(EmployeeModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """\
        query {
            employees {
                id
                name
                role
                department {
                    edges {
                        node {
                            id
                            name
                            employees {
                                id
                                name
                                role
                            }
                        }
                    }
                }
            }
        }
    """

    # Create test data
    async with async_sessionmaker(expire_on_commit=False) as session:
        department = DepartmentModel(name="Department Test")
        e1 = EmployeeModel(name="John", role="Developer")
        e2 = EmployeeModel(name="Bill", role="Doctor")
        e3 = EmployeeModel(name="Maria", role="Teacher")
        e1.department.append(department)
        session.add_all([department, e1, e2, e3])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        # breakpoint()
        assert result.data == {
                'employees': [
                    {
                        'id': 1,
                        'name': 'John',
                        'role': 'Developer',
                        'department': {
                            'edges': [
                                {
                                    'node': {
                                        'id': 1,
                                        'name': 'Department Test',
                                        'employees': {
                                            'id': 1,
                                            'name': 'John',
                                            'role': 'Developer'
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    {
                        'id': 2,
                        'name': 'Bill',
                        'role': 'Doctor',
                        'department': {
                            'edges': []
                        }
                    },
                    {
                        'id': 3,
                        'name': 'Maria',
                        'role': 'Teacher',
                        'department': {
                            'edges': []
                        }
                    }
                ]
            }


async def test_query_with_secondary_table_with_values_with_different_ids(
    secondary_tables,
    base,
    async_engine,
    async_sessionmaker
):
    # This test ensures that the `keys` variable used inside `StrawberrySQLAlchemyLoader.loader_for` does not incorrectly repeat values (e.g., ((1, 1), (4, 4))) as observed in some test scenarios.

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
        @strawberry.field
        async def employees(self) -> List[Employee]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(EmployeeModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """\
        query {
            employees {
                id
                name
                role
                department {
                    edges {
                        node {
                            id
                            name
                            employees {
                                id
                                name
                                role
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
        e1.department.append(department2)
        e2.department.append(department1)
        session.add_all([department1, department2, e1, e2, e3])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        # breakpoint()
        assert result.data == {
                'employees': [
                    {
                        'id': 1,
                        'name': 'John',
                        'role': 'Developer',
                        'department': {
                            'edges': [
                                {
                                    'node': {
                                        'id': 1,
                                        'name': 'Department Test',
                                        'employees': {
                                            'id': 1,
                                            'name': 'John',
                                            'role': 'Developer'
                                        }
                                    }
                                }
                            ]
                        }
                    },
                    {
                        'id': 2,
                        'name': 'Bill',
                        'role': 'Doctor',
                        'department': {
                            'edges': []
                        }
                    },
                    {
                        'id': 3,
                        'name': 'Maria',
                        'role': 'Teacher',
                        'department': {
                            'edges': []
                        }
                    }
                ]
            }




# TODO
# test with different ids
# add a test on Loader to see
# Add test with query by secondary id