import textwrap
from typing import List

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String, select
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from strawberry import relay
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader, connection
from strawberry_sqlalchemy_mapper.exc import UnsupportedAssociationProxyTarget
from strawberry_sqlalchemy_mapper.relay import KeysetConnection

# === TABLES FIXTURES ===


@pytest.fixture
def tables_with_wrong_association_proxy(base):
    class Department(base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship("Employee", back_populates="department")
        employee_names = association_proxy("employees", "name")

    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("department.id"))
        department = relationship("Department", back_populates="employees")

    return Employee, Department


@pytest.fixture
def tables_with_association_proxy(
    base,
):
    class Building(base):
        __tablename__ = "buildings"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)

        departments = relationship("Department", back_populates="building")
        employees = association_proxy("departments", "employees")

    class Department(base):
        __tablename__ = "departments"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        building_id = Column(Integer, ForeignKey("buildings.id"))

        building = relationship("Building", back_populates="departments")
        employees = relationship("Employee", back_populates="department")

    class Employee(base):
        __tablename__ = "employees"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("departments.id"))

        department = relationship("Department", back_populates="employees")

    return Building, Department, Employee


@pytest.fixture
def tables_with_association_proxy_and_nullable_relationship(
    base,
):
    class Building(base):
        __tablename__ = "buildings"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)

        department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
        department = relationship(
            "Department",
            back_populates="building",
            foreign_keys=[department_id],
            uselist=False,
        )

        employees = association_proxy("department", "employees")

    class Department(base):
        __tablename__ = "departments"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)

        building = relationship(
            "Building",
            back_populates="department",
            foreign_keys=[Building.department_id],
        )

        employees = relationship("Employee", back_populates="department")

    class Employee(base):
        __tablename__ = "employees"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("departments.id"))

        department = relationship("Department", back_populates="employees")

    return Building, Department, Employee


# === TESTS ===


def test_relationships_schema_with_association_proxy_should_raise_UnsupportedAssociationProxyTarget(
    tables_with_wrong_association_proxy, mapper
):
    EmployeeModel, DepartmentModel = tables_with_wrong_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        __exclude__ = ["password_hash"]

    with pytest.raises(UnsupportedAssociationProxyTarget) as exc_info:

        @mapper.type(DepartmentModel)
        class Department:
            pass

    assert (
        "Association proxy `employee_names` is expected to be of form association_proxy"
        "(relationship_name, other relationship name). Ensure it matches the expected form or add "
        "this association proxy to __exclude__" in str(exc_info.value)
    )


def test_schema_with_assoc_proxy_should_not_raise_exception_if_target_excluded(
    tables_with_wrong_association_proxy, mapper
):
    EmployeeModel, DepartmentModel = tables_with_wrong_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        __exclude__ = ["password_hash", "employee_names"]

    @strawberry.type
    class Query:
        @strawberry.field
        def departments(self) -> Department: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = get_schema_should_not_raise_UnsupportedAssociation_if_excluded_expected_shema()
    assert str(schema) == textwrap.dedent(expected).strip()


def test_relationships_schema_with_association_proxy(
    tables_with_association_proxy,
    mapper,
):
    BuildingModel, DepartmentModel, EmployeeModel = tables_with_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @mapper.type(BuildingModel)
    class Building:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def buildings(self) -> Building: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = get_test_relationships_schema_with_association_proxy_expected_schema()
    assert str(schema) == textwrap.dedent(expected).strip()


