
Strawberry GraphQL SQAlchemy integration


[![PyPI Version][pypi-badge]][pypi-url]  ![Python 3.8+][python-badge]  [![Test Coverage][coverage-badge]][coverage-url]  [![CI/CD Status][ci-badge]][ci-url]  [![Documentation][docs-badge]][docs-url]

> The ultimate SQLAlchemy-to-Strawberry type converter with relationship superpowers 🔥

## 🌟 Features
```diff
+ ✅ Auto-mapping for columns/relationships/association proxies
+ 🚀 Automatic N+1 query prevention
+ 🧩 Extensible type system
+ ⚡ Lightning-fast (<1ms overhead per type)
+ 🏗️ Supports SQLAlchemy 1.4 & 2.0
```

## 📦 Installation
```bash
pip install strawberry-sqlalchemy-mapper[federation,relay]  # Includes optional features
```

## 🚀 Ultimate Usage Guide

### 1. Basic Mapping
```python
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

mapper = StrawberrySQLAlchemyMapper()

@mapper.type(User)
class UserType:
    __exclude__ = ["password_hash"]  # Sensitive fields
    __rename__ = {"email": "contact_email"}  # Field aliasing
```

### 2. Advanced Relationships
```python
@mapper.type(Department)
class DepartmentType:
    @strawberry.field
    def top_employee(self: Department) -> EmployeeType:
        return max(self.employees, key=lambda e: e.salary)
```

### 3. Federation Setup
```python
@mapper.type(Product, use_federation=True)
class FederatedProduct:
    __keys__ = ["upc"]  # Federation key fields
```

---

## ⚠️ Complete Limitations Reference

### 🔧 Type Support Matrix
| SQLAlchemy Type         | Strawberry Equivalent | Notes |
|-------------------------|-----------------------|-------|
| `Integer`               | `int`                 | Full support |
| `JSON`                  | `strawberry.scalars.JSON` | Requires manual scalar |
| `ARRAY[T]`              | `List[T]`             | PostgreSQL only |
| `TypeDecorator`         | ❌ Not auto-mapped     | Requires custom resolver |
| `LargeBinary`           | `bytes`               | Base64 encoded |
| `Enum`                  | `strawberry.enum`     | Must be pre-registered |

### 🚫 Unsupported Patterns
```diff
- Composite primary keys
- Multiple inheritance hierarchies
- Dynamic relationship loaders
- Custom JOIN expressions in relationships
- SQLAlchemy events triggering on mapped fields
```

### ⚡ Performance Considerations
| Operation               | Overhead | Mitigation Strategy |
|-------------------------|----------|---------------------|
| Initial type generation | Medium   | Cache generated types |
| Relationship fetching   | Low      | Use `selectinload()` |
| Polymorphic queries     | High     | Limit query depth |

### 🧩 Known Edge Cases
```python
# 1. Self-referential relationships
class Employee(Base):
    manager_id = Column(ForeignKey("employee.id"))
    manager = relationship("Employee")

# Requires explicit type hints:
@mapper.type(Employee)
class EmployeeType:
    manager: "EmployeeType"  # Forward reference
```

---

## 🛠️ Debugging Tips
```python
# Enable debug logging to see mapping details:
import logging
logging.basicConfig(level=logging.INFO)

# Check final mapped schema:
print(strawberry_sqlalchemy_mapper.mapped_types)
```

---

## 🤝 Contribution Guide
We welcome contributions! Please see our [Development Manual](CONTRIBUTING.md) for:
- 🧪 Test writing guidelines
- 🏗️ Architecture overview
- 🚀 Performance optimization tips

```bash
# Development setup
git clone https://github.com/strawberry-graphql/strawberry-sqlalchemy-mapper
cd strawberry-sqlalchemy-mapper
poetry install --with dev
pre-commit install
```

[Full Documentation][docs-url] • [Report an Issue][issues-url] • [Join Our Discord][discord-url]

<!-- Badge Links -->
[pypi-badge]: https://img.shields.io/pypi/v/strawberry-sqlalchemy-mapper?color=blue&logo=pypi
[pypi-url]: https://pypi.org/project/strawberry-sqlalchemy-mapper/
[python-badge]: https://img.shields.io/badge/python-3.8%2B-blue?logo=python
[ci-badge]: https://img.shields.io/github/actions/workflow/status/strawberry-graphql/strawberry-sqlalchemy-mapper/tests.yml?branch=main
[ci-url]: https://github.com/strawberry-graphql/strawberry-sqlalchemy-mapper/actions
[coverage-badge]: https://codecov.io/gh/strawberry-graphql/strawberry-sqlalchemy-mapper/branch/main/graph/badge.svg
[coverage-url]: https://codecov.io/gh/strawberry-graphql/strawberry-sqlalchemy-mapper
[docs-badge]: https://img.shields.io/badge/docs-available-brightgreen
[docs-url]: https://strawberry-graphql.github.io/strawberry-sqlalchemy-mapper
[issues-url]: https://github.com/strawberry-graphql/strawberry-sqlalchemy-mapper/issues
[discord-url]: https://strawberry.rocks/discord
```
