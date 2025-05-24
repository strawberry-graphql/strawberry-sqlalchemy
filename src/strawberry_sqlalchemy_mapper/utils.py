from __future__ import annotations

from typing import (
    TypeVar,
    overload,
)

from strawberry.types.base import (
    StrawberryContainer,
    StrawberryType,
)

_T = TypeVar("_T", bound=type)


@overload
def unwrap_type(type_: StrawberryContainer) -> StrawberryType | type: ...


@overload
def unwrap_type(type_: _T) -> _T: ...


def unwrap_type(type_):
    while isinstance(type_, StrawberryContainer):
        type_ = type_.of_type

    return type_
