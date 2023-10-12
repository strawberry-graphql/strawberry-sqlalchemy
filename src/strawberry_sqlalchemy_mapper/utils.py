from __future__ import annotations

from typing import (
    TypeVar,
    overload,
)

from strawberry.type import (
    StrawberryContainer,
    StrawberryType,
)

_Type = TypeVar("_Type", bound="StrawberryType | type")


@overload
def unwrap_type(type_: StrawberryContainer) -> StrawberryType | type:
    ...


@overload
def unwrap_type(type_: _Type) -> _Type:
    ...


def unwrap_type(type_):
    while isinstance(type_, StrawberryContainer):
        type_ = type_.of_type

    return type_
