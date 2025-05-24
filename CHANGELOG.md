CHANGELOG
=========

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
