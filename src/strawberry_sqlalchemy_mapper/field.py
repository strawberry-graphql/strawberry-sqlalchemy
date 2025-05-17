from __future__ import annotations

import asyncio
import contextlib
import contextvars
import dataclasses
import inspect
from collections import defaultdict
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Generator,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from typing_extensions import Annotated, TypeAlias

from sqlakeyset.types import Keyset
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, Session
from strawberry import relay
from strawberry.annotation import StrawberryAnnotation
from strawberry.extensions.field_extension import (
    FieldExtension,
)
from strawberry.permission import BasePermission
from strawberry.relay.exceptions import RelayWrongAnnotationError
from strawberry.relay.types import NodeIterableType
from strawberry.types import Info
from strawberry.types.arguments import StrawberryArgument, argument
from strawberry.types.base import (
    StrawberryList,
    StrawberryOptional,
    get_object_definition,
)
from strawberry.types.field import (
    _RESOLVER_TYPE,
    StrawberryField,
)
from strawberry.types.fields.resolver import StrawberryResolver
from strawberry.utils.aio import asyncgen_to_list

_T = TypeVar("_T")
_SessionMaker: TypeAlias = Callable[[], Union[Session, AsyncSession]]

assert argument  # type: ignore[truthy-function]


connection_session: contextvars.ContextVar[Union[Session, AsyncSession, None]] = (
    contextvars.ContextVar(
        "connection-session",
        default=None,
    )
)


@contextlib.contextmanager
def set_connection_session(
    s: Union[Session, AsyncSession, None],
) -> Generator[None, None, None]:
    token = connection_session.set(s)
    try:
        yield
    finally:
        connection_session.reset(token)


class StrawberrySQLAlchemyField(StrawberryField):
    """
    Base field for SQLAlchemy types.
    """

    def __init__(
        self,
        sessionmaker: _SessionMaker | None = None,
        keyset: Keyset | None = None,
        **kwargs,
    ):
        self.sessionmaker = sessionmaker
        self.keyset = keyset
        super().__init__(**kwargs)


@dataclasses.dataclass
class StrawberrySQLAlchemyAsyncQuery:
    session: AsyncSession
    query: Callable[[Session], Query]
    iterator: Iterator[Any] | None = None
    limit: int | None = None
    offset: int | None = None

    def __getitem__(self, key: int | slice):
        assert isinstance(key, slice)

        start = int(key.start) if key.start is not None else None
        if start is not None:
            self.offset = start

        stop = int(key.stop) if key.stop is not None else None
        if stop is not None:
            self.limit = stop - (start or 0)

        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.iterator is None:

            def query_runner(s: Session):
                q = self.query(s)
                if self.limit is not None:
                    q = q.limit(self.limit)
                if self.offset is not None:
                    q = q.offset(self.offset)
                return list(q)

            self.iterator = iter(await self.session.run_sync(query_runner))

        try:
            return next(self.iterator)
        except StopIteration as e:
            raise StopAsyncIteration from e


