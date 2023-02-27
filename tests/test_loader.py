from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader


def test_loader_init():
    loader = StrawberrySQLAlchemyLoader(bind=None)
    assert loader.bind is None
    assert loader._loaders == {}


def test_loader_for():
    Base = declarative_base()

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

    base_loader = StrawberrySQLAlchemyLoader(bind=None)
    loader = base_loader.loader_for(Employee.department.property)
    assert loader.max_batch_size is None
    assert loader.cache is True
    assert not loader.cache_map.cache_map
    assert loader._loop is None
    assert loader.load_fn is not None