async def test_query_with_association_proxy_schema(
    base,
    engine,
    sessionmaker,
    tables_with_association_proxy,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = tables_with_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @mapper.type(BuildingModel)
    class Building:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def buildings(self) -> List[Building]:
            result = session.scalars(select(BuildingModel))
            return result.all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    test_data = create_test_data(
        session,
        tables_with_association_proxy,
    )

    query = query_to_test_association_proxy()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    session.close()

    assert result.errors is None
    assert result.data == get_test_query_with_association_proxy_schema_expected_result(*test_data)


async def test_query_with_association_proxy_schema_with_empty_database(
    base,
    engine,
    sessionmaker,
    tables_with_association_proxy,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = tables_with_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @mapper.type(BuildingModel)
    class Building:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def buildings(self) -> List[Building]:
            result = session.scalars(select(BuildingModel))
            return result.all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    query = query_to_test_association_proxy()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    session.close()

    assert result.errors is None
    assert result.data == {"buildings": []}


async def test_query_with_association_proxy_schema_keyset_connection(
    base,
    engine,
    sessionmaker,
    tables_with_association_proxy,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = tables_with_association_proxy

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @mapper.type(BuildingModel)
    class Building(relay.Node):
        id: relay.NodeID[int]
        name: str

    @strawberry.type
    class Query:
        buildings: KeysetConnection[Building] = connection(
            sessionmaker=sessionmaker,
            keyset=(BuildingModel.name,),
        )

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    test_data = create_test_data(
        session,
        tables_with_association_proxy,
    )

    query = get_test_query_with_association_proxy_schema_keyset_connection_query()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )

    assert result.errors is None
    assert (
        result.data
        == get_test_query_with_association_proxy_schema_keyset_connection_expected_result(
            *test_data
        )
    )

    result = await schema.execute(
        query,
        {"first": 1},
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    assert result.errors is None
    assert (
        result.data
        == get_test_query_with_association_proxy_keyset_connection_expected_result_with_first(
            *test_data
        )
    )


async def test_query_with_association_proxy_schema_with_nullable_relationship(
    base,
    engine,
    sessionmaker,
    tables_with_association_proxy_and_nullable_relationship,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = (
        tables_with_association_proxy_and_nullable_relationship
    )

    @mapper.type(EmployeeModel)
    class Employee:
        pass

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @mapper.type(BuildingModel)
    class Building:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def buildings(self) -> List[Building]:
            result = session.scalars(select(BuildingModel))
            return result.all()

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    test_data = create_test_data_with_nullable_relationship(
        session,
        tables_with_association_proxy_and_nullable_relationship,
    )

    query = query_to_test_association_proxy()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    session.close()

    assert result.errors is None
    assert (
        result.data
        == get_test_query_with_association_proxy_schema_with_nullable_relationship_expected_result(
            *test_data
        )
    )


# === HELPERS ===


def get_schema_should_not_raise_UnsupportedAssociation_if_excluded_expected_shema():
    return '''
    type Department {
      id: Int!
      name: String!
      employees(first: Int = null, after: String = null, last: Int = null, before: String = null): EmployeeConnection!
    }

    type Employee {
      id: Int!
      name: String!
      departmentId: Int
      department: Department
    }

    type EmployeeConnection {
      """Pagination data for this connection"""
      pageInfo: PageInfo!
      edges: [EmployeeEdge!]!
    }

    type EmployeeEdge {
      """A cursor for use in pagination"""
      cursor: String!

      """The item at the end of the edge"""
      node: Employee!
    }

    """Information to aid in pagination."""
    type PageInfo {
      """When paginating forwards, are there more items?"""
      hasNextPage: Boolean!

      """When paginating backwards, are there more items?"""
      hasPreviousPage: Boolean!

      """When paginating backwards, the cursor to continue."""
      startCursor: String

      """When paginating forwards, the cursor to continue."""
      endCursor: String
    }

    type Query {
      departments: Department!
    }
    '''  # noqa: E501 - long lines needed for exact string matches


def get_test_relationships_schema_with_association_proxy_expected_schema():
    return '''
type Building {
  id: Int!
  name: String!
  departments(first: Int = null, after: String = null, last: Int = null, before: String = null): DepartmentConnection!
  employees: EmployeeConnection!
}

type Department {
  id: Int!
  name: String!
  buildingId: Int
  building: Building
  employees(first: Int = null, after: String = null, last: Int = null, before: String = null): EmployeeConnection!
}

type DepartmentConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [DepartmentEdge!]!
}

type DepartmentEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: Department!
}

type Employee {
  id: Int!
  name: String!
  departmentId: Int
  department: Department
}

type EmployeeConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [EmployeeEdge!]!
}

type EmployeeEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: Employee!
}

"""Information to aid in pagination."""
type PageInfo {
  """When paginating forwards, are there more items?"""
  hasNextPage: Boolean!

  """When paginating backwards, are there more items?"""
  hasPreviousPage: Boolean!

  """When paginating backwards, the cursor to continue."""
  startCursor: String

  """When paginating forwards, the cursor to continue."""
  endCursor: String
}

type Query {
  buildings: Building!
}
    '''  # noqa: E501 - long lines needed for exact string matches


def create_test_data(
    session,
    building_department_employee_tables,
):
    BuildingModel, DepartmentModel, EmployeeModel = building_department_employee_tables

    building1 = BuildingModel(id=1, name="Main Office")
    building2 = BuildingModel(id=6, name="New Office")
    department1 = DepartmentModel(id=2, name="Engineering")
    department2 = DepartmentModel(id=3, name="Human Resources")
    employee1 = EmployeeModel(id=4, name="Alice")
    employee2 = EmployeeModel(id=5, name="Bob")

    # Establish relationships
    department1.employees.extend([employee1])
    department2.employees.extend([employee2])
    building1.departments.extend([department1, department2])

    session.add_all([building1, building2, department1, department2, employee1, employee2])
    session.commit()
    return [building1, building2, department1, department2, employee1, employee2]


def query_to_test_association_proxy():
    return """
    query {
      buildings {
        id
        name
        employees {
          pageInfo {
            hasNextPage
            hasPreviousPage
            startCursor
            endCursor
          }
          edges {
            cursor
            node {
              id
              name
              department {
                id
                name
              }
            }
          }
        }
      }
    }
    """


def get_test_query_with_association_proxy_schema_expected_result(
    building1, building2, department1, department2, employee1, employee2
):
    return {
        "buildings": [
            {
                "id": building1.id,
                "name": building1.name,
                "employees": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                        "endCursor": "YXJyYXljb25uZWN0aW9uOjE=",
                    },
                    "edges": [
                        {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                            "node": {
                                "id": employee1.id,
                                "name": employee1.name,
                                "department": {
                                    "id": department1.id,
                                    "name": department1.name,
                                },
                            },
                        },
                        {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjE=",
                            "node": {
                                "id": employee2.id,
                                "name": employee2.name,
                                "department": {
                                    "id": department2.id,
                                    "name": department2.name,
                                },
                            },
                        },
                    ],
                },
            },
            {
                "id": building2.id,
                "name": building2.name,
                "employees": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": None,
                        "endCursor": None,
                    },
                    "edges": [],
                },
            },
        ]
    }


