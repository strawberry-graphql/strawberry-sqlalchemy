from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

import sqlakeyset
import strawberry
from sqlalchemy import and_, or_
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sqlalchemy_inspect
from strawberry import relay
from strawberry.relay.exceptions import NodeIDAnnotationError
from strawberry.relay.types import NodeType
from strawberry.types.base import StrawberryContainer, get_object_definition

if TYPE_CHECKING:
    from typing_extensions import Literal, Self

    from sqlalchemy.orm import Query, Session
    from strawberry.types.info import Info
    from strawberry.utils.await_maybe import AwaitableOrValue

    from strawberry_sqlalchemy_mapper.field import StrawberrySQLAlchemyAsyncQuery
    from strawberry_sqlalchemy_mapper.mapper import (
        WithStrawberrySQLAlchemyObjectDefinition,
    )


_T = TypeVar("_T")


__all__ = [
    "resolve_model_id",
    "resolve_model_id_attr",
    "resolve_model_node",
    "resolve_model_nodes",
]


@strawberry.type(description="An edge in a connection.")
class Edge(relay.Edge[NodeType]):
    @classmethod
    def resolve_edge(cls, node: NodeType, *, cursor: Any = None) -> Self:
        return cls(cursor=cursor, node=node)


@strawberry.type(name="Connection", description="A connection to a list of items.")
class KeysetConnection(relay.Connection[NodeType]):
    edges: List[Edge[NodeType]] = strawberry.field(  # type: ignore[assignment]
        description="Contains the nodes in this connection",
    )

    @classmethod
    def resolve_connection(
        cls,
        nodes: Union[Query, StrawberrySQLAlchemyAsyncQuery],  # type: ignore[override]
        *,
        info: Info,
        before: Optional[str] = None,
        after: Optional[str] = None,
        first: Optional[int] = None,
        last: Optional[int] = None,
        **kwargs: Any,
    ) -> AwaitableOrValue[Self]:
        from .field import StrawberrySQLAlchemyAsyncQuery, connection_session

        if first and last:
            raise ValueError("Cannot provide both `first` and `last`")
        elif first and before:
            raise ValueError("`first` cannot be provided with `before`")
        elif last and after:
            raise ValueError("`last` cannot be provided with `after`")

        max_results = info.schema.config.relay_max_results
        per_page = first or last or max_results
        if per_page > max_results:
            raise ValueError(f"Argument 'last' cannot be higher than {max_results}.")

        session = connection_session.get()
        assert session is not None

        def resolve_connection(page: sqlakeyset.Page):
            type_def = get_object_definition(cls)
            assert type_def
            field_def = type_def.get_field("edges")
            assert field_def

            field = field_def.resolve_type(type_definition=type_def)
            while isinstance(field, StrawberryContainer):
                field = field.of_type

            edge_class = cast("Edge[NodeType]", field)

            return cls(
                page_info=relay.PageInfo(
                    has_next_page=page.paging.has_next,
                    has_previous_page=page.paging.has_previous,
                    start_cursor=page.paging.get_bookmark_at(0) if page else None,
                    end_cursor=page.paging.get_bookmark_at(-1) if page else None,
                ),
                edges=[
                    edge_class.resolve_edge(n, cursor=page.paging.get_bookmark_at(i))
                    for i, n in enumerate(page)
                ],
            )

        def resolve_nodes(s: Session, nodes=nodes):
            if isinstance(nodes, StrawberrySQLAlchemyAsyncQuery):
                nodes = nodes.query(s)

            return resolve_connection(
                sqlakeyset.get_page(
                    nodes,
                    before=(sqlakeyset.unserialize_bookmark(before).place if before else None),
                    after=(sqlakeyset.unserialize_bookmark(after).place if after else None),
                    per_page=per_page,
                )
            )

        # TODO: It would be better to aboid session.run_sync in here but
        # sqlakeyset doesn't have a `get_page` async counterpart.
        if isinstance(session, AsyncSession):

            async def resolve_async(nodes=nodes):
                return await session.run_sync(lambda s: resolve_nodes(s))

            return resolve_async()

        return resolve_nodes(session)


@overload
def resolve_model_nodes(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    *,
    session: Session,
    info: Optional[Info] = None,
    node_ids: Iterable[Union[str, relay.GlobalID]],
    required: Literal[True],
) -> AwaitableOrValue[Iterable[_T]]: ...


@overload
def resolve_model_nodes(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    *,
    session: Session,
    info: Optional[Info] = None,
    node_ids: None = None,
    required: Literal[True],
) -> AwaitableOrValue[Iterable[_T]]: ...


@overload
def resolve_model_nodes(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    *,
    session: Session,
    info: Optional[Info] = None,
    node_ids: Iterable[Union[str, relay.GlobalID]],
    required: Literal[False],
) -> AwaitableOrValue[Iterable[Optional[_T]]]: ...


