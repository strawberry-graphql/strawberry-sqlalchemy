import sys

if sys.version_info[:2] >= (3, 8):
    # TODO: Import directly (no need for conditional) when `python_requires = >= 3.8`
    from importlib.metadata import PackageNotFoundError, version  # pragma: no cover
else:
    from importlib_metadata import PackageNotFoundError, version  # pragma: no cover

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

__all__ = [
    "__version__",
    "StrawberrySQLAlchemyLoader",
    "StrawberrySQLAlchemyMapper",
    "field",
    "node",
    "connection",
]