class StrawberrySQLAlchemyNodeExtension(relay.NodeExtension):
    def get_node_resolver(  # type: ignore[override]  # noqa: ANN201
        self, field: StrawberrySQLAlchemyField
    ):
        # NOTE: This is a copy of relay.NodeExtension to allow us to pass
        # the session to resolve_node below
        type_ = field.type
        is_optional = isinstance(type_, StrawberryOptional)

        if (field_sessionmaker := field.sessionmaker) is None:
            raise TypeError(f"Missing `sessionmaker` argument for field {field.name}")

        def resolver(
            info: Info,
            id: Annotated[relay.GlobalID, argument(description="The ID of the object.")],
        ):
            session = field_sessionmaker()

            if isinstance(session, AsyncSession):
                return session.run_sync(
                    lambda s: id.resolve_type(info).resolve_node(
                        id.node_id,
                        info=info,
                        required=not is_optional,
                        session=s,  # type: ignore
                    )
                )

            return id.resolve_type(info).resolve_node(
                id.node_id,
                info=info,
                required=not is_optional,
                session=session,  # type: ignore
            )

        return resolver

    def get_node_list_resolver(  # type: ignore[override]  # noqa: ANN201
        self,
        field: StrawberrySQLAlchemyField,
    ):
        # NOTE: This is a copy of relay.NodeExtension to allow us to pass
        # the session to resolve_nodes below
        type_ = field.type
        assert isinstance(type_, StrawberryList)
        is_optional = isinstance(type_.of_type, StrawberryOptional)

        if (field_sessionmaker := field.sessionmaker) is None:
            raise TypeError(f"Missing `sessionmaker` argument for field {field.name}")

        def resolver(
            info: Info,
            ids: Annotated[List[relay.GlobalID], argument(description="The IDs of the objects.")],
        ):
            session = field_sessionmaker()

            nodes_map: DefaultDict[Type[relay.Node], List[str]] = defaultdict(list)
            # Store the index of the node in the list of nodes of the same type
            # so that we can return them in the same order while also supporting
            # different types
            index_map: Dict[relay.GlobalID, Tuple[Type[relay.Node], int]] = {}
            for gid in ids:
                node_t = gid.resolve_type(info)
                nodes_map[node_t].append(gid.node_id)
                index_map[gid] = (node_t, len(nodes_map[node_t]) - 1)

            resolved_nodes = {
                node_t: (
                    session.run_sync(
                        lambda s, node_t=node_t, node_ids=node_ids: list(  # type: ignore
                            node_t.resolve_nodes(
                                info=info,
                                node_ids=node_ids,
                                required=not is_optional,
                                session=s,
                            )
                        )
                    )
                    if isinstance(session, AsyncSession)
                    else node_t.resolve_nodes(
                        info=info,
                        node_ids=node_ids,
                        required=not is_optional,
                        session=session,  # type: ignore
                    )
                )
                for node_t, node_ids in nodes_map.items()
            }
            awaitable_nodes = {
                node_t: nodes
                for node_t, nodes in resolved_nodes.items()
                if inspect.isawaitable(nodes)
            }
            # Async generators are not awaitable, so we need to handle them separately
            asyncgen_nodes = {
                node_t: nodes
                for node_t, nodes in resolved_nodes.items()
                if inspect.isasyncgen(nodes)
            }

            if awaitable_nodes or asyncgen_nodes:

                async def resolve(resolved=resolved_nodes):
                    resolved.update(
                        zip(
                            [
                                *awaitable_nodes.keys(),
                                *asyncgen_nodes.keys(),
                            ],
                            # Resolve all awaitable nodes concurrently
                            await asyncio.gather(
                                *awaitable_nodes.values(),
                                *(asyncgen_to_list(nodes) for nodes in asyncgen_nodes.values()),
                            ),
                        )
                    )

                    # Resolve any generator to lists
                    resolved = {node_t: list(nodes) for node_t, nodes in resolved.items()}
                    return [resolved[index_map[gid][0]][index_map[gid][1]] for gid in ids]

                return resolve()

            # Resolve any generator to lists
            resolved = {
                node_t: list(cast("Iterator[relay.Node]", nodes))
                for node_t, nodes in resolved_nodes.items()
            }
            return [resolved[index_map[gid][0]][index_map[gid][1]] for gid in ids]

        return resolver


