from importlib.metadata import PackageNotFoundError, version  # pragma: no cover

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "strawberry-sqlalchemy-mapper"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError


from .field import connection, field, node
from .loader import StrawberrySQLAlchemyLoader
from .mapper import StrawberrySQLAlchemyMapper
from .scalars import BigInt, strawberry_sqlalchemy_scalar_map

__all__ = [
    "BigInt",
    "StrawberrySQLAlchemyLoader",
    "StrawberrySQLAlchemyMapper",
    "__version__",
    "connection",
    "field",
    "node",
    "strawberry_sqlalchemy_scalar_map",
]
