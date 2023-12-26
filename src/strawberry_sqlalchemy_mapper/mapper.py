import ast
import asyncio
import collections.abc
import dataclasses
import sys
import types
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from itertools import chain
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Dict,
    ForwardRef,
    Generic,
    Iterable,
    List,
    Literal,
    Mapping,
    MutableMapping,
    NewType,
    Optional,
    Protocol,
    Set,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)
from typing_extensions import Self

import sentinel
import strawberry
from sqlalchemy import (
    ARRAY,
    JSON,
    VARCHAR,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    Unicode,
    UnicodeText,
    inspect,
)
from sqlalchemy.dialects.postgresql import UUID as SQLAlchemyUUID
from sqlalchemy.ext.associationproxy import AssociationProxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    MANYTOMANY,
    MANYTOONE,
    ONETOMANY,
    Mapper,
    RelationshipProperty,
)
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.sql.type_api import TypeEngine
from strawberry import relay
from strawberry.annotation import StrawberryAnnotation
from strawberry.field import StrawberryField
from strawberry.lazy_type import LazyType
from strawberry.private import is_private
from strawberry.scalars import JSON as StrawberryJSON
from strawberry.type import WithStrawberryObjectDefinition, get_object_definition
from strawberry.types import Info

from strawberry_sqlalchemy_mapper.exc import (
    HybridPropertyNotAnnotated,
    InterfaceModelNotPolymorphic,
    UnsupportedAssociationProxyTarget,
    UnsupportedColumnType,
    UnsupportedDescriptorType,
)
from strawberry_sqlalchemy_mapper.field import field
from strawberry_sqlalchemy_mapper.relay import (
    resolve_model_id,
    resolve_model_id_attr,
    resolve_model_node,
    resolve_model_nodes,
)

if TYPE_CHECKING:
    from sqlalchemy.sql.expression import ColumnElement

BaseModelType = TypeVar("BaseModelType")

SkipTypeSentinelT = NewType("SkipTypeSentinelT", object)
SkipTypeSentinel = cast(SkipTypeSentinelT, sentinel.create("SkipTypeSentinel"))


#: Set on generated types to the original type handed to the decorator
_ORIGINAL_TYPE_KEY = "_original_type"
#: Set on generated types, containing the list of keys of fields that were generated
_GENERATED_FIELD_KEYS_KEY = "_generated_field_keys"
#: Set on generated <Model>Connection types
_IS_GENERATED_CONNECTION_TYPE_KEY = "_is_generated_connection_type"
#: Set on resolvers generated by the mapper
_IS_GENERATED_RESOLVER_KEY = "_is_generated_resolver"


@dataclasses.dataclass(frozen=True)
class StrawberrySQLAlchemyLazy(LazyType):
    # We don't actually want `Optional` here but we can't use dataclasse's
    # kw_only untul python 3.10, and we do have fields with default values
    # in strawberry's LazyType
    mapper: Optional["StrawberrySQLAlchemyMapper[Any]"] = None
    module: str = "__not_used__"

    def resolve_type(self) -> Type[Any]:
        assert self.mapper is not None
        return self.mapper.mapped_types[self.type_name]


class WithStrawberrySQLAlchemyObjectDefinition(
    WithStrawberryObjectDefinition,
    Protocol,
):
    __strawberry_sqlalchemy_definition__: ClassVar["StrawberrySQLAlchemyType"]


@dataclasses.dataclass
class StrawberrySQLAlchemyType(Generic[BaseModelType]):
    """
    Stores metadata information for a SQLAlchemy model type.
    """

    TYPE_KEY_NAME: ClassVar[str] = "__strawberry_sqlalchemy_definition__"

    #: In which mapper the type was defined
    mapper: "StrawberrySQLAlchemyMapper[BaseModelType]"

    #: The model used in the mapper
    model: Type[BaseModelType]

    @overload
    @classmethod
    def from_type(cls, type_: type, *, strict: Literal[True]) -> Self:
        ...

    @overload
    @classmethod
    def from_type(cls, type_: type, *, strict: bool = False) -> Optional[Self]:
        ...

    @classmethod
    def from_type(
        cls,
        type_: Union[type, WithStrawberrySQLAlchemyObjectDefinition],
        *,
        strict: bool = False,
    ) -> Optional[Self]:
        definition = getattr(type_, cls.TYPE_KEY_NAME, None)
        if strict and definition is None:
            raise TypeError(f"{type_!r} does not have a StrawberrySQLAlchemyType in it")
        return definition


