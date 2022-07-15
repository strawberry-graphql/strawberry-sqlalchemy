from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any, Optional, Union

import strawberry
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from strawberry.types import Info

from strawberry_sqlalchemy_mapper.sqlakeyset.paging import get_page as sqlakeyset_page


def cursor_from_obj(obj: Any) -> str:
    return encode_cursor(f"id:{obj.id}")


def encode_cursor(value: int) -> str:
    return base64.b64encode(str(value).encode()).decode()


def decode_cursor(value: str) -> int:
    return int(base64.b64decode(str(value).encode()).decode().split(":")[1])


@strawberry.interface
class Node:
    """GraphQL Relay Node interface.

    This interface is part of relay implementation, and is
    intended to be subclassed by types on which you want pagination.
    """

    id: strawberry.ID


@strawberry.interface
class Edge:
    """GraphQL Relay Edge interface.

    This interface is part of the relay implementation.
    """

    cursor: str
    node: Node


@strawberry.type
class PageInfo:
    """GraphQL Relay PageIngo type that gives information about the current page."""

    has_next_page: bool
    has_previous_page: bool
    start_cursor: str
    end_cursor: str

    @classmethod
    def empty_page(cls) -> PageInfo:
        return cls(False, False, encode_cursor(0), encode_cursor(-1))


@strawberry.interface
class Connection:
    """GraphQL Connection interface.

    This interface is part of the relay implementation.
    """

    edges: list[Edge]
    page_info: PageInfo


@strawberry.input
class PageInput:
    """GraphQL Relay PageInput.

    This input enable use of forward and backward pagination on resolver.
    It can be passed to `get_connection()` to get a connection object:

    >>> @strawberry.field
    >>> def users(page_input: PageInput) -> UserConnection:
    >>>     query = select(User).order_by(User.id)
    >>>     return await connection(query, page_input, UserConnection)
    """

    after: Optional[strawberry.ID] = None
    first: Optional[int] = None
    before: Optional[strawberry.ID] = None
    last: Optional[int] = None

    _error = "Valid combinations are either first/after or last/before."

    @property
    def per_page(self) -> int:
        """
        Valid combinations are either:
        - first, after
        - last, before
        """
        per_page = self.first
        if per_page is None:
            if self.last is None:
                raise ValueError("You must specify either 'first' or 'last'")
            elif self.after is not None:
                raise ValueError(f"You can't use 'after' with 'last'. {self._error}")
            per_page = self.last
        elif self.before is not None:
            raise ValueError(f"You can't use 'before' with 'first'. {self._error}")
        return per_page

    @property
    def place(self) -> Optional[Union[int, strawberry.ID]]:
        return self.after if self.before is None else self.before

    def decode_cursor(self) -> Optional[strawberry.ID]:
        place = self.place
        return (decode_cursor(place),) if place else place

    def __hash__(self) -> int:
        keys = [self.after or "", self.first or "", self.before or "", self.last or ""]
        return hash("".join(str(k) for k in keys))


