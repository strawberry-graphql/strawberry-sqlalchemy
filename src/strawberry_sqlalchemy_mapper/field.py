from __future__ import annotations

import dataclasses
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Sequence,
    TypeVar,
    cast,
    overload,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, Session
from strawberry import relay
from strawberry.annotation import StrawberryAnnotation
from strawberry.extensions.field_extension import (
    FieldExtension,
)
from strawberry.field import (
    StrawberryField,
    Union,
)
from strawberry.relay.exceptions import RelayWrongAnnotationError
from strawberry.type import (
    get_object_definition,
)
from strawberry.types.fields.resolver import StrawberryResolver

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    from strawberry.arguments import StrawberryArgument
    from strawberry.field import _RESOLVER_TYPE
    from strawberry.permission import BasePermission
    from strawberry.relay.types import NodeIterableType
    from strawberry.types import Info


_T = TypeVar("_T")
_SessionMaker: TypeAlias = Callable[[], Union[Session, AsyncSession]]


class StrawberrySQLAlchemyField(StrawberryField):
    """
    Base field for SQLAlchemy types.
    """

    def __init__(
        self,
        sessionmaker: _SessionMaker | None = None,
        **kwargs,
    ):
        self.sessionmaker = sessionmaker
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


class StrawberrySQLAlchemyConnectionExtension(relay.ConnectionExtension):
    def apply(self, field: StrawberrySQLAlchemyField) -> None:
        from strawberry_sqlalchemy_mapper.mapper import StrawberrySQLAlchemyType

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
            raise RelayWrongAnnotationError(field.name, cast(type, field.origin))

        assert isinstance(node_type, type)
        sqlalchemy_definition = StrawberrySQLAlchemyType.from_type(
            node_type,
            strict=True,
        )
        model = sqlalchemy_definition.model
        args: dict[str, StrawberryArgument] = {
            a.python_name: a for a in field.arguments
        }
        field.arguments = list(args.values())

        if field.base_resolver is None:
            if (field_sessionmaker := field.sessionmaker) is None:
                raise TypeError(
                    f"Missing `sessionmaker` argument for field {field.name}"
                )

            def default_resolver(
                root: None,
                info: Info,
                **kwargs: Any,
            ) -> Iterable[Any]:
                session = field_sessionmaker()
                if isinstance(session, AsyncSession):
                    return cast(
                        Iterable[Any],
                        StrawberrySQLAlchemyAsyncQuery(
                            session=session,
                            query=lambda s: s.query(model),
                        ),
                    )

                return session.query(model)

            field.base_resolver = StrawberryResolver(default_resolver)

        return super().apply(field)


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
) -> _T:
    ...


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
) -> Any:
    ...


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
) -> StrawberrySQLAlchemyField:
    ...


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

        >>> @strawberry.django.type
        >>> class X:
        ...     field_abc: str = strawberry.django.field(description="ABC")
        ...     @strawberry.django.field(description="ABC")
        ...
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
        extensions=cast(List[FieldExtension], extensions),
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
        >>> class X:
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
    extensions = [*extensions, relay.NodeExtension()]
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
) -> Any:
    ...


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
) -> Any:
    ...


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
        >>> class X:
        ...     some_node: relay.Connection[SomeType] = relay.connection(
        ...         description="ABC",
        ...     )
        ...
        ...     @relay.connection(description="ABC")
        ...     def get_some_nodes(self, age: int) -> Iterable[SomeType]:
        ...         ...

        Will produce a query like this:

        ```
        query {
          someNode (
            before: String
            after: String
            first: String
            after: String
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
    )

    if resolver:
        f = f(resolver)

    return f
