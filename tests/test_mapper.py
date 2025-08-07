import enum
import textwrap
from typing import List, Optional

import pytest
import strawberry
from sqlalchemy import JSON, Column, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql.array import ARRAY
from sqlalchemy.orm import relationship
from strawberry.scalars import JSON as StrawberryJSON
from strawberry.types.base import StrawberryList, StrawberryOptional
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper


@pytest.fixture
def polymorphic_employee(base):
    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        type = Column(String(50))
        name = Column(String(50))

        __mapper_args__ = {"polymorphic_identity": "employee", "polymorphic_on": type}

    return Employee


@pytest.fixture
def polymorphic_lawyer(polymorphic_employee):
    class Lawyer(polymorphic_employee):
        __mapper_args__ = {"polymorphic_identity": "lawyer"}

    return Lawyer


@pytest.fixture
def employee_table(base):
    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)

    return Employee


@pytest.fixture
def employee_and_department_tables(base):
    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("department.id"))
        department = relationship("Department", back_populates="employees")

    class Department(base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship("Employee", back_populates="department")

    return Employee, Department


@pytest.fixture
def polymorphic_employee_table(base):
    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        type = Column(String(50))

        __mapper_args__ = {"polymorphic_identity": "employee", "polymorphic_on": type}

    return Employee


def test_mapper_default_model_to_type_name(employee_table):
    Employee = employee_table
    assert StrawberrySQLAlchemyMapper._default_model_to_type_name(Employee) == "Employee"


def test_default_model_to_interface_name(employee_table):
    Employee = employee_table
    assert (
        StrawberrySQLAlchemyMapper._default_model_to_interface_name(Employee) == "EmployeeInterface"
    )


def test_model_is_interface_fails(employee_table, mapper):
    Employee = employee_table

    assert mapper.model_is_interface(Employee) is False


def test_model_is_interface_succeeds(polymorphic_employee_table, mapper):
    Employee = polymorphic_employee_table
    assert mapper.model_is_interface(Employee) is True


def test_is_model_polymorphic(polymorphic_employee_table, mapper):
    Employee = polymorphic_employee_table
    assert mapper._is_model_polymorphic(Employee) is True


def test_edge_type_for(mapper):
    employee_edge_class = mapper._edge_type_for("Employee")
    assert employee_edge_class.__name__ == "EmployeeEdge"
    assert employee_edge_class._generated_field_keys == ["node"]


def test_connection_type_for(mapper):
    employee_connection_class = mapper._connection_type_for("Employee")
    assert employee_connection_class.__name__ == "EmployeeConnection"
    assert employee_connection_class._generated_field_keys == ["edges"]
    assert employee_connection_class._is_generated_connection_type is True


def test_get_polymorphic_base_model(polymorphic_employee_table, mapper):
    Employee = polymorphic_employee_table

    class Lawyer(Employee):
        pass

    class ParaLegal(Lawyer):
        pass

    assert mapper._get_polymorphic_base_model(Employee) == Employee
    assert mapper._get_polymorphic_base_model(Lawyer) == Employee
    assert mapper._get_polymorphic_base_model(ParaLegal) == Employee


def test_convert_all_columns_to_strawberry_type(mapper):
    for (
        sqlalchemy_type,
        strawberry_type,
    ) in mapper.sqlalchemy_type_to_strawberry_type_map.items():
        assert (
            mapper._convert_column_to_strawberry_type(Column(sqlalchemy_type, nullable=False))
            == strawberry_type
        )


def test_convert_column_to_strawberry_type(mapper):
    int_column = Column(Integer, nullable=False)
    assert mapper._convert_column_to_strawberry_type(int_column) is int
    string_column = Column(String, nullable=False)
    assert mapper._convert_column_to_strawberry_type(string_column) is str


def test_convert_json_column_to_strawberry_type(mapper):
    json_colum = Column(JSON, nullable=False)
    assert mapper._convert_column_to_strawberry_type(json_colum) == StrawberryJSON


def test_convert_array_column_to_strawberry_type(mapper):
    column = Column(ARRAY(String))
    assert mapper._convert_column_to_strawberry_type(column) == Optional[List[str]]
    column = Column(ARRAY(String), nullable=False)
    assert mapper._convert_column_to_strawberry_type(column) == List[str]


def test_convert_enum_column_to_strawberry_type(mapper):
    class SampleEnum(enum.Enum):
        one = 1
        two = 2
        three = 3

    column = Column(Enum(SampleEnum))
    assert mapper._convert_column_to_strawberry_type(column) == Optional[SampleEnum]
    column = Column(Enum(SampleEnum), nullable=False)
    assert mapper._convert_column_to_strawberry_type(column) == SampleEnum


def test_convert_relationship_to_strawberry_type(employee_and_department_tables, mapper):
    _, Department = employee_and_department_tables
    employees_property = Department.employees.property
    assert (
        mapper._convert_relationship_to_strawberry_type(employees_property).__name__
        == "EmployeeConnection"
    )


def test_get_relationship_is_optional(employee_and_department_tables, mapper):
    _, Department = employee_and_department_tables
    employees_property = Department.employees.property
    assert mapper._get_relationship_is_optional(employees_property) is True


def test_add_annotation(mapper):
    class base:
        a: int = 3
        b: str = "abc"

    field_keys = []
    key = "name"
    annotation = "base_name"
    mapper._add_annotation(base, key, annotation, field_keys)
    assert base.__annotations__[key] == annotation
    assert field_keys == [key]


def test_connection_resolver_for(employee_and_department_tables, mapper):
    _, Department = employee_and_department_tables
    employees_property = Department.employees.property
    assert mapper.connection_resolver_for(employees_property) is not None


def test_type_simple(employee_table, mapper):
    Employee = employee_table

    @mapper.type(Employee)
    class Employee:
        pass

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 1
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type.__strawberry_definition__.fields) == 2
    employee_type_fields = mapped_employee_type.__strawberry_definition__.fields
    name = next(iter(filter(lambda f: f.name == "name", employee_type_fields)))
    assert name.type is str
    id = next(iter(filter(lambda f: f.name == "id", employee_type_fields)))
    assert id.type is int


