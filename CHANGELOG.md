CHANGELOG
=========

0.7.0 - 2025-08-07
------------------

Implement Relay-style cursor pagination for SQLAlchemy relationships by extending the connection resolver and DataLoader to accept pagination arguments, computing pageInfo metadata, and introducing cursor utilities. Add PaginatedLoader to scope DataLoader instances per pagination parameters and update tests to verify pagination behavior.

**New Features**:
- Support cursor-based pagination (first, after, last, before) on GraphQL relationship fields
- Introduce PaginatedLoader to manage DataLoader instances per pagination configuration

**Enhancements**:
- Extend connection resolvers to compute pageInfo fields (hasNextPage, hasPreviousPage, totalCount) and handle forward and backward pagination
- Add utilities for cursor encoding/decoding and relationship key extraction

**Tests**:
- Add comprehensive tests for forward and backward pagination scenarios in both synchronous and asynchronous execution contexts

**Examples**:

Get the first three books for a specific author:

```gql
query {
  author(id: 1) {
    id
    name
    books(first: 3) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```

Get all books after a specific book's cursor:

```gql
query($afterBook: String) {
  author(id: 1) {
    id
    name
    books(after: $afterBook) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```

Get the first three books for a specific author after a specific book's cursor:

```gql
query($afterBook: String) {
  author(id: 1) {
    id
    name
    books(first: 3, after: $afterBook) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```


Get the last three books for a specific author:

```gql
query {
  author(id: 1) {
    id
    name
    books(last: 3) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```

Get all books before a specific book's cursor:

```gql
query($beforeBook: String) {
  author(id: 1) {
    id
    name
    books(before: $beforeBook) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```

Get the last three books for a specific author before a specific book's cursor:

```gql
query($beforeBook: String) {
  author(id: 1) {
    id
    name
    books(last: 3, before: $beforeBook) {
      edges {
        node {
          id
          title
        }
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
}
```

