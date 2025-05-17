"""
    conftest.py for strawberry_sqlalchemy_mapper.

    If you don't know what this is for, just leave it empty.
    Read more about conftest.py under:
    - https://docs.pytest.org/en/stable/fixture.html
    - https://docs.pytest.org/en/stable/writing_plugins.html
"""

import contextlib
import logging
import platform
import socket

import pytest
import sqlalchemy
from packaging import version
from sqlalchemy import orm
from sqlalchemy.engine import Engine
from sqlalchemy.ext import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper
from testing.postgresql import Postgresql, PostgresqlFactory

SQLA_VERSION = version.parse(sqlalchemy.__version__)
SQLA2 = SQLA_VERSION >= version.parse("2.0")


logging.basicConfig()
log = logging.getLogger("sqlalchemy.engine")
log.setLevel(logging.INFO)


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
    log.info("Skipping postgresql tests on Windows OS")
    SUPPORTED_DBS = []
else:
    SUPPORTED_DBS = ["postgresql"]  # TODO: Add sqlite and mysql.


@pytest.fixture(params=SUPPORTED_DBS)
def engine(request) -> Engine:
    if request.param == "postgresql":
        url = (
            request.getfixturevalue("postgresql")
            .url()
            .replace("postgresql://", "postgresql+psycopg2://")
        )
    else:
        raise ValueError("Unsupported database: %s", request.param)
    kwargs = {}
    if not SQLA2:
        kwargs["future"] = True
    engine = sqlalchemy.create_engine(url, **kwargs)
    return engine


@pytest.fixture
def sessionmaker(engine) -> orm.sessionmaker:
    return orm.sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(params=SUPPORTED_DBS)
def async_engine(request) -> AsyncEngine:
    if request.param == "postgresql":
        url = (
            request.getfixturevalue("postgresql")
            .url()
            .replace("postgresql://", "postgresql+asyncpg://")
        )
    else:
        raise ValueError("Unsupported database: %s", request.param)
    kwargs = {}
    if not SQLA2:
        kwargs["future"] = True
    engine = create_async_engine(url, **kwargs)
    return engine


@pytest.fixture
def async_sessionmaker(async_engine):
    if SQLA2:
        return asyncio.async_sessionmaker(async_engine)
    else:
        return lambda **kwargs: asyncio.AsyncSession(async_engine, **kwargs)


@pytest.fixture
def base():
    return orm.declarative_base()


@pytest.fixture
def default_employee_department_join_table(base):
    EmployeeDepartmentJoinTable = sqlalchemy.Table(
        "employee_department_join_table",
        base.metadata,
        sqlalchemy.Column(
            "employee_id", sqlalchemy.ForeignKey("employee.id"), primary_key=True
        ),
        sqlalchemy.Column(
            "department_id", sqlalchemy.ForeignKey("department.id"), primary_key=True
        ),
    )


@pytest.fixture
def secondary_tables(base, default_employee_department_join_table):
    class Employee(base):
        __tablename__ = "employee"
        id = sqlalchemy.Column(
            sqlalchemy.Integer, autoincrement=True, primary_key=True, nullable=False
        )
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        role = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        department = orm.relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        employees = orm.relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
        )

    return Employee, Department


@pytest.fixture
def secondary_tables_with_another_foreign_key(base):
    EmployeeDepartmentJoinTable = sqlalchemy.Table(
        "employee_department_join_table",
        base.metadata,
        sqlalchemy.Column(
            "employee_name", sqlalchemy.ForeignKey("employee.name"), primary_key=True
        ),
        sqlalchemy.Column(
            "department_id", sqlalchemy.ForeignKey("department.id"), primary_key=True
        ),
    )

    class Employee(base):
        __tablename__ = "employee"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, nullable=False)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False, primary_key=True)
        role = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        department = orm.relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        employees = orm.relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
        )

    return Employee, Department


@pytest.fixture
def secondary_tables_with_more_secondary_tables(
    base, default_employee_department_join_table
):
    EmployeeBuildingJoinTable = sqlalchemy.Table(
        "employee_building_join_table",
        base.metadata,
        sqlalchemy.Column(
            "employee_id", sqlalchemy.ForeignKey("employee.id"), primary_key=True
        ),
        sqlalchemy.Column(
            "building_id", sqlalchemy.ForeignKey("building.id"), primary_key=True
        ),
    )

    class Employee(base):
        __tablename__ = "employee"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        role = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        department = orm.relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )
        building = orm.relationship(
            "Building",
            secondary="employee_building_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        employees = orm.relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
        )

    class Building(base):
        __tablename__ = "building"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        employees = orm.relationship(
            "Employee",
            secondary="employee_building_join_table",
            back_populates="building",
        )

    return Employee, Department, Building


@pytest.fixture
def secondary_tables_with_use_list_false(base, default_employee_department_join_table):
    class Employee(base):
        __tablename__ = "employee"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        role = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        department = orm.relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        employees = orm.relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
            uselist=False,
        )

    return Employee, Department


@pytest.fixture
def secondary_tables_with_normal_relationship(
    base, default_employee_department_join_table
):
    class Employee(base):
        __tablename__ = "employee"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        role = sqlalchemy.Column(sqlalchemy.String, nullable=True)
        department = orm.relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )
        building_id = sqlalchemy.Column(
            sqlalchemy.Integer, sqlalchemy.ForeignKey("building.id")
        )
        building = orm.relationship(
            "Building",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        employees = orm.relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="department",
        )

    class Building(base):
        __tablename__ = "building"
        id = sqlalchemy.Column(sqlalchemy.Integer, autoincrement=True, primary_key=True)
        name = sqlalchemy.Column(sqlalchemy.String, nullable=False)
        employees = orm.relationship(
            "Employee",
            back_populates="building",
        )

    return Employee, Department, Building


@pytest.fixture
def expected_schema_from_secondary_tables():
    return '''
    type Department {
      id: Int!
      name: String
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
      role: String
      department: DepartmentConnection!
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
      departments: [Department!]!
    }
    '''


@pytest.fixture
def expected_schema_from_secondary_tables_with_more_secondary_tables():
    return '''
      type Building {
        id: Int!
        name: String!
        employees: EmployeeConnection!
      }

      type BuildingConnection {
        """Pagination data for this connection"""
        pageInfo: PageInfo!
        edges: [BuildingEdge!]!
      }

      type BuildingEdge {
        """A cursor for use in pagination"""
        cursor: String!

        """The item at the end of the edge"""
        node: Building!
      }

      type Department {
        id: Int!
        name: String!
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
        role: String
        department: DepartmentConnection!
        building: BuildingConnection!
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
        departments: [Department!]!
      }
      '''


@pytest.fixture
def expected_schema_from_secondary_tables_with_more_secondary_tables_with_use_list_false():
    return '''
    type Department {
      id: Int!
      name: String!
      employees: Employee
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
      role: String
      department: DepartmentConnection!
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
      departments: [Department!]!
    }
    '''


@pytest.fixture
def expected_schema_from_secondary_tables_with_more_secondary_tables_with__with_normal_relationship():
    return '''
    type Building {
      id: Int!
      name: String!
      employees: EmployeeConnection!
    }

    type Department {
      id: Int!
      name: String!
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
      role: String
      buildingId: Int
      department: DepartmentConnection!
      building: Building
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
      departments: [Department!]!
    }
    '''


def mapper():
    return StrawberrySQLAlchemyMapper()
