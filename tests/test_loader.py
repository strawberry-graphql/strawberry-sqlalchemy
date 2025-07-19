import pytest
from sqlalchemy import Column, ForeignKey, Integer, String, Table
from sqlalchemy.orm import relationship
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def many_to_one_tables(base):
    class Employee(base):
        __tablename__ = "employee"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        department_id = Column(Integer, ForeignKey("department.id"))
        department = relationship("Department", back_populates="employees")
        __mapper_args__ = {"eager_defaults": True}

    class Department(base):
        __tablename__ = "department"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship("Employee", back_populates="department")
        __mapper_args__ = {"eager_defaults": True}

    return Employee, Department


@pytest.fixture
def secondary_tables(base):
    EmployeeDepartmentJoinTable = Table(
        "employee_department_join_table",
        base.metadata,
        Column("employee_id", ForeignKey("employee.e_id"), primary_key=True),
        Column("department_id", ForeignKey("department.d_id"), primary_key=True),
    )

    class Employee(base):
        __tablename__ = "employee"
        e_id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        departments = relationship(
            "Department",
            secondary="employee_department_join_table",
            back_populates="employees",
        )

    class Department(base):
        __tablename__ = "department"
        d_id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        employees = relationship(
            "Employee",
            secondary="employee_department_join_table",
            back_populates="departments",
        )

    return Employee, Department


def test_loader_init():
    loader = StrawberrySQLAlchemyLoader(bind=None)
    assert loader._bind is None
    assert loader._loaders == {}


@pytest.mark.asyncio
async def test_loader_for(engine, base, sessionmaker, many_to_one_tables):
    Employee, Department = many_to_one_tables
    base.metadata.create_all(engine)

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
        paginated_loader = base_loader.loader_for(Employee.department.property)
        loader = paginated_loader.loader_for()
        assert loader.max_batch_size is None
        assert loader.cache is True
        assert not loader.cache_map.cache_map
        assert loader._loop is None
        assert loader.load_fn is not None

        key = tuple(
            getattr(e1, local.key) for local, _ in Employee.department.property.local_remote_pairs
        )
        department = await loader.load(key)
        assert department.name == "d2"

        paginated_loader = base_loader.loader_for(Department.employees.property)
        loader = paginated_loader.loader_for()

        employees = await loader.load((d2.id,))
        assert {e.name for e in employees} == {"e1"}


@pytest.mark.asyncio
async def test_loader_with_async_session(
    async_engine, base, async_sessionmaker, many_to_one_tables
):
    Employee, Department = many_to_one_tables
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    async with async_sessionmaker(expire_on_commit=False) as session:
        e1 = Employee(name="e1")
        e2 = Employee(name="e2")
        d1 = Department(name="d1")
        d2 = Department(name="d2")
        session.add(e1)
        session.add(e2)
        session.add(d1)
        session.add(d2)
        await session.flush()

        e1.department = d2
        e2.department = d1
        await session.commit()
        d2_id = d2.id
        department_loader_key = tuple(
            getattr(e1, local.key) for local, _ in Employee.department.property.local_remote_pairs
        )
    base_loader = StrawberrySQLAlchemyLoader(async_bind_factory=async_sessionmaker)
    loader = base_loader.loader_for(Employee.department.property).loader_for()

    department = await loader.load(department_loader_key)
    assert department.name == "d2"

    loader = base_loader.loader_for(Department.employees.property).loader_for()
    employees = await loader.load((d2_id,))
    assert {e.name for e in employees} == {"e1"}


@pytest.mark.xfail
@pytest.mark.asyncio
async def test_loader_for_secondary(engine, base, sessionmaker, secondary_tables):
    Employee, Department = secondary_tables
    base.metadata.create_all(engine)

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

        base_loader = StrawberrySQLAlchemyLoader(bind=session)
        loader = base_loader.loader_for(Employee.departments.property).loader_for()

        key = tuple(
            [
                getattr(e1, local.key)
                for local, _ in Employee.departments.property.local_remote_pairs
            ]
        )
        departments = await loader.load(key)
        assert {d.name for d in departments} == {"d1", "d2"}
