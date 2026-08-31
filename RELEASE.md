Release type: minor

Migrate the `BigInt` scalar to `StrawberryConfig.scalar_map` and raise the supported
`strawberry-graphql` and Python versions.

`BigInt` was built by passing a type to `strawberry.scalar()`, a pattern deprecated in
`strawberry-graphql` 0.288.0, so simply importing `strawberry_sqlalchemy_mapper` emitted a
`DeprecationWarning`. `BigInt` is now a plain `NewType` and its scalar definition is exposed as
`strawberry_sqlalchemy_scalar_map`.

Fixes [#259](https://github.com/strawberry-graphql/strawberry-sqlalchemy/issues/259).

**Breaking Changes**:

- If your models use `BigInteger` columns, you must now register the scalar map on your schema:

```python
import strawberry
from strawberry.schema.config import StrawberryConfig
from strawberry_sqlalchemy_mapper import strawberry_sqlalchemy_scalar_map

schema = strawberry.Schema(
    query=Query,
    config=StrawberryConfig(scalar_map=strawberry_sqlalchemy_scalar_map),
)
```

  If you already maintain your own `scalar_map`, merge the two:

```python
config = StrawberryConfig(
    scalar_map={**strawberry_sqlalchemy_scalar_map, **my_scalar_map},
)
```

  Forgetting to register it raises `TypeError: ... fields cannot be resolved. Unexpected type
  '...BigInt'` when the schema is built.

  See [Custom scalars](https://strawberry.rocks/docs/types/scalars) in the Strawberry
  documentation for more about `scalar_map`.

- The minimum `strawberry-graphql` version is now 0.288.0, which is where `scalar_map` was added.

- Python 3.8 and 3.9 are no longer supported. `strawberry-graphql` 0.288.0 requires Python 3.10
  or newer, and both versions have reached end of life.

- Combining `first` with `before` on a connection now returns a different page. Older
  `strawberry-graphql` releases walked backward from the `before` cursor, effectively behaving
  like `last`. This was corrected in `strawberry-graphql`
  [0.322.2](https://github.com/strawberry-graphql/strawberry/releases/tag/0.322.2), so `before`
  now bounds the range and `first` takes from its start, per the Relay Cursor Connections spec.
  Queries relying on the previous behaviour should use `last`.

- Relay node ids are now exposed as the `ID` scalar instead of `GlobalID`, following the
  `relay_use_legacy_global_id` default in newer `strawberry-graphql` versions. Queries written
  against the generated schema must use `ID` (for example `query Fruit($id: ID!)`). Pass
  `StrawberryConfig(relay_use_legacy_global_id=True)` to keep the previous `GlobalID` naming.

**Fixes**:

- `import strawberry_sqlalchemy_mapper` no longer emits a `DeprecationWarning`.
- `Edge.resolve_edge` now accepts the additional keyword arguments its `strawberry.relay`
  supertype may pass to it.

**Internal**:

- Removed the `sys.version_info` branches that supported Python 3.8/3.9, in
  `strawberry_sqlalchemy_mapper/__init__.py` and the annotation merging in
  `StrawberrySQLAlchemyMapper.type()`.
- Dropped the `importlib-metadata` dependency, unused now that `importlib.metadata` is always
  available.
- Declared `typing-extensions` as an explicit dependency. It is imported directly by the mapper
  but was previously only installed as a transitive dependency of `strawberry-graphql`.
- Updated development dependencies: `ruff` 0.16, `mypy` 2.3, `pytest` 9, `pytest-asyncio` 1.4,
  `pytest-cov` 7, `pytest-codspeed` 5, `pytest-mypy-plugins` 4, `pytest-xdist` 3.8 and `nox` 2026.
- Set the `ruff` target and `pyright` version to Python 3.10, ignored the additional rules that
  conflict with the project's runtime-typing conventions (`UP035`, `UP045`, `CPY001`, `PLC0415`,
  `PLW0108`, `PYI061`, `PYI016`, `FURB110`), and removed `ANN101`/`ANN102`, which `ruff` no longer
  implements.
- Updated the CI test matrix, `noxfile.py`, the devcontainer image, Read the Docs and the
  GitHub action images to Python 3.10.
- Added `tests/test_scalars.py`, covering the `BigInt` scalar: schema registration, the
  `BigInteger` column mapping and serialization of values above 32 bits.