def test_interface_and_type_polymorphic(mapper, polymorphic_employee, polymorphic_lawyer):
    @mapper.interface(polymorphic_employee)
    class EmployeeInterface:
        pass

    @mapper.type(polymorphic_employee)
    class Employee:
        pass

    @mapper.type(polymorphic_lawyer)
    class Lawyer:
        pass

    mapper.finalize()

    additional_interfaces = list(mapper.mapped_interfaces.values())
    assert len(additional_interfaces) == 1
    mapped_employee_interface_type = additional_interfaces[0]
    assert mapped_employee_interface_type.__name__ == "EmployeeInterface"

    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 2
    assert {"Employee", "Lawyer"} == {t.__name__ for t in additional_types}


def test_use_list(employee_and_department_tables, mapper):
    Employee, Department = employee_and_department_tables

    @mapper.type(Employee)
    class Employee:
        pass

    @mapper.type(Department)
    class Department:
        __use_list__ = ["employees"]

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 2
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    mapped_department_type = additional_types[1]
    assert mapped_department_type.__name__ == "Department"
    assert len(mapped_department_type.__strawberry_definition__.fields) == 3
    department_type_fields = mapped_department_type.__strawberry_definition__.fields

    name = next((field for field in department_type_fields if field.name == "employees"), None)
    assert name is not None
    assert isinstance(name.type, StrawberryOptional) is False
    assert isinstance(name.type, StrawberryList) is True


def test_type_relationships(employee_and_department_tables, mapper):
    Employee, _ = employee_and_department_tables

    @mapper.type(Employee)
    class Employee:
        pass

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 2
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type.__strawberry_definition__.fields) == 4
    employee_type_fields = mapped_employee_type.__strawberry_definition__.fields
    name = next(iter(filter(lambda f: f.name == "department_id", employee_type_fields)))
    assert type(name.type) is StrawberryOptional
    id = next(iter(filter(lambda f: f.name == "department", employee_type_fields)))
    assert type(id.type) is StrawberryOptional


def test_relationships_schema(employee_and_department_tables, mapper):
    EmployeeModel, DepartmentModel = employee_and_department_tables

    @mapper.type(EmployeeModel)
    class Employee:
        __exclude__ = ["password_hash"]

    @mapper.type(DepartmentModel)
    class Department:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def departments(self) -> Department: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = '''
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
    assert str(schema) == textwrap.dedent(expected).strip()


@pytest.mark.parametrize(
    "directives",
    [
        (["@deprecated(reason: 'Use newEmployee instead')"]),
        (
            [
                "@deprecated(reason: 'Use newEmployee instead')",
                "@customDirective(value: 'example')",
            ]
        ),
    ],
)
def test_type_with_directives(mapper, employee_table, directives):
    Employee = employee_table

    @mapper.type(Employee, directives=directives)
    class Employee:
        pass

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 1
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type.__strawberry_definition__.fields) == 2
    assert mapped_employee_type.__strawberry_definition__.directives == directives


@pytest.mark.parametrize(
    "directives",
    [
        (["@deprecated(reason: 'Use newEmployee instead')"]),
        (
            [
                "@deprecated(reason: 'Use newEmployee instead')",
                "@customDirective(value: 'example')",
            ]
        ),
    ],
)
def test_type_with_directives_and_federation(mapper, employee_table, directives):
    Employee = employee_table

    @mapper.type(Employee, directives=directives, use_federation=True)
    class Employee:
        pass

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 1
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type.__strawberry_definition__.fields) == 2
    assert mapped_employee_type.__strawberry_definition__.directives == directives


@pytest.mark.parametrize(
    ("use_federation_value", "expected_directives"),
    [(True, []), (False, ())],
)
def test_type_with_default_directives(
    mapper, employee_table, use_federation_value, expected_directives
):
    Employee = employee_table

    @mapper.type(Employee, use_federation=use_federation_value)
    class Employee:
        pass

    mapper.finalize()
    additional_types = list(mapper.mapped_types.values())
    assert len(additional_types) == 1
    mapped_employee_type = additional_types[0]
    assert mapped_employee_type.__name__ == "Employee"
    assert len(mapped_employee_type.__strawberry_definition__.fields) == 2
    assert mapped_employee_type.__strawberry_definition__.directives == expected_directives