Contributed by [David Roeca](https://github.com/davidroeca) via [PR #255](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/255/)


0.6.4 - 2025-07-08
------------------

This release improves how types inherit fields from other mapped types using `@mapper.type(...)`.
You can now safely inherit from another mapped type, and the resulting GraphQL type will include all expected fields with predictable conflict resolution.

Some examples:

- Basic Inheritance:

```python
@mapper.type(ModelA)
class ApiA:
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # ApiB inherits all fields declared in ApiA
    pass
```


- The `__exclude__` option continues working:

```python
@mapper.type(ModelA)
class ApiA:
    __exclude__ = ["relationshipB_id"]


@mapper.type(ModelB)
class ApiB(ApiA):
    # ApiB will have all fields declared in ApiA, except "relationshipB_id"
    pass
```

- If two SQLAlchemy models define fields with the same name, the field from the model inside `.type(...)` takes precedence:

```python
class ModelA(base):
    __tablename__ = "a"

    id = Column(String, primary_key=True)
    example_field = Column(String(50))


class ModelB(base):
    __tablename__ = "b"

    id = Column(String, primary_key=True)
    example_field = Column(Integer, autoincrement=True)


@mapper.type(ModelA)
class ApiA:
    # example_field will be a String
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # example_field will be taken from ModelB and will be an Integer
    pass
```


- If a field is explicitly declared in the mapped type, it will override any inherited or model-based definition:

```python
class ModelA(base):
    __tablename__ = "a"

    id = Column(String, primary_key=True)
    example_field = Column(String(50))


class ModelB(base):
    __tablename__ = "b"

    id = Column(String, primary_key=True)
    example_field = Column(Integer, autoincrement=True)


@mapper.type(ModelA)
class ApiA:
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # example_field will be a Float
    example_field: float = strawberry.field(name="exampleField")
```

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #253](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/253/)


0.6.3 - 2025-06-21
------------------

This update helps verify compatibility with Python 3.13.

- Added new test environments in the CI pipeline to ensure compatibility with Python 3.13.
- No changes to runtime code or dependencies.

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #254](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/254/)


0.6.2 - 2025-05-24
------------------

This release does not introduce any new features or bug fixes. It focuses solely on internal code quality improvements.

Changes:
- Added Mypy configuration aligned with the main Strawberry project.
- Enforced type checking via CI to ensure consistency.
- Ran pre-commit across all files to standardize formatting and follow the project's linting architecture.

These changes aim to improve maintainability and ensure better development practices moving forward.

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #250](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/250/)


0.6.1 - 2025-05-13
------------------

Ensure association proxy resolvers return valid relay connections, including `page_info` and edge `cursor` details, even for empty results.

Thanks to https://github.com/tylernisonoff for the original PR.

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #241](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/241/)


0.6.0 - 2025-04-25
------------------

**Added support for GraphQL directives** in the SQLAlchemy type mapper, enabling better integration with GraphQL federation.

**Example usage:**
```python
@mapper.type(Employee, directives=["@deprecated(reason: 'Use newEmployee instead')"])
class Employee:
    pass
```

Contributed by [Cameron Sechrist](https://github.com/csechrist) via [PR #204](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/204/)


0.5.0 - 2024-11-12
------------------

Add an optional function to exclude relationships from relay pagination and use traditional strawberry lists.
Default behavior preserves original behavior for backwords compatibilty.

Contributed by [Juniper](https://github.com/fruitymedley) via [PR #168](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/168/)


0.4.5 - 2024-10-17
------------------

Updated imports to be compatible with strawberry 0.236.0
Increased the minimum required strawberry version to 0.236.0

Contributed by [Hendrik](https://github.com/novag) via [PR #187](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/187/)


0.4.4 - 2024-10-02
------------------

Resolved an issue with the BigInt scalar definition, ensuring compatibility with Python 3.8 and 3.9. The missing name parameter was added to prevent runtime errors.
Fixed failing CI tests by updating the GitHub Actions workflow to improve test stability.

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #190](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/190/)


0.4.3 - 2024-05-22
------------------

Fix an issue where auto generated connections were missing some expected
attributes to be properly instantiated.

Contributed by [Thiago Bellini Ribeiro](https://github.com/bellini666) via [PR #137](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/137/)


0.4.2 - 2023-12-29
------------------

This change implements a new custom scalar `BigInt` that is mapped to SQLAlchemy's `BigInteger`.

Contributed by [IdoKendo](https://github.com/IdoKendo) via [PR #101](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/101/)


0.4.1 - 2023-12-27
------------------

Fix a regression from 0.4.0 which was [raising an issue](https://github.com/strawberry-graphql/strawberry-sqlalchemy/issues/97)
when trying to create a connection from the model's relationships.

Contributed by [Thiago Bellini Ribeiro](https://github.com/bellini666) via [PR #106](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/106/)


0.4.0 - 2023-12-06
------------------

Initial relay connection/node support using Strawberry's relay integration.

Contributed by [Thiago Bellini Ribeiro](https://github.com/bellini666) via [PR #65](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/65/)


0.3.1 - 2023-09-26
------------------

Make sure async session is still open when we call .all()

Contributed by [mattalbr](https://github.com/mattalbr) via [PR #55](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/55/)


0.3.0 - 2023-09-26
------------------

Adds support for async sessions. To use:

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader

url = "postgresql://..."
engine = create_async_engine(url)
sessionmaker = async_sessionmaker(engine)

loader = StrawberrySQLAlchemyLoader(async_bind_factory=sessionmaker)
```

Contributed by [mattalbr](https://github.com/mattalbr) via [PR #53](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/53/)


0.2.1 - 2023-09-21
------------------

Fix typo in pyproject.toml for poetry build.

Contributed by [Dan Sully](https://github.com/dsully) via [PR #52](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/52/)


0.2.0 - 2023-09-15
------------------

Native SQLAlchemy JSON Conversion Support. Added native support for SQLAlchemy JSON conversions. Now, you'll find that `sqlalchemy.JSON` is converted to `strawberry.scalars.JSON` for enhanced compatibility.

Contributed by [Luis Gustavo](https://github.com/Ckk3) via [PR #40](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/40/)


0.1.4 - 2023-09-11
------------------

Makes a series of minor changes to fix lint errors between MyPy and Ruff.

Contributed by [mattalbr](https://github.com/mattalbr) via [PR #38](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/38/)


0.1.3 - 2023-09-11
------------------

Fixes a bug where an Interface is not properly registered, resulting in an infinite-loop for mapping Interfaces to polymorphic Models.

Contributed by [Layton Wedgeworth](https://github.com/asimov-layton) via [PR #24](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/24/)


0.1.2 - 2023-09-08
------------------

Dependency version changes needed for python 3.12 compatibility.

Contributed by [mattalbr](https://github.com/mattalbr) via [PR #35](https://github.com/strawberry-graphql/strawberry-sqlalchemy/pull/35/)