class PagingList(list):
    def __init__(self, *args, page_info: PageInfo = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_info = page_info

    @property
    def page_info(self) -> PageInfo:
        if self._page_info is None:
            return PageInfo.empty_page()
        return self._page_info

    def set_page_info(self, page_info: PageInfo) -> None:
        self._page_info = page_info

    def page(self, page_input: RelativePageInput) -> "PagingList":
        """Paginate from a list of PagedObjects."""

        place = page_input.place
        backward = page_input.last is not None

        if place is not None:
            start = -1 if backward else 0

            for i, _ in enumerate(self):
                if i + 1 == place:
                    break
            else:
                i = len(self) if backward else 0

            start = i - page_input.last if backward else i + 1
            if backward:
                stop = i
            else:
                stop = i + page_input.first + 1
        else:
            start = len(self) - page_input.last if backward else 0
            stop = None if backward else start + page_input.first

        # correct boundaries
        if start < 0:
            start = 0

        if stop is not None and stop >= len(self):
            stop = None

        # Set page info
        if self[start:stop]:
            self.set_page_info(
                PageInfo(
                    has_next_page=stop is not None and stop < len(self),
                    has_previous_page=start > 0,
                    start_cursor=cursor_from_obj(self[start]),
                    end_cursor=cursor_from_obj(
                        self[stop - 1 if stop is not None else -1]
                    ),
                )
            )
        return PagingList(self[start:stop], page_info=self._page_info)


@strawberry.input
class RelativePageInput:

    after: Optional[int] = 0
    first: Optional[int] = None
    last: Optional[int] = None
    before: Optional[int] = None

    _error = "Valid combinations are either first/afterIndex or last/beforeIndex."

    @property
    def place(self) -> Optional[int]:
        if self.after is not None:
            return self.after
        elif self.before is not None:
            return self.before
        return None

    @property
    def per_page(self) -> int:
        """
        Valid combinations are either:
        - first, after
        - last, before
        """
        per_page = self.first
        if per_page is None:
            if self.last is None:
                raise ValueError("You must specify either 'first' or 'last'")
            elif self.before > 0:
                raise ValueError("before must be a negative index")
            elif self.after is not None:
                raise ValueError(
                    f"You can't use 'afterIndex' with 'last'. {self._error}"
                )
            per_page = self.last
        elif self.before is not None:
            raise ValueError(f"You can't use 'beforeIndex' with 'first'. {self._error}")
        return per_page

    def decode_cursor(self):
        place = self.place
        return (self.place,) if place else None

    def __hash__(self) -> int:
        keys = [
            self.after or "",
            self.first or "",
            self.before or "",
            self.last or "",
        ]
        return hash("".join(str(k) for k in keys))


async def page(selectable: Select, page_input: PageInput, session: AsyncSession):
    place = page_input.decode_cursor()
    backwards = True if page_input.last is not None else False

    page = await sqlakeyset_page(
        selectable,
        per_page=page_input.per_page,
        place=place,
        backwards=backwards,
        session=session,
    )

    null_cursor = encode_cursor("")
    start_cursor = (
        encode_cursor(page.paging.first[0]) if page.paging.first else null_cursor
    )

    end_cursor = encode_cursor(page.paging.last[0]) if page.paging.last else null_cursor

    page_info = PageInfo(
        has_next_page=page.paging.has_next,
        has_previous_page=page.paging.has_previous,
        start_cursor=start_cursor,
        end_cursor=end_cursor,
    )

    return [item[0] for item in page], page_info


async def connection(
    selectable: Select, page_input: PageInput, connection: type[Connection], info: Info
) -> tuple[list[Any], PageInfo]:
    """Get a connection object from a page input.

    >>> @strawberry.field
    >>> def users(page_input: PageInput) -> UserConnection:
    >>>     query = select(User).order_by(User.id)
    >>>     return await connection(query, page_input, UserConnection)
    """

    for f in connection._type_definition.fields:
        if f.name == "edges":
            edge = f.type.of_type
            break
    else:
        raise TypeError(f"{connection} type has no edges field")

    objects, page_info = await page(
        selectable, page_input, session=info.context["session"]
    )

    edges = [edge(node=item, cursor=cursor_from_obj(item)) for item in objects]
    return connection(edges=edges, page_info=page_info)


class ConnectionMixin:

    """Add edge and connection strawberry type to subclasses."""

    if TYPE_CHECKING:
        Edge: type[Edge]
        Connection: type[Connection]

    def __init_subclass__(cls) -> None:
        for attr in ["Edge", "Connection"]:
            if hasattr(cls, attr):
                raise TypeError(f"{cls.__name__} already has a {attr} attribute")

        edge_cls = type(
            f"{cls.__name__}Edge",
            (Edge,),
            {
                "__annotations__": {"cursor": str, "node": cls},
                "__module__": cls.__module__,
            },
        )
        setattr(cls, "Edge", strawberry.type(edge_cls))

        connection_cls = type(
            f"{cls.__name__}Connection",
            (Connection,),
            {
                "__annotations__": {
                    "page_info": PageInfo,
                    "edges": list[getattr(cls, "Edge")],
                },
                "__module__": cls.__module__,
            },
        )
        setattr(cls, "Connection", strawberry.type(connection_cls))
