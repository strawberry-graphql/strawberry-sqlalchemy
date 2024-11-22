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

from sqlalchemy import select, tuple_, label
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import RelationshipProperty, Session
from strawberry.dataloader import DataLoader


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

    async def _scalars_all(self, *args, disabled_optimization_to_secondary_tables=False, **kwargs):
        if self._async_bind_factory:
            async with self._async_bind_factory() as bind:
                if disabled_optimization_to_secondary_tables is True:
                    return (await bind.execute(*args, **kwargs)).all()
                return (await bind.scalars(*args, **kwargs)).all()
        else:
            assert self._bind is not None
            if disabled_optimization_to_secondary_tables is True:
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
                if relationship.secondary is None:
                    query = select(related_model).filter(
                        tuple_(
                            *[remote for _, remote in relationship.local_remote_pairs or []]
                        ).in_(keys)
                    )
                else:
                    # Use another query when relationship uses a secondary table
                    # *[remote[1] for remote in relationship.local_remote_pairs or []]
                    self_model = relationship.parent.entity

                    self_model_key_label = relationship.local_remote_pairs[0][1].key
                    related_model_key_label = relationship.local_remote_pairs[1][1].key

                    self_model_key = relationship.local_remote_pairs[0][0].key
                    # breakpoint()
                    # Gets the
                    remote_to_use = relationship.local_remote_pairs[0][1]
                    query_keys = tuple([item[0] for item in keys])
                    breakpoint()
                    query = (
                        # select(related_model)
                        select(
                            label(self_model_key_label, getattr(
                                self_model, self_model_key)),
                            related_model
                        )
                        # .join(
                        #     related_model,
                        #     getattr(relationship.secondary.c, related_model_key_label) == getattr(
                        #         related_model, related_model_key)
                        # )
                        # .join(
                        #     relationship.secondary,
                        #     getattr(relationship.secondary.c, self_model_key_label) == getattr(
                        #         self_model, self_model_key)
                        # )
                        # .join(
                        #     relationship.secondary,
                        #     getattr(relationship.secondary.c, self_model_key_label) == getattr(
                        #         self_model, self_model_key)
                        # )
                        .join(
                            relationship.secondary,  # Join the secondary table
                            getattr(relationship.secondary.c, related_model_key_label) == related_model.id  # Match department_id
                        )
                        .join(
                            self_model,  # Join the Employee table
                            getattr(relationship.secondary.c, self_model_key_label) == self_model.id  # Match employee_id
                        )
                        .filter(
                            remote_to_use.in_(query_keys)
                        )
                    )
                    # query = (
                    #     # select(related_model)
                    #     select(
                    #         related_model,
                    #         label(self_model_key_label, getattr(self_model, self_model_key))
                    #     )
                    #     .join(relationship.secondary, relationship.secondaryjoin)
                    #     .filter(
                    #         remote_to_use.in_(query_keys)
                    #     )
                    # )

                    # query = (
                    #     select(related_model)
                    #     .join(relationship.secondary, relationship.secondaryjoin)
                    #     .filter(
                    #         # emote_to_use.in_(keys)
                    #         tuple_(
                    #             *[remote[1] for remote in relationship.local_remote_pairs or []]
                    #         ).in_(keys)
                    #     )
                    # )

                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)

                if relationship.secondary is not None:
                    # We need get the self_model values too, so we need to remove the slqalchemy optimization that returns only the related_model values, this is needed because we use the keys var to match the related_model and the self_model
                    rows = await self._scalars_all(query, disabled_optimization_to_secondary_tables=True)
                else:
                    rows = await self._scalars_all(query)

                def group_by_remote_key(row: Any) -> Tuple:
                    if relationship.secondary is None:
                        return tuple(
                            [
                                getattr(row, remote.key)
                                for _, remote in relationship.local_remote_pairs or []
                                if remote.key
                            ]
                        )
                    else:
                        # Use another query when relationship uses a secondary table
                        # breakpoint()
                        related_model_table = relationship.entity.entity.__table__
                        # breakpoint()
                        # return tuple(
                        #     [
                        #         getattr(row, remote[0].key)
                        #         for remote in relationship.local_remote_pairs or []
                        #         if remote[0].key is not None and remote[0].table == related_model_table
                        #     ]
                        # )
                        result = []
                        for remote in relationship.local_remote_pairs or []:
                            if remote[0].key is not None and relationship.local_remote_pairs[1][0].table == related_model_table:
                                result.extend(
                                    [

                                        getattr(row, remote[0].key)

                                    ]
                                )
                        breakpoint()
                        return tuple(
                            [
                                getattr(row, remote[0].key)
                                for remote in relationship.local_remote_pairs or []
                                if remote[0].key is not None and relationship.local_remote_pairs[1][0].table == related_model_table
                            ]
                        )

                grouped_keys: Mapping[Tuple, List[Any]] = defaultdict(list)
                breakpoint()
                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)

                breakpoint()
                if relationship.uselist:
                    return [grouped_keys[key] for key in keys]
                else:
                    return [
                        grouped_keys[key][0] if grouped_keys[key] else None
                        for key in keys
                    ]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
