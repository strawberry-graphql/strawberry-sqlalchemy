```markdown
# <img src="logo.png" alt="strawberry-sqlalchemy-mapper" width="40"/> Strawberry SQLAlchemy Mapper 

[![PyPI Version][pypi-badge]][pypi-url]  
[![Python 3.8+][python-badge]][python-url]  
[![CI Status][ci-badge]][ci-url]  
[![Code Coverage][coverage-badge]][coverage-url]  
[![License][license-badge]][license-url]

> Automatic Strawberry types for SQLAlchemy models with full relationship support

## ✨ Features
- Auto-generate types for **columns**, **relationships**, and **hybrid properties**
- **N+1 query prevention** via batching
- Native support for **SQLAlchemy ≥1.4**
- Lightweight (<100KB installation)

## 📦 Installation
```bash
pip install strawberry-sqlalchemy-mapper
```

## 🚀 Complete Usage Example

### 1. Define SQLAlchemy Models
```python
from sqlalchemy import Column, String, UUID, ForeignKey
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

class Employee(Base):
    __tablename__ = "employee"
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    department_id = Column(UUID, ForeignKey("department.id"))
    department = relationship("Department", back_populates="employees")

class Department(Base):
    __tablename__ = "department"
    id = Column(UUID, primary_key=True)
    name = Column(String, nullable=False)
    employees = relationship("Employee", back_populates="department")
```

### 2. Create Strawberry Types
```python
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

@strawberry_sqlalchemy_mapper.type(Employee)
class EmployeeType:
    __exclude__ = ["password_hash"]  # Sensitive field exclusion

@strawberry_sqlalchemy_mapper.type(Department)
class DepartmentType:
    pass
```

### 3. Set Up GraphQL Schema
```python
from strawberry import Schema
from sqlalchemy import select

@strawberry.type
class Query:
    @strawberry.field
    def departments(self) -> List[DepartmentType]:
        return session.scalars(select(Department)).all()

# Required finalization
strawberry_sqlalchemy_mapper.finalize()
schema = Schema(query=Query)
```

### 4. Query with Relationships
```graphql
query {
  departments {
    id
    name
    employees {
      id
      name
    }
  }
}
```

## ⚠️ Full Limitations
| SQLAlchemy Feature      | Support Level | Notes |
|-------------------------|---------------|-------|
| Polymorphic Hierarchies | ✅ Full       | Requires `@mapper.interface()` |
| TypeDecorator           | ⚠️ Partial    | Manual implementation may be needed |
| Association Proxies     | ✅ Full       | Must follow `association_proxy('rel1', 'rel2')` pattern |

## 🤝 Contributing
1. Fork the Project  
2. Setup dev environment:  
   ```bash
   pip install pre-commit
   pre-commit install
   ```
3. Create your Feature Branch  
4. Submit a Pull Request

## ⚖️ License
MIT © Strawberry GraphQL Team

<!-- Badge Links -->
[pypi-badge]: https://img.shields.io/pypi/v/strawberry-sqlalchemy-mapper?color=blue
[pypi-url]: https://pypi.org/project/strawberry-sqlalchemy-mapper/
[python-badge]: https://img.shields.io/badge/python-3.8%2B-blue
[ci-badge]: https://github.com/strawberry-graphql/strawberry-sqlalchemy-mapper/actions/workflows/tests.yml/badge.svg
[ci-url]: https://github.com/strawberry-graphql/strawberry-sqlalchemy-mapper/actions
[coverage-badge]: https://codecov.io/gh/strawberry-graphql/strawberry-sqlalchemy-mapper/branch/main/graph/badge.svg
[coverage-url]: https://codecov.io/gh/strawberry-graphql/strawberry-sqlalchemy-mapper
[license-badge]: https://img.shields.io/github/license/strawberry-graphql/strawberry-sqlalchemy-mapper
[license-url]: LICENSE.txt
```