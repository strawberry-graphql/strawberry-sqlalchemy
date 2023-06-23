import asyncio
import unittest

import pytest
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader


pytest_plugins = ("pytest_asyncio",)


def _create_many_to_one_tables(Base):
    class Employee(Base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("department.id"))
        department = relationship("Department", back_populates="employees")

    class Department(Base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship("Employee", back_populates="department")

    return Employee, Department


def _create_secondary_tables(Base):
    EmployeeDepartmentJoinTable = Table(
        "employee_department_join_table",
        Base.metadata,
        Column("employee_id", ForeignKey("employee.id"), primary_key=True),
        Column("department_id", ForeignKey("department.id"), primary_key=True)
    )

    class Employee(Base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        departments = relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees"
        )

    class Department(Base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="departments"
        )

    return Employee, Department


def test_loader_init():
    loader = StrawberrySQLAlchemyLoader(bind=None)
    assert loader.bind is None
    assert loader._loaders == {}


@pytest.mark.asyncio
async def test_loader_for(engine, Base, sessionmaker):
    Employee, Department = _create_many_to_one_tables(Base)
    Base.metadata.create_all(engine)

    with sessionmaker() as session:
        e1 = Employee(name="e1")
        e2 = Employee(name="e2")
        d1 = Department(name="d1")
        d2 = Department(name="d2")
        session.add(e1)
        session.add(e2)
        session.add(d1)
        session.add(d2)
        session.flush()

        e1.department = d2
        e2.department = d1
        session.commit()
        base_loader = StrawberrySQLAlchemyLoader(bind=session)
        loader = base_loader.loader_for(Employee.department.property)
        assert loader.max_batch_size is None
        assert loader.cache is True
        assert not loader.cache_map.cache_map
        assert loader._loop is None
        assert loader.load_fn is not None

        key = tuple([getattr(e1, local.key) for local, _ in Employee.department.property.local_remote_pairs])
        department = await loader.load(key)
        assert department.name == "d2"

        loader = base_loader.loader_for(Department.employees.property)
        key = tuple([getattr(d2, local.key) for local, _ in Department.employees.property.local_remote_pairs])
        employees = await loader.load((d2.id,))
        assert {e.name for e in employees} == {"e1"}


@pytest.mark.xfail
@pytest.mark.asyncio
async def test_loader_for_secondary(engine, Base, sessionmaker):
    Employee, Department = _create_secondary_tables(Base)
    Base.metadata.create_all(engine)

    with sessionmaker() as session:
        e1 = Employee(name="e1")
        e2 = Employee(name="e2")
        d1 = Department(name="d1")
        d2 = Department(name="d2")
        session.add(e1)
        session.add(e2)
        session.add(d1)
        session.add(d2)
        session.flush()

        e1.departments.append(d1)
        e1.departments.append(d2)
        e2.departments.append(d2)
        session.commit()

        base_loader=StrawberrySQLAlchemyLoader(bind=session)
        loader = base_loader.loader_for(Employee.departments.property)

        key = tuple([getattr(e1, local.key) for local, _ in Employee.departments.property.local_remote_pairs])
        departments = await loader.load(key)
        assert {d.name for d in departments} == {"d1", "d2"}