@overload
def resolve_model_nodes(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    *,
    session: Session,
    info: Optional[Info] = None,
    node_ids: None = None,
    required: Literal[False],
) -> AwaitableOrValue[Optional[Iterable[_T]]]: ...


@overload
def resolve_model_nodes(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    *,
    session: Session,
    info: Optional[Info] = None,
    node_ids: Optional[Iterable[Union[str, relay.GlobalID]]] = None,
    required: bool = False,
) -> AwaitableOrValue[
    Union[
        Iterable[_T],
        Query[_T],
        Iterable[Optional[_T]],
        Optional[Query[_T]],
    ]
]: ...


def resolve_model_nodes(
    source,
    *,
    session: Session,
    info=None,
    node_ids=None,
    required=False,
) -> AwaitableOrValue[
    Union[
        Iterable[_T],
        Iterable[Optional[_T]],
        Optional[Iterable[Optional[_T]]],
    ]
]:
    """
    Resolve model nodes.

    Args:
    ----
        source:
            The source model or the model type that implements the `Node` interface
        info:
            Optional gql execution info.
        session:
            A sqlalchemy session object.
        node_ids:
            Optional filter by those node_ids instead of retrieving everything
        required:
            If `True`, all `node_ids` requested must exist. If they don't,
            an error must be raised. If `False`, missing nodes should be
            returned as `None`. It only makes sense when passing a list of
            `node_ids`, otherwise it will should ignored.

    Returns:
    -------
        The resolved queryset, already prefetched from the database

    """
    from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

    definition = StrawberrySQLAlchemyType[Any].from_type(source, strict=True)
    model = definition.model

    query = session.query(model)

    if node_ids:
        attrs = cast("relay.Node", source).resolve_id_attr().split("|")
        converters = [getattr(model, attr).type.python_type for attr in attrs]
        filters = [
            and_(
                *(
                    getattr(model, attr) == converters[i](part)
                    for i, (attr, part) in enumerate(zip(attrs, node_id.split("|")))
                )
            )
            for node_id in node_ids
        ]
        query = query.where(or_(*filters))

    return query


@overload
def resolve_model_node(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    node_id: Union[str, relay.GlobalID],
    *,
    session: Session,
    info: Optional[Info] = ...,
    required: Literal[False] = ...,
) -> AwaitableOrValue[Optional[_T]]: ...


@overload
def resolve_model_node(
    source: Union[
        Type[WithStrawberrySQLAlchemyObjectDefinition],
        Type[relay.Node],
        Type[_T],
    ],
    node_id: Union[str, relay.GlobalID],
    *,
    session: Session,
    info: Optional[Info] = ...,
    required: Literal[True],
) -> AwaitableOrValue[_T]: ...


def resolve_model_node(
    source,
    node_id,
    *,
    session: Session,
    info: Optional[Info] = None,
    required=False,
):
    """
    Resolve model node.

    Args:
    ----
        source:
            The source model or the model type that implements the `Node` interface
        node_id:
            The node it to retrieve the model from
        session:
            A sqlalchemy session object.
        info:
            Optional gql execution info.
        required:
            If the return value is required to exist. If true, `qs.get()` will be
            used, which might raise `model.DoesNotExist` error if the node doesn't
            exist. Otherwise, `qs.first()` will be used, which might return None.

    Returns:
    -------
        The resolved node, already prefetched from the database

    """
    results = resolve_model_nodes(
        source,
        session=session,
        node_ids=[node_id],
        required=required,
    )

    try:
        return results.one()
    except NoResultFound:
        # If returning a single result fails, return `None` if this wasn't
        # required, otherwise reraise the exception
        if not required:
            return None

        raise


def resolve_model_id_attr(source: Type) -> str:
    """
    Resolve the model id attribute.

    In case of composed primary keys, those will be returned separated by a `|`.
    """
    cache_key = "_relay_model_id_attr"
    # Using __dict__ instead of getattr to support inheritance
    if (id_attr := source.__dict__.get(cache_key)) is not None:
        return id_attr

    try:
        id_attr = super(source, source).resolve_id_attr()
    except NodeIDAnnotationError:
        from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

        definition = StrawberrySQLAlchemyType[Any].from_type(source, strict=True)
        id_attr = "|".join(key.name for key in sqlalchemy_inspect(definition.model).primary_key)

    setattr(source, cache_key, id_attr)
    return id_attr


def resolve_model_id(
    source: type,
    root: Any,
    *,
    info: Optional[Info] = None,
) -> AwaitableOrValue[str]:
    """
    Resolve the model id.

    In case of composed primary keys, those will be returned separated by a `|`.
    """
    id_attr = cast("relay.Node", source).resolve_id_attr().split("|")

    assert id_attr
    # TODO: Maybe we can work with the tuples directly in the future?
    # We would need to add support on strawberry for that first though.
    return "|".join(str(getattr(root, k)) for k in id_attr)
