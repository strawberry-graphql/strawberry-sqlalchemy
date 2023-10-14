from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from sqlalchemy import and_, or_
from sqlalchemy.exc import NoResultFound
from sqlalchemy.inspection import inspect as sqlalchemy_inspect
from strawberry import relay
from strawberry.relay.exceptions import NodeIDAnnotationError

if TYPE_CHECKING:
    from typing_extensions import Literal

    from sqlalchemy.orm import Query, Session
    from strawberry.types.info import Info
    from strawberry.utils.await_maybe import AwaitableOrValue

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
) -> AwaitableOrValue[Iterable[_T]]:
    ...


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
) -> AwaitableOrValue[Iterable[_T]]:
    ...


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
) -> AwaitableOrValue[Iterable[Optional[_T]]]:
    ...


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
) -> AwaitableOrValue[Optional[Iterable[_T]]]:
    ...


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
]:
    ...


def resolve_model_nodes(
    source,
    *,
    session: Session,
    info=None,
    node_ids=None,
    required=False,
    filter_perms=False,
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
            Optional gql execution info. Make sure to always provide this or
            otherwise, the queryset cannot be optimized in case DjangoOptimizerExtension
            is enabled. This will also be used for `is_awaitable` check.
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
        attrs = cast(relay.Node, source).resolve_id_attr().split("|")
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
    filter_perms: bool = False,
) -> AwaitableOrValue[Optional[_T]]:
    ...


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
    filter_perms: bool = False,
) -> AwaitableOrValue[_T]:
    ...


def resolve_model_node(
    source,
    node_id,
    *,
    session: Session,
    info: Optional[Info] = None,
    required=False,
    filter_perms=False,
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
            Optional gql execution info. Make sure to always provide this or
            otherwise, the queryset cannot be optimized in case DjangoOptimizerExtension
            is enabled. This will also be used for `is_awaitable` check.
        required:
            If the return value is required to exist. If true, `qs.get()` will be
            used, which might raise `model.DoesNotExist` error if the node doesn't
            exist. Otherwise, `qs.first()` will be used, which might return None.

    Returns:
    -------
        The resolved node, already prefetched from the database

    """
    from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

    definition = StrawberrySQLAlchemyType[Any].from_type(source, strict=True)
    model = definition.model

    if isinstance(node_id, relay.GlobalID):
        node_id = node_id.node_id

    attrs = cast(relay.Node, source).resolve_id_attr().split("|")
    converters = [getattr(model, attr).type.python_type for attr in attrs]

    filter = dict(
        zip(
            cast(relay.Node, source).resolve_id_attr().split("|"),
            (converters[i](nid) for i, nid in enumerate(node_id.split("|"))),
        )
    )

    try:
        return session.get(model, filter)
    except NoResultFound:
        if not required:
            return None

        raise


def resolve_model_id_attr(source: Type) -> str:
    """
    Resolve the model id attribute.

    In case of composed primary keys, those will be returned separated by a `|`.
    """
    try:
        id_attr = super(source, source).resolve_id_attr()
    except NodeIDAnnotationError:
        from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

        definition = StrawberrySQLAlchemyType[Any].from_type(source, strict=True)
        id_attr = "|".join(
            key.name for key in sqlalchemy_inspect(definition.model).primary_key
        )

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
    id_attr = cast(relay.Node, source).resolve_id_attr().split("|")

    assert id_attr
    return "|".join(str(getattr(root, k)) for k in id_attr)
