import textwrap
from typing import List

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String, select
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader
from strawberry_sqlalchemy_mapper.exc import UnsupportedAssociationProxyTarget


@pytest.fixture
def employee_and_department_tables_with_wrong_association_proxy(base):
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


def test_relationships_schema_with_association_proxy_should_raise_UnsupportedAssociationProxyTarget(
    employee_and_department_tables_with_wrong_association_proxy, mapper
):

    EmployeeModel, DepartmentModel = (
        employee_and_department_tables_with_wrong_association_proxy
    )

    @mapper.type(EmployeeModel)
    class Employee:
        __exclude__ = ["password_hash"]

    with pytest.raises(UnsupportedAssociationProxyTarget) as exc_info:

        @mapper.type(DepartmentModel)
        class Department:
            pass

    assert (
        "Association proxy `employee_names` is expected to be of form association_proxy(relationship_name, other relationship name)"
        in str(exc_info.value)
    )


def test_relationships_schema_with_association_proxy(
    building_department_employee_tables_with_association_proxy_and_normal_relationship,
    mapper,
):

    BuildingModel, DepartmentModel, EmployeeModel = (
        building_department_employee_tables_with_association_proxy_and_normal_relationship
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
        def buildings(self) -> Building: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = '''
type Building {
  id: Int!
  name: String!
  departments: DepartmentConnection!
  employees: EmployeeConnection!
}

type Department {
  id: Int!
  name: String!
  buildingId: Int
  building: Building
  employees: EmployeeConnection!
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
    '''
    assert str(schema) == textwrap.dedent(expected).strip()


def create_test_data(
    session,
    building_department_employee_tables_with_association_proxy_and_normal_relationship,
):
    BuildingModel, DepartmentModel, EmployeeModel = (
        building_department_employee_tables_with_association_proxy_and_normal_relationship
    )

    building = BuildingModel(id=1, name="Main Office")
    department1 = DepartmentModel(id=2, name="Engineering")
    department2 = DepartmentModel(id=3, name="Human Resources")
    employee1 = EmployeeModel(id=4, name="Alice")
    employee2 = EmployeeModel(id=5, name="Bob")

    # Establish relationships
    department1.employees.extend([employee1])
    department2.employees.extend([employee2])
    building.departments.extend([department1, department2])

    session.add_all([building, department1, department2, employee1, employee2])
    session.commit()
    return building, department1, department2, employee1, employee2


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


async def test_query_with_association_proxy_schema(
    base,
    engine,
    sessionmaker,
    building_department_employee_tables_with_association_proxy_and_normal_relationship,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = (
        building_department_employee_tables_with_association_proxy_and_normal_relationship
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

    building, department1, department2, employee1, employee2 = create_test_data(
        session,
        building_department_employee_tables_with_association_proxy_and_normal_relationship,
    )

    query = query_to_test_association_proxy()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    session.close()

    assert result.errors is None
    assert result.data == {
        "buildings": [
            {
                "id": building.id,
                "name": building.name,
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
            }
        ]
    }


async def test_query_with_association_proxy_schema_with_empty_database(
    base,
    engine,
    sessionmaker,
    building_department_employee_tables_with_association_proxy_and_normal_relationship,
    mapper,
):
    base.metadata.create_all(engine)
    session = sessionmaker()

    BuildingModel, DepartmentModel, EmployeeModel = (
        building_department_employee_tables_with_association_proxy_and_normal_relationship
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

    query = query_to_test_association_proxy()

    result = await schema.execute(
        query,
        context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)},
    )
    session.close()

    assert result.errors is None
    assert result.data == {"buildings": []}


## TODO
# test with keysetConnection