class StrawberrySQLAlchemyConnectionExtension(relay.ConnectionExtension):
    def apply(self, field: StrawberrySQLAlchemyField) -> None:  # type: ignore[override]
        from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

        self.field = field
        strawberry_definition = get_object_definition(field.type, strict=True)
        node_type = strawberry_definition.type_var_map.get("NodeType")
        if node_type is None:
            specialized_type_var_map = strawberry_definition.specialized_type_var_map
            node_type = (
                specialized_type_var_map.get("NodeType")
                if specialized_type_var_map is not None
                else None
            )

        if node_type is None:
            raise RelayWrongAnnotationError(field.name, cast("type", field.origin))

        assert isinstance(node_type, type)
        sqlalchemy_definition = StrawberrySQLAlchemyType[Any].from_type(
            node_type,
            strict=True,
        )
        model = sqlalchemy_definition.model
        args: dict[str, StrawberryArgument] = {a.python_name: a for a in field.arguments}
        field.arguments = list(args.values())

        if field.base_resolver is None:
            if (field_sessionmaker := field.sessionmaker) is None:
                raise TypeError(f"Missing `sessionmaker` argument for field {field.name}")

            def default_resolver(
                root: Optional[Any],
                info: Info,
                **kwargs: Any,
            ) -> Iterable[Any]:
                session = connection_session.get()
                if session is None:
                    session = field_sessionmaker()

                def _get_query(s: Session):
                    query = getattr(root, field.python_name) if root is not None else s.query(model)

                    if field.keyset is not None:
                        query = query.order_by(*field.keyset)

                    return query

                if isinstance(session, AsyncSession):
                    return cast(
                        "Iterable[Any]",
                        StrawberrySQLAlchemyAsyncQuery(
                            session=session,
                            query=lambda s: _get_query(s),
                        ),
                    )

                return _get_query(session)

            field.base_resolver = StrawberryResolver(default_resolver)

        return super().apply(field)

    def resolve(self, *args, **kwargs) -> Any:
        if (field_sessionmaker := self.field.sessionmaker) is None:
            raise TypeError(f"Missing `sessionmaker` argument for field {self.field.name}")

        session = field_sessionmaker()

        if isinstance(session, AsyncSession):
            super_meth = super().resolve

            async def inner_resolve_async():
                async with session as s:
                    with set_connection_session(s):
                        retval = super_meth(*args, **kwargs)
                        if inspect.isawaitable(retval):
                            retval = await retval
                        return retval

            return inner_resolve_async()

        with session as s:
            with set_connection_session(s):
                return super().resolve(*args, **kwargs)

    async def resolve_async(self, *args, **kwargs) -> Any:
        if (field_sessionmaker := self.field.sessionmaker) is None:
            raise TypeError(f"Missing `sessionmaker` argument for field {self.field.name}")

        session = field_sessionmaker()

        if isinstance(session, AsyncSession):
            async with session as s:
                with set_connection_session(s):
                    return await super().resolve_async(*args, **kwargs)

        with session as s:
            with set_connection_session(s):
                return await super().resolve_async(*args, **kwargs)


@overload
def field(
    *,
    field_cls: type[StrawberrySQLAlchemyField] = StrawberrySQLAlchemyField,
    resolver: Callable[[], _T],
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    init: Literal[False] = False,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    graphql_type: Any | None = None,
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
) -> _T: ...


@overload
def field(
    *,
    field_cls: type[StrawberrySQLAlchemyField] = StrawberrySQLAlchemyField,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    init: Literal[True] = True,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    graphql_type: Any | None = None,
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
) -> Any: ...


@overload
def field(
    resolver: StrawberryResolver | Callable | staticmethod | classmethod,
    *,
    field_cls: type[StrawberrySQLAlchemyField] = StrawberrySQLAlchemyField,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    graphql_type: Any | None = None,
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
) -> StrawberrySQLAlchemyField: ...


def field(
    resolver=None,
    *,
    field_cls: type[StrawberrySQLAlchemyField] = StrawberrySQLAlchemyField,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    graphql_type: Any | None = None,
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
    # This init parameter is used by pyright to determine whether this field
    # is added in the constructor or not. It is not used to change
    # any behavior at the moment.
    init: Literal[True, False, None] = None,
) -> Any:
    """Annotate a method or property as a SQLAlchemy GraphQL field.

    Examples
    --------
        It can be used both as decorator and as a normal function:

        >>> @strawberry_sqlalchemy_mapper.field
        >>> class SomeType:
        ...     field_abc: str = strawberry_sqlalchemy_mapper.field(description="ABC")
        ...
        ...     @strawberry_sqlalchemy_mapper.field(description="ABC")
        ...     def field_with_resolver(self) -> str:
        ...         return "abc"

    """
    f = field_cls(
        python_name=None,
        graphql_name=name,
        type_annotation=StrawberryAnnotation.from_annotation(graphql_type),
        description=description,
        is_subscription=is_subscription,
        permission_classes=permission_classes or [],
        deprecation_reason=deprecation_reason,
        default=default,
        default_factory=default_factory,
        metadata=metadata,
        directives=directives or (),
        extensions=cast("List[FieldExtension]", extensions),
        sessionmaker=sessionmaker,
    )

    if resolver:
        return f(resolver)

    return f


