from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

def _create_employee_table():
    # todo: use pytest fixtures
    Base = declarative_base()
    class Employee(Base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
    return Employee

def _create_polymorphic_employee_table():
    Base = declarative_base()
    class Employee(Base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        type = Column(String(50))

        __mapper_args__ = {
            'polymorphic_identity':'employee',
            'polymorphic_on':type
        }
    return Employee


def test_mapper_default_model_to_type_name():
    Employee = _create_employee_table()
    assert StrawberrySQLAlchemyMapper._default_model_to_type_name(Employee) == "Employee"

def test_default_model_to_interface_name():
    Employee = _create_employee_table()
    assert StrawberrySQLAlchemyMapper._default_model_to_interface_name(Employee) == "EmployeeInterface"

def test_model_is_interface_fails():
    Employee = _create_employee_table()
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    assert strawberry_sqlalchemy_mapper.model_is_interface(Employee)is False

def test_model_is_interface_succeeds():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    Employee = _create_polymorphic_employee_table()
    assert strawberry_sqlalchemy_mapper.model_is_interface(Employee) is True

def test_is_model_polymorphic():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    Employee = _create_polymorphic_employee_table()
    assert strawberry_sqlalchemy_mapper._is_model_polymorphic(Employee) is True

def test_edge_type_for():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    employee_edge_class = strawberry_sqlalchemy_mapper._edge_type_for("Employee")
    assert employee_edge_class.__name__ == "EmployeeEdge"
    assert employee_edge_class._generated_field_keys == ['node']

def test_connection_type_for():
    strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
    employee_connection_class = strawberry_sqlalchemy_mapper._connection_type_for("Employee")
    assert employee_connection_class.__name__ == "EmployeeConnection"
    assert employee_connection_class._generated_field_keys == ['edges']
    assert employee_connection_class._is_generated_connection_type is True