class StrawberrySQLAlchemyMapper(Generic[BaseModelType]):
    """
    Mapper for SQLAlchemy models to Strawberry types.

    Requires a consistent naming convention between SQLAlchemy
    models and Strawberry types, which is codified in `model_to_type_name`.
    By default, the convention is model name == type name,
    but you can modify it so that e.g., `BookModel` (model) -> `Book` (type).
    """

    #: Function to get the strawberry.type name for a given model
    model_to_type_name: Callable[[Type[BaseModelType]], str]

    #: Function to get the strawberry.interface name
    #: for a given (polymorphic base) model
    model_to_interface_name: Callable[[Type[BaseModelType]], str]

    #: Default mapping from sqlalchemy types to strawberry types
    _default_sqlalchemy_type_to_strawberry_type_map: Dict[
        Type[TypeEngine], Union[Type[Any], SkipTypeSentinelT]
    ] = {
        Integer: int,
        Float: float,
        BigInteger: int,
        Numeric: Decimal,
        DateTime: datetime,
        Date: date,
        Time: time,
        String: str,
        Text: str,
        Boolean: bool,
        LargeBinary: SkipTypeSentinel,
        Unicode: str,
        UnicodeText: str,
        SmallInteger: int,
        SQLAlchemyUUID: uuid.UUID,
        VARCHAR: str,
        JSON: StrawberryJSON,
    }
    #: Mapping from sqlalchemy types to strawberry types
    sqlalchemy_type_to_strawberry_type_map: MutableMapping[
        Type[TypeEngine], Union[Type[Any], SkipTypeSentinelT]
    ]
    #: <Model>Edge types generated by the mapper
    edge_types: Dict[str, Type[Any]]
    #: <Model>Connection types generated by the mapper
    connection_types: Dict[str, Type[Any]]
    #: Model (non-interface) types generated by the mapper
    mapped_types: Dict[str, Type[Any]]
    #: Model interface types generated by the mapper
    mapped_interfaces: Dict[str, Type[Any]]
    #: All (non-interface) models that are related to currently mapped types
    #: (since we need to generate types for all relationshps)
    _related_type_models: Set[Type[BaseModelType]]
    #: All interface models that are related to currently mapped types
    _related_interface_models: Set[Type[BaseModelType]]

    def __init__(
        self,
        model_to_type_name: Optional[Callable[[Type[BaseModelType]], str]] = None,
        model_to_interface_name: Optional[Callable[[Type[BaseModelType]], str]] = None,
        extra_sqlalchemy_type_to_strawberry_type_map: Optional[
            Mapping[Type[TypeEngine], Type[Any]]
        ] = None,
    ) -> None:
        if model_to_type_name is None:
            model_to_type_name = self._default_model_to_type_name
        self.model_to_type_name = model_to_type_name
        if model_to_interface_name is None:
            model_to_interface_name = self._default_model_to_interface_name
        self.model_to_interface_name = model_to_interface_name
        self.sqlalchemy_type_to_strawberry_type_map = (
            self._default_sqlalchemy_type_to_strawberry_type_map.copy()
        )
        if extra_sqlalchemy_type_to_strawberry_type_map is not None:
            self.sqlalchemy_type_to_strawberry_type_map.update(
                extra_sqlalchemy_type_to_strawberry_type_map
            )
        self.edge_types = {}
        self.connection_types = {}
        self.mapped_types = {}
        self.mapped_interfaces = {}
        self._related_type_models = set()
        self._related_interface_models = set()

    @staticmethod
    def _default_model_to_type_name(model: Type[BaseModelType]) -> str:
        return model.__name__

    @staticmethod
    def _default_model_to_interface_name(model: Type[BaseModelType]) -> str:
        return f"{model.__name__}Interface"

    def model_is_interface(self, model: Type[BaseModelType]) -> bool:
        """
        Whether a given SQLAlchemy model is a valid
        interface (base of a polymorphic hierarchy)
        """
        return (
            self._is_model_polymorphic(model)
            and self._get_polymorphic_base_model(model) == model
        )

    def model_to_type_or_interface_name(self, model: Type[BaseModelType]) -> str:
        """
        Get corresponding name of the corresponding type
        for the model if it's the target of a relationship
        """
        if self.model_is_interface(model):
            return self.model_to_interface_name(model)
        else:
            return self.model_to_type_name(model)

    def _is_model_polymorphic(self, model: Type[BaseModelType]) -> bool:
        """
        Whether a model is part of a polymorphic hierarchy
        """
        return inspect(model).polymorphic_on is not None  # type: ignore[union-attr]

    def _edge_type_for(self, type_name: str) -> Type[Any]:
        """
        Get or create a corresponding Edge model for the given type
        (to support future pagination)
        """
        edge_name = f"{type_name}Edge"
        if edge_name not in self.edge_types:
            lazy_type = StrawberrySQLAlchemyLazy(type_name=type_name, mapper=self)
            self.edge_types[edge_name] = edge_type = strawberry.type(
                dataclasses.make_dataclass(
                    edge_name,
                    [],
                    bases=(relay.Edge[lazy_type],),  # type: ignore[valid-type]
                )
            )
            setattr(edge_type, _GENERATED_FIELD_KEYS_KEY, ["node"])
        return self.edge_types[edge_name]

    def _connection_type_for(self, type_name: str) -> Type[Any]:
        """
        Get or create a corresponding Connection model for the given type
        (to support future pagination)
        """
        connection_name = f"{type_name}Connection"
        if connection_name not in self.connection_types:
            edge_type = self._edge_type_for(type_name)
            lazy_type = StrawberrySQLAlchemyLazy(type_name=type_name, mapper=self)
            self.connection_types[connection_name] = connection_type = strawberry.type(
                dataclasses.make_dataclass(
                    connection_name,
                    [
                        ("edges", List[edge_type]),  # type: ignore[valid-type]
                    ],
                    bases=(relay.ListConnection[lazy_type],),  # type: ignore[valid-type]
                )
            )
            setattr(connection_type, _GENERATED_FIELD_KEYS_KEY, ["edges"])
            setattr(connection_type, _IS_GENERATED_CONNECTION_TYPE_KEY, True)
        return self.connection_types[connection_name]

    def _get_polymorphic_base_model(
        self, model: Type[BaseModelType]
    ) -> Type[BaseModelType]:
        """
        Given a model, return the base of its inheritance tree (which may be itself).
        """
        return inspect(model).base_mapper.entity  # type: ignore[union-attr]

    def _convert_column_to_strawberry_type(
        self, column: Column
    ) -> Union[Type[Any], SkipTypeSentinelT]:
        """
        Given a SQLAlchemy Column, return the type annotation for the field in the
        corresponding strawberry type.
        """
        if isinstance(column.type, Enum):
            type_annotation = column.type.python_type
        elif isinstance(column.type, ARRAY):
            item_type = self._convert_column_to_strawberry_type(
                Column(column.type.item_type, nullable=False)
            )
            if item_type is SkipTypeSentinel:
                return item_type
            type_annotation = List[item_type]  # type: ignore
        else:
            for (
                sqlalchemy_type,
                strawberry_type,
            ) in self.sqlalchemy_type_to_strawberry_type_map.items():
                if isinstance(column.type, sqlalchemy_type):
                    type_annotation = strawberry_type
                    break
            else:
                raise UnsupportedColumnType(column.key, column.type)
        if type_annotation is SkipTypeSentinel:
            return type_annotation
        if column.nullable:
            type_annotation = Optional[type_annotation]
        assert type_annotation is not None
        return type_annotation

    def _convert_relationship_to_strawberry_type(
        self, relationship: RelationshipProperty
    ) -> Union[Type[Any], ForwardRef]:
        """
        Given a SQLAlchemy relationship, return the type annotation for the field in the
        corresponding strawberry type.
        """
        relationship_model: Type[BaseModelType] = relationship.entity.entity  # type: ignore[assignment]
        type_name = self.model_to_type_or_interface_name(relationship_model)
        if self.model_is_interface(relationship_model):
            self._related_interface_models.add(relationship_model)
        else:
            self._related_type_models.add(relationship_model)
        if relationship.uselist:
            return self._connection_type_for(type_name)
        else:
            if self._get_relationship_is_optional(relationship):
                return Optional[ForwardRef(type_name)]  # type: ignore
            else:
                return ForwardRef(type_name)

    def _get_relationship_is_optional(self, relationship: RelationshipProperty) -> bool:
        """
        Whether the value for a relationship can be nullable
        """
        if relationship.direction in [ONETOMANY, MANYTOMANY]:
            # many on other side means it's optional always
            return True
        else:
            assert relationship.direction == MANYTOONE
            # this model is the one with the FK
            local_col: ColumnElement
            for local_col, _ in relationship.local_remote_pairs or []:
                if local_col.nullable:
                    return True
            return False

    def _add_annotation(
        self, type_: Any, key: str, annotation: Any, generated_field_keys: List[str]
    ) -> None:
        """
        Add type annotation to the given type.
        """
        type_.__annotations__[key] = annotation
        if not hasattr(type_, key):
            setattr(type_, key, field())
        generated_field_keys.append(key)

    def _get_association_proxy_annotation(
        self, mapper: Mapper, key: str, descriptor: Any
    ) -> Union[Type[Any], ForwardRef, SkipTypeSentinelT]:
        """
        Given an association proxy, return the type annotation
        for it. This only supports association proxies that
        are of the form (relationship, relationship).
        """
        is_multiple = mapper.relationships[descriptor.target_collection].uselist
        in_between_mapper: Mapper = mapper.relationships[  # type: ignore[assignment]
            descriptor.target_collection
        ].entity
        if descriptor.value_attr in in_between_mapper.relationships:
            relationship = in_between_mapper.relationships[descriptor.value_attr]
            is_multiple = is_multiple or relationship.uselist
            strawberry_type = self._convert_relationship_to_strawberry_type(
                relationship
            )
        else:
            raise UnsupportedAssociationProxyTarget(key)
        if strawberry_type is SkipTypeSentinel:
            return strawberry_type
        if is_multiple and not self._is_connection_type(strawberry_type):
            if isinstance(strawberry_type, ForwardRef):
                strawberry_type = self._connection_type_for(
                    strawberry_type.__forward_arg__
                )
            else:
                strawberry_type = self._connection_type_for(strawberry_type.__name__)
        return strawberry_type

    def make_connection_wrapper_resolver(
        self, resolver: Callable[..., Awaitable[Any]], type_name: str
    ) -> Callable[..., Awaitable[Any]]:
        """
        Wrap a resolver that returns an array of model types to return
        a Connection instead.
        """
        connection_type = self._connection_type_for(type_name)
        edge_type = self._edge_type_for(type_name)

        async def wrapper(self, info: Info):
            return connection_type(
                edges=[
                    edge_type(
                        node=related_object,
                    )
                    for related_object in await resolver(self, info)
                ]
            )

        setattr(wrapper, _IS_GENERATED_RESOLVER_KEY, True)

        return wrapper

    def relationship_resolver_for(
        self, relationship: RelationshipProperty
    ) -> Callable[..., Awaitable[Any]]:
        """
        Return an async field resolver for the given relationship,
        so as to avoid n+1 query problem.
        """

        async def resolve(self, info: Info):
            instance_state = cast(InstanceState, inspect(self))
            if relationship.key not in instance_state.unloaded:
                related_objects = getattr(self, relationship.key)
            else:
                relationship_key = tuple(
                    [
                        getattr(self, local.key)
                        for local, _ in relationship.local_remote_pairs or []
                        if local.key
                    ]
                )
                if any(item is None for item in relationship_key):
                    if relationship.uselist:
                        return []
                    else:
                        return None
                if isinstance(info.context, dict):
                    loader = info.context["sqlalchemy_loader"]
                else:
                    loader = info.context.sqlalchemy_loader
                related_objects = await loader.loader_for(relationship).load(
                    relationship_key
                )
            return related_objects

        setattr(resolve, _IS_GENERATED_RESOLVER_KEY, True)

        return resolve

    def connection_resolver_for(
        self, relationship: RelationshipProperty
    ) -> Callable[..., Awaitable[Any]]:
        """
        Return an async field resolver for the given relationship that
        returns a Connection instead of an array of objects.
        """
        relationship_resolver = self.relationship_resolver_for(relationship)
        if relationship.uselist:
            return self.make_connection_wrapper_resolver(
                relationship_resolver,
                self.model_to_type_or_interface_name(relationship.entity.entity),  # type: ignore[arg-type]
            )
        else:
            return relationship_resolver

    def _is_connection_type(self, type_: Union[Type[Any], ForwardRef]) -> bool:
        """
        Returns whether a given type is a <Model>Connection type.
        """
        return getattr(type_, _IS_GENERATED_CONNECTION_TYPE_KEY, False)

    def association_proxy_resolver_for(
        self, mapper: Mapper, descriptor: Any, strawberry_type: Type
    ) -> Callable[..., Awaitable[Any]]:
        """
        Return an async field resolver for the given association proxy.
        """
        in_between_relationship = mapper.relationships[descriptor.target_collection]
        in_between_resolver = self.relationship_resolver_for(in_between_relationship)
        in_between_mapper: Mapper = mapper.relationships[  # type: ignore[assignment]
            descriptor.target_collection
        ].entity
        assert descriptor.value_attr in in_between_mapper.relationships
        end_relationship = in_between_mapper.relationships[descriptor.value_attr]
        end_relationship_resolver = self.relationship_resolver_for(end_relationship)
        end_type_name = self.model_to_type_or_interface_name(
            end_relationship.entity.entity  # type: ignore[arg-type]
        )
        connection_type = self._connection_type_for(end_type_name)
        edge_type = self._edge_type_for(end_type_name)
        is_multiple = self._is_connection_type(strawberry_type)

        async def resolve(self, info: Info):
            in_between_objects = await in_between_resolver(self, info)
            if in_between_objects is None:
                if is_multiple:
                    return connection_type(edges=[])
                else:
                    return None
            if descriptor.value_attr in in_between_mapper.relationships:
                assert end_relationship_resolver is not None
                if isinstance(in_between_objects, collections.abc.Iterable):
                    outputs = await asyncio.gather(
                        *[
                            end_relationship_resolver(obj, info)
                            for obj in in_between_objects
                        ]
                    )
                    if outputs and isinstance(outputs[0], list):
                        outputs = list(chain.from_iterable(outputs))
                    else:
                        outputs = [output for output in outputs if output is not None]
                else:
                    outputs = await end_relationship_resolver(in_between_objects, info)
                if not isinstance(outputs, collections.abc.Iterable):
                    return outputs
                return connection_type(edges=[edge_type(node=obj) for obj in outputs])
            else:
                assert descriptor.value_attr in in_between_mapper.columns
                if isinstance(in_between_objects, collections.abc.Iterable):
                    return [
                        getattr(obj, descriptor.value_attr)
                        for obj in in_between_objects
                    ]
                else:
                    return getattr(in_between_objects, descriptor.value_attr)

        setattr(resolve, _IS_GENERATED_RESOLVER_KEY, True)
        return resolve

    def _handle_columns(
        self,
        mapper: Mapper,
        type_: Any,
        excluded_keys: Iterable[str],
        generated_field_keys: List[str],
    ) -> None:
        """
        Add annotations for the columns of the given mapper.
        """
        column: Column
        for key, column in mapper.columns.items():
            if (
                key in excluded_keys
                or key in type_.__annotations__
                or hasattr(type_, key)
            ):
                continue
            type_annotation = self._convert_column_to_strawberry_type(column)
            if type_annotation is not SkipTypeSentinel:
                self._add_annotation(
                    type_,
                    key,
                    type_annotation,
                    generated_field_keys,
                )

    def type(
        self,
        model: Type[BaseModelType],
        make_interface=False,
        use_federation=False,
    ) -> Callable[[Type[object]], Any]:
        """
        Decorate a type with this to register it as a strawberry type
        for the given SQLAlchemy model. This will automatically add fields
        for the model's columns, relationships, association proxies, and hybrid
        properties. For example:

        ```
        class Employee(Model):
            id = Column(UUID, primary_key=True)
            name = Column(String, nullable=False)


        # in another file
        strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()
        @strawberry_sqlalchemy_mapper.type(models.Employee)
        class Employee:
            pass
        ```
        """

        def convert(type_: Any) -> Any:
            old_annotations = getattr(type_, "__annotations__", {})
            type_.__annotations__ = {
                k: v for k, v in old_annotations.items() if is_private(v)
            }
            mapper: Mapper = cast(Mapper, inspect(model))
            generated_field_keys = []

            excluded_keys = getattr(type_, "__exclude__", [])

            # if the type inherits from another mapped type, then it may have
            # generated resolvers. These will be treated by dataclasses as having
            # a default value, which will likely cause issues because of keys
            # that don't have default values. To fix this, we wrap them in
            # `strawberry.field()` (like when they were originally made), so
            # dataclasses will ignore them.
            # TODO: Potentially raise/fix this issue upstream
            for key in dir(type_):
                val = getattr(type_, key)
                if getattr(val, _IS_GENERATED_RESOLVER_KEY, False):
                    setattr(type_, key, field(resolver=val))
                    generated_field_keys.append(key)

            self._handle_columns(mapper, type_, excluded_keys, generated_field_keys)
            relationship: RelationshipProperty
            for key, relationship in mapper.relationships.items():
                if (
                    key in excluded_keys
                    or key in type_.__annotations__
                    or hasattr(type_, key)
                ):
                    continue
                strawberry_type = self._convert_relationship_to_strawberry_type(
                    relationship
                )
                self._add_annotation(
                    type_,
                    key,
                    strawberry_type,
                    generated_field_keys,
                )
                sqlalchemy_field = cast(
                    StrawberryField,
                    field(resolver=self.connection_resolver_for(relationship)),
                )
                assert not sqlalchemy_field.init
                setattr(
                    type_,
                    key,
                    sqlalchemy_field,
                )
            for key, descriptor in mapper.all_orm_descriptors.items():
                if (
                    key in excluded_keys
                    or key in type_.__annotations__
                    or hasattr(type_, key)
                ):
                    continue
                if key in mapper.columns or key in mapper.relationships:
                    continue
                if key in model.__annotations__:
                    annotation = ast.literal_eval(model.__annotations__[key])
                    for (  # type: ignore[assignment]
                        sqlalchemy_type,
                        strawberry_type,
                    ) in self.sqlalchemy_type_to_strawberry_type_map.items():
                        if isinstance(annotation, sqlalchemy_type):
                            self._add_annotation(
                                type_, key, strawberry_type, generated_field_keys
                            )
                            break
                elif isinstance(descriptor, AssociationProxy):
                    strawberry_type = self._get_association_proxy_annotation(  # type: ignore[assignment]
                        mapper, key, descriptor
                    )
                    if strawberry_type is SkipTypeSentinel:
                        continue
                    self._add_annotation(
                        type_, key, strawberry_type, generated_field_keys
                    )
                    sqlalchemy_field = cast(
                        StrawberryField,
                        field(
                            resolver=self.association_proxy_resolver_for(
                                mapper, descriptor, strawberry_type  # type: ignore[arg-type]
                            )
                        ),
                    )
                    assert not sqlalchemy_field.init
                    setattr(type_, key, sqlalchemy_field)
                elif isinstance(descriptor, hybrid_property):
                    if (
                        not hasattr(descriptor, "__annotations__")
                        or "return" not in descriptor.__annotations__
                    ):
                        raise HybridPropertyNotAnnotated(key)
                    annotation = descriptor.__annotations__["return"]
                    if isinstance(annotation, str):
                        try:
                            if "typing" in annotation:
                                # Try to evaluate from existing typing imports
                                annotation = annotation[7:]
                            annotation = ast.literal_eval(annotation)
                        except NameError:
                            raise UnsupportedDescriptorType(key)
                    self._add_annotation(
                        type_,
                        key,
                        annotation,
                        generated_field_keys,
                    )
                else:
                    raise UnsupportedDescriptorType(key)

            # ignore inherited `is_type_of`
            if "is_type_of" not in type_.__dict__:
                type_.is_type_of = (
                    lambda obj, info: type(obj) == model or type(obj) == type_
                )

            # Default querying methods for relay
            if issubclass(type_, relay.Node):
                for attr, func in [
                    ("resolve_id", resolve_model_id),
                    ("resolve_id_attr", resolve_model_id_attr),
                    ("resolve_node", resolve_model_node),
                    ("resolve_nodes", resolve_model_nodes),
                ]:
                    existing_resolver = getattr(type_, attr, None)
                    if (
                        existing_resolver is None
                        or existing_resolver.__func__
                        is getattr(relay.Node, attr).__func__
                    ):
                        setattr(
                            type_,
                            attr,
                            types.MethodType(func, type_),  # type: ignore[arg-type]
                        )

                    # Adjust types that inherit from other types/interfaces that implement Node
                    # to make sure they pass themselves as the node type
                    meth = getattr(type_, attr)
                    if (
                        isinstance(meth, types.MethodType)
                        and meth.__self__ is not type_
                    ):
                        setattr(
                            type_,
                            attr,
                            types.MethodType(cast(classmethod, meth).__func__, type_),
                        )

            # need to make fields that are already in the type
            # (prior to mapping) appear *after* the mapped fields
            # because the pre-existing fields might have default values,
            # which will cause the mapped fields to fail
            # (because they may not have default values)
            type_.__annotations__.update(old_annotations)

            if make_interface:
                mapped_type = strawberry.interface(type_)
                self.mapped_interfaces[type_.__name__] = mapped_type
            elif use_federation:
                mapped_type = strawberry.federation.type(type_)
                self.mapped_types[type_.__name__] = mapped_type
            else:
                mapped_type = strawberry.type(type_)
                self.mapped_types[type_.__name__] = mapped_type

            setattr(
                type_,
                StrawberrySQLAlchemyType.TYPE_KEY_NAME,
                StrawberrySQLAlchemyType(
                    mapper=self,
                    model=model,
                ),
            )
            setattr(mapped_type, _GENERATED_FIELD_KEYS_KEY, generated_field_keys)
            setattr(mapped_type, _ORIGINAL_TYPE_KEY, type_)
            return mapped_type

        return convert

    def interface(self, model: Type[BaseModelType]) -> Callable[[Type[object]], Any]:
        """
        Decorate a type with this to register it as a strawberry interface for
        the given SQLAlchemy model.
        """
        if (
            not self._is_model_polymorphic(model)
            or self._get_polymorphic_base_model(model) != model
        ):
            raise InterfaceModelNotPolymorphic(model)
        return self.type(model, make_interface=True)

    def finalize(self) -> None:
        """
        Finalize right before initializing the strawberry Schema.
        Not performing this step may result in confusing errors
        from graphql-core and/or strawberry.
        """
        self._map_unmapped_relationships()
        self._fix_annotation_namespaces()

    def _fix_annotation_namespaces(self) -> None:
        """
        Modify the namespaces of the fields of the generated types by this
        mapper to include references to *other* generated types by this mapper,
        so that the types of relationships can resolve to generated types that
        may not be in the module of the referring type.
        """
        for mapped_type in chain(
            self.mapped_types.values(),
            self.mapped_interfaces.values(),
            self.edge_types.values(),
            self.connection_types.values(),
        ):
            strawberry_definition = get_object_definition(mapped_type, strict=True)
            for f in strawberry_definition.fields:
                if f.name in getattr(mapped_type, _GENERATED_FIELD_KEYS_KEY):
                    namespace = {}
                    if hasattr(mapped_type, _ORIGINAL_TYPE_KEY):
                        namespace.update(
                            sys.modules[
                                getattr(mapped_type, _ORIGINAL_TYPE_KEY).__module__
                            ].__dict__
                        )
                    namespace.update(self.mapped_types)
                    namespace.update(self.mapped_interfaces)
                    namespace.update(self.edge_types)
                    namespace.update(self.connection_types)
                    if f.type_annotation is not None:
                        f.type_annotation.namespace = namespace
                    else:
                        f.type_annotation = StrawberryAnnotation(
                            f.type, namespace=namespace
                        )

    def _map_unmapped_relationships(self) -> None:
        """
        Map strawberry types and interfaces for (transitively) related models.
        """
        unmapped_model_found = True
        while unmapped_model_found:
            unmapped_models = set()
            unmapped_interface_models = set()
            for model in self._related_type_models:
                type_name = self.model_to_type_name(model)
                if type_name not in self.mapped_types:
                    unmapped_models.add(model)
            for model in self._related_interface_models:
                type_name = self.model_to_interface_name(model)
                if type_name not in self.mapped_interfaces:
                    unmapped_interface_models.add(model)
            for model in unmapped_models:
                self.type(model)(type(self.model_to_type_name(model), (object,), {}))
            for model in unmapped_interface_models:
                self.interface(model)(
                    type(self.model_to_interface_name(model), (object,), {})
                )
            unmapped_model_found = (
                len(unmapped_models) > 0 or len(unmapped_interface_models) > 0
            )