def node(
    *,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    graphql_type: Any | None = None,
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
    # This init parameter is used by pyright to determine whether this field
    # is added in the constructor or not. It is not used to change
    # any behavior at the moment.
    init: Literal[True, False, None] = None,
) -> Any:
    """Annotate a property to create a relay query field.

    Examples
    --------
        Annotating something like this:

        >>> @strawberry.type
        >>> class Query:
        ...     some_node: SomeType = relay.node(description="ABC")

        Will produce a query like this that returns `SomeType` given its id.

        ```
        query {
          someNode (id: ID) {
            id
            ...
          }
        }
        ```

    """
    extensions = [*extensions, StrawberrySQLAlchemyNodeExtension()]
    return StrawberrySQLAlchemyField(
        python_name=None,
        graphql_name=name,
        type_annotation=StrawberryAnnotation.from_annotation(graphql_type),
        description=description,
        is_subscription=is_subscription,
        permission_classes=permission_classes or [],
        deprecation_reason=deprecation_reason,
        default=default,
        default_factory=default_factory,
        metadata=metadata,
        directives=directives or (),
        extensions=extensions,
        sessionmaker=sessionmaker,
    )


@overload
def connection(
    graphql_type: type[relay.Connection[relay.NodeType]] | None = None,
    *,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
    keyset: Keyset | None = None,
) -> Any: ...


@overload
def connection(
    graphql_type: type[relay.Connection[relay.NodeType]] | None = None,
    *,
    resolver: _RESOLVER_TYPE[NodeIterableType[Any]] | None = None,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    init: Literal[True] = True,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
    keyset: Keyset | None = None,
) -> Any: ...


def connection(
    graphql_type: type[relay.Connection[relay.NodeType]] | None = None,
    *,
    resolver: _RESOLVER_TYPE[NodeIterableType[Any]] | None = None,
    name: str | None = None,
    field_name: str | None = None,
    is_subscription: bool = False,
    description: str | None = None,
    permission_classes: list[type[BasePermission]] | None = None,
    deprecation_reason: str | None = None,
    default: Any = dataclasses.MISSING,
    default_factory: Callable[..., object] | object = dataclasses.MISSING,
    metadata: Mapping[Any, Any] | None = None,
    directives: Sequence[object] | None = (),
    extensions: Sequence[FieldExtension] = (),
    sessionmaker: _SessionMaker | None = None,
    keyset: Keyset | None = None,
    # This init parameter is used by pyright to determine whether this field
    # is added in the constructor or not. It is not used to change
    # any behavior at the moment.
    init: Literal[True, False, None] = None,
) -> Any:
    """Annotate a property or a method to create a relay connection field.

    Relay connections_ are mostly used for pagination purposes. This decorator
    helps creating a complete relay endpoint that provides default arguments
    and has a default implementation for the connection slicing.

    Note that when setting a resolver to this field, it is expected for this
    resolver to return an iterable of the expected node type, not the connection
    itself. That iterable will then be paginated accordingly. So, the main use
    case for this is to provide a filtered iterable of nodes by using some custom
    filter arguments.

    Examples
    --------
        Annotating something like this:

        >>> @strawberry.type
        >>> class Query:
        ...     @relay.connection(relay.ListConnection[SomeType])
        ...     def some_connection(self, age: int) -> Iterable[SomeType]:
        ...         ...

        Will produce a query like this:

        ```
        query {
          some_connection (
            before: String
            after: String
            first: Int
            after: Int
            age: Int
          ) {
            totalCount
            pageInfo {
              hasNextPage
              hasPreviousPage
              startCursor
              endCursor
            }
            edges {
              cursor
              node {
                  id
                  ...
              }
            }
          }
        }
        ```

    .. _Relay connections:
        https://relay.dev/graphql/connections.htm

    """
    extensions = [*extensions, StrawberrySQLAlchemyConnectionExtension()]
    f = StrawberrySQLAlchemyField(
        python_name=None,
        graphql_name=name,
        type_annotation=StrawberryAnnotation.from_annotation(graphql_type),
        description=description,
        is_subscription=is_subscription,
        permission_classes=permission_classes or [],
        deprecation_reason=deprecation_reason,
        default=default,
        default_factory=default_factory,
        metadata=metadata,
        directives=directives or (),
        extensions=extensions,
        sessionmaker=sessionmaker,
        keyset=keyset,
    )

    if resolver:
        f = f(resolver)

    return f