def get_test_query_with_association_proxy_schema_keyset_connection_query():
    return """
    query Buildings($first: Int, $after: String) {
      buildings(first: $first, after: $after) {
        pageInfo {
          hasNextPage
          hasPreviousPage
          startCursor
          endCursor
        }
        edges {
          cursor
          node {
            id
            name
            employees {
              pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
              }
              edges {
                cursor
                node {
                  id
                  name
                  department {
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


def get_test_query_with_association_proxy_schema_keyset_connection_expected_result(
    building1, building2, department1, department2, employee1, employee2
):
    return {
        "buildings": {
            "pageInfo": {
                "hasNextPage": False,
                "hasPreviousPage": False,
                "startCursor": f">s:{building1.name}",
                "endCursor": f">s:{building2.name}",
            },
            "edges": [
                {
                    "cursor": f">s:{building1.name}",
                    "node": {
                        "id": "QnVpbGRpbmc6MQ==",
                        "name": building1.name,
                        "employees": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "hasPreviousPage": False,
                                "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                                "endCursor": "YXJyYXljb25uZWN0aW9uOjE=",
                            },
                            "edges": [
                                {
                                    "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                                    "node": {
                                        "id": employee1.id,
                                        "name": employee1.name,
                                        "department": {
                                            "id": department1.id,
                                            "name": department1.name,
                                        },
                                    },
                                },
                                {
                                    "cursor": "YXJyYXljb25uZWN0aW9uOjE=",
                                    "node": {
                                        "id": employee2.id,
                                        "name": employee2.name,
                                        "department": {
                                            "id": department2.id,
                                            "name": department2.name,
                                        },
                                    },
                                },
                            ],
                        },
                    },
                },
                {
                    "cursor": f">s:{building2.name}",
                    "node": {
                        "id": "QnVpbGRpbmc6Ng==",
                        "name": building2.name,
                        "employees": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "hasPreviousPage": False,
                                "startCursor": None,
                                "endCursor": None,
                            },
                            "edges": [],
                        },
                    },
                },
            ],
        }
    }


def get_test_query_with_association_proxy_keyset_connection_expected_result_with_first(
    building1, building2, department1, department2, employee1, employee2
):
    return {
        "buildings": {
            "pageInfo": {
                "hasNextPage": True,
                "hasPreviousPage": False,
                "startCursor": f">s:{building1.name}",
                "endCursor": f">s:{building1.name}",
            },
            "edges": [
                {
                    "cursor": f">s:{building1.name}",
                    "node": {
                        "id": "QnVpbGRpbmc6MQ==",
                        "name": building1.name,
                        "employees": {
                            "pageInfo": {
                                "hasNextPage": False,
                                "hasPreviousPage": False,
                                "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                                "endCursor": "YXJyYXljb25uZWN0aW9uOjE=",
                            },
                            "edges": [
                                {
                                    "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                                    "node": {
                                        "id": employee1.id,
                                        "name": employee1.name,
                                        "department": {
                                            "id": department1.id,
                                            "name": department1.name,
                                        },
                                    },
                                },
                                {
                                    "cursor": "YXJyYXljb25uZWN0aW9uOjE=",
                                    "node": {
                                        "id": employee2.id,
                                        "name": employee2.name,
                                        "department": {
                                            "id": department2.id,
                                            "name": department2.name,
                                        },
                                    },
                                },
                            ],
                        },
                    },
                }
            ],
        }
    }


def create_test_data_with_nullable_relationship(
    session,
    building_department_employee_tables,
):
    BuildingModel, DepartmentModel, EmployeeModel = building_department_employee_tables

    building1 = BuildingModel(id=1, name="Main Office")
    building2 = BuildingModel(id=6, name="New Office")
    department1 = DepartmentModel(id=2, name="Engineering")
    department2 = DepartmentModel(id=3, name="Human Resources")
    employee1 = EmployeeModel(id=4, name="Alice")
    employee2 = EmployeeModel(id=5, name="Bob")

    # Establish relationships
    department1.employees.extend([employee1])
    department2.employees.extend([employee2])
    building2.department = department2

    session.add_all([building1, building2, department1, department2, employee1, employee2])
    session.commit()
    return building1, building2, department1, department2, employee1, employee2


def get_test_query_with_association_proxy_schema_with_nullable_relationship_expected_result(
    building1, building2, department1, department2, employee1, employee2
):
    return {
        "buildings": [
            {
                "id": building1.id,
                "name": building1.name,
                "employees": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": None,
                        "endCursor": None,
                    },
                    "edges": [],
                },
            },
            {
                "id": building2.id,
                "name": building2.name,
                "employees": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "hasPreviousPage": False,
                        "startCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                        "endCursor": "YXJyYXljb25uZWN0aW9uOjA=",
                    },
                    "edges": [
                        {
                            "cursor": "YXJyYXljb25uZWN0aW9uOjA=",
                            "node": {
                                "id": employee2.id,
                                "name": employee2.name,
                                "department": {
                                    "id": department2.id,
                                    "name": department2.name,
                                },
                            },
                        }
                    ],
                },
            },
        ]
    }
