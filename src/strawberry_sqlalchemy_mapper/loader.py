import logging
from collections import defaultdict
from typing import (
    Any,
    AsyncContextManager,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

from sqlalchemy import select, tuple_
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import RelationshipProperty, Session
from strawberry.dataloader import DataLoader

from strawberry_sqlalchemy_mapper.exc import InvalidLocalRemotePairs


class StrawberrySQLAlchemyLoader:
    """
    Creates DataLoader instances on-the-fly for SQLAlchemy relationships
    """

    _loaders: Dict[RelationshipProperty, DataLoader]

    def __init__(
        self,
        bind: Union[Session, Connection, None] = None,
        async_bind_factory: Optional[
            Union[
                Callable[[], AsyncContextManager[AsyncSession]],
                Callable[[], AsyncContextManager[AsyncConnection]],
            ]
        ] = None,
    ) -> None:
        self._loaders = {}
        self._bind = bind
        self._async_bind_factory = async_bind_factory
        self._logger = logging.getLogger("strawberry_sqlalchemy_mapper")
        if bind is None and async_bind_factory is None:
            self._logger.warning(
                "One of bind or async_bind_factory must be set for loader to function properly."
            )

    async def _scalars_all(self, *args, query_secondary_tables=False, **kwargs):
        # query_secondary_tables explanation:
        # We need to retrieve values from both the self_model and related_model.
        # To achieve this, we must disable the default SQLAlchemy optimization
        # that returns only related_model values.
        # This is necessary because we use the keys variable
        # to match both related_model and self_model.
        if self._async_bind_factory:
            async with self._async_bind_factory() as bind:
                if query_secondary_tables:
                    return (await bind.execute(*args, **kwargs)).all()
                return (await bind.scalars(*args, **kwargs)).all()
        assert self._bind is not None
        if query_secondary_tables:
            return self._bind.execute(*args, **kwargs).all()
        return self._bind.scalars(*args, **kwargs).all()

    def loader_for(self, relationship: RelationshipProperty) -> DataLoader:
        """
        Retrieve or create a DataLoader for the given relationship
        """
        try:
            return self._loaders[relationship]
        except KeyError:
            related_model = relationship.entity.entity

            async def load_fn(keys: List[Tuple]) -> List[Any]:
                def _build_normal_relationship_query(related_model, relationship, keys):
                    return select(related_model).filter(
                        tuple_(
                            *[
                                remote
                                for _, remote in relationship.local_remote_pairs or []
                            ]
                        ).in_(keys)
                    )

                def _build_relationship_with_secondary_table_query(
                    related_model, relationship, keys
                ):
                    # Use another query when relationship uses a secondary table
                    self_model = relationship.parent.entity

                    if not relationship.local_remote_pairs:
                        raise InvalidLocalRemotePairs(
                            f"{related_model.__name__} -- {self_model.__name__}"
                        )

                    self_model_key_label = str(
                        relationship.local_remote_pairs[0][1].key
                    )
                    related_model_key_label = str(
                        relationship.local_remote_pairs[1][1].key
                    )

                    self_model_key = str(relationship.local_remote_pairs[0][0].key)
                    related_model_key = str(relationship.local_remote_pairs[1][0].key)

                    remote_to_use = relationship.local_remote_pairs[0][1]
                    query_keys = tuple([item[0] for item in keys])

                    # This query returns rows in this format -> (self_model.key, related_model)
                    return (
                        select(
                            getattr(self_model, self_model_key).label(
                                self_model_key_label
                            ),
                            related_model,
                        )
                        .join(
                            relationship.secondary,
                            getattr(relationship.secondary.c, related_model_key_label)
                            == getattr(related_model, related_model_key),
                        )
                        .join(
                            self_model,
                            getattr(relationship.secondary.c, self_model_key_label)
                            == getattr(self_model, self_model_key),
                        )
                        .filter(remote_to_use.in_(query_keys))
                    )

                query = (
                    _build_normal_relationship_query(related_model, relationship, keys)
                    if relationship.secondary is None
                    else _build_relationship_with_secondary_table_query(
                        related_model, relationship, keys
                    )
                )

                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)

                if relationship.secondary is not None:
                    # We need to retrieve values from both the self_model and related_model.
                    # To achieve this, we must disable the default SQLAlchemy optimization
                    # that returns only related_model values.
                    # This is necessary because we use the keys variable
                    # to match both related_model and self_model.
                    rows = await self._scalars_all(query, query_secondary_tables=True)
                else:
                    rows = await self._scalars_all(query)

                def group_by_remote_key(row: Any) -> Tuple:
                    return tuple(
                        [
                            getattr(row, remote.key)
                            for _, remote in relationship.local_remote_pairs or []
                            if remote.key
                        ]
                    )

                grouped_keys: Mapping[Tuple, List[Any]] = defaultdict(list)
                if relationship.secondary is None:
                    for row in rows:
                        grouped_keys[group_by_remote_key(row)].append(row)
                else:
                    for row in rows:
                        grouped_keys[(row[0],)].append(row[1])

                if relationship.uselist:
                    return [grouped_keys[key] for key in keys]
                else:
                    return [
                        grouped_keys[key][0] if grouped_keys[key] else None
                        for key in keys
                    ]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
