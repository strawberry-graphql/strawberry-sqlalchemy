from typing import List

import pytest
import strawberry
from sqlalchemy import select
from strawberry import relay
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper, connection, StrawberrySQLAlchemyLoader


@pytest.fixture
def default_query_secondary_table():
    return """
        query {
            departments {
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
    """


@pytest.mark.asyncio
async def test_query_with_secondary_table_with_values_list_without_list_connection(
    secondary_tables,
    base,
    async_engine,
    async_sessionmaker,
    default_query_secondary_table
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
        async def departments(self) -> List[Department]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(DepartmentModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)


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

        result = await schema.execute(default_query_secondary_table, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        assert result.data == {
            "departments": [
                {
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
                },
                {
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
            ]
        }


@pytest.mark.asyncio
async def test_query_with_secondary_table_with_values_list_with_foreign_key_different_than_id(
    secondary_tables_with_another_foreign_key,
    base,
    async_engine,
    async_sessionmaker,
    default_query_secondary_table
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel = secondary_tables_with_another_foreign_key

    @mapper.type(DepartmentModel)
    class Department():
        pass

    @mapper.type(EmployeeModel)
    class Employee():
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def departments(self) -> List[Department]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(DepartmentModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

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

        result = await schema.execute(default_query_secondary_table, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        assert result.data == {
            "departments": [
                {
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
                },
                {
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
            ]
        }


@pytest.mark.asyncio
async def test_query_with_secondary_tables_with_more_than_2_colluns_values_list(
    secondary_tables_with_more_secondary_tables,
    base,
    async_engine,
    async_sessionmaker
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel, BuildingModel = secondary_tables_with_more_secondary_tables

    @mapper.type(DepartmentModel)
    class Department():
        pass

    @mapper.type(EmployeeModel)
    class Employee():
        pass

    @mapper.type(BuildingModel)
    class Building():
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def departments(self) -> List[Department]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(DepartmentModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """
        query {
            departments {
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
                            },
                            building {
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
    """

    # Create test data
    async with async_sessionmaker(expire_on_commit=False) as session:
        building = BuildingModel(id=2, name="Building 1")
        department1 = DepartmentModel(id=10, name="Department Test 1")
        department2 = DepartmentModel(id=3, name="Department Test 2")
        e1 = EmployeeModel(id=1, name="John", role="Developer")
        e2 = EmployeeModel(id=5, name="Bill", role="Doctor")
        e3 = EmployeeModel(id=4, name="Maria", role="Teacher")
        department1.employees.append(e1)
        department1.employees.append(e2)
        department2.employees.append(e3)
        building.employees.append(e1)
        building.employees.append(e2)
        building.employees.append(e3)
        session.add_all([department1, department2, e1, e2, e3, building])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        assert result.data == {
            "departments": [
                {
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
                                    },
                                    "building": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "id": 2,
                                                    "name": "Building 1"
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
                                    },
                                    "building": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "id": 2,
                                                    "name": "Building 1"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                },
                {
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
                                    },
                                    "building": {
                                        "edges": [
                                            {
                                                "node": {
                                                    "id": 2,
                                                    "name": "Building 1"
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }


@pytest.mark.asyncio
async def test_query_with_secondary_table(
    secondary_tables_with_use_list_false,
    base,
    async_engine,
    async_sessionmaker
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel = secondary_tables_with_use_list_false

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

    query = """
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


@pytest.mark.asyncio
async def test_query_with_secondary_table_without_list_connection(
    secondary_tables_with_use_list_false,
    base,
    async_engine,
    async_sessionmaker
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel = secondary_tables_with_use_list_false

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

    query = """
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


@pytest.mark.asyncio
async def test_query_with_secondary_table_with_values_with_different_ids(
    secondary_tables_with_use_list_false,
    base,
    async_engine,
    async_sessionmaker
):
    # This test ensures that the `keys` variable used inside `StrawberrySQLAlchemyLoader.loader_for` does not incorrectly repeat values (e.g., ((1, 1), (4, 4))) as observed in some test scenarios.

    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel = secondary_tables_with_use_list_false

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

    query = """
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
        assert result.data == {
            'employees': [
                {
                    'id': 5,
                    'name': 'Bill',
                    'role': 'Doctor',
                    'department': {
                        'edges': [
                            {
                                'node': {
                                    'id': 10,
                                    'name': 'Department Test 1',
                                    'employees': {
                                        'id': 5,
                                        'name': 'Bill',
                                        'role': 'Doctor'
                                    }
                                }
                            }
                        ]
                    }
                },
                {
                    'id': 1,
                    'name': 'John',
                    'role': 'Developer',
                    'department': {
                        'edges': [
                            {
                                'node': {
                                    'id': 3,
                                    'name': 'Department Test 2',
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
                    'id': 4,
                    'name': 'Maria',
                    'role': 'Teacher',
                    'department': {
                        'edges': []
                    }
                }
            ]
        }


@pytest.mark.asyncio
async def test_query_with_secondary_table_with_values_list_and_normal_relationship(
    secondary_tables_with_normal_relationship,
    base,
    async_engine,
    async_sessionmaker
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    mapper = StrawberrySQLAlchemyMapper()
    EmployeeModel, DepartmentModel, BuildingModel = secondary_tables_with_normal_relationship

    @mapper.type(DepartmentModel)
    class Department():
        pass

    @mapper.type(EmployeeModel)
    class Employee():
        pass

    @mapper.type(BuildingModel)
    class Building():
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def departments(self) -> List[Department]:
            async with async_sessionmaker() as session:
                result = await session.execute(select(DepartmentModel))
                return result.scalars().all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = """
        query {
            departments {
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
                            },
                            building {
                                id
                                name
                            }
                        }
                    }          
                }
            }
        }
    """

    # Create test data
    async with async_sessionmaker(expire_on_commit=False) as session:
        building = BuildingModel(id=2, name="Building 1")
        department1 = DepartmentModel(id=10, name="Department Test 1")
        department2 = DepartmentModel(id=3, name="Department Test 2")
        e1 = EmployeeModel(id=1, name="John", role="Developer")
        e2 = EmployeeModel(id=5, name="Bill", role="Doctor")
        e3 = EmployeeModel(id=4, name="Maria", role="Teacher")
        department1.employees.append(e1)
        department1.employees.append(e2)
        department2.employees.append(e3)
        building.employees.append(e1)
        building.employees.append(e2)
        building.employees.append(e3)
        session.add_all([department1, department2, e1, e2, e3, building])
        await session.commit()

        result = await schema.execute(query, context_value={
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                async_bind_factory=async_sessionmaker
            )
        })
        assert result.errors is None
        assert result.data == {
            "departments": [
                {
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
                                    },
                                    "building": {
                                        "id": 2,
                                        "name": "Building 1"
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
                                    },
                                    "building": {
                                        "id": 2,
                                        "name": "Building 1"
                                    }
                                }
                            }
                        ]
                    }
                },
                {
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
                                    },
                                    "building": {
                                        "id": 2,
                                        "name": "Building 1"
                                    }
                                }
                            }
                        ]
                    }
                }
            ]
        }
