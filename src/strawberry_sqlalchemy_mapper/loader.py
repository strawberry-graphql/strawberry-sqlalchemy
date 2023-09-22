import logging
from collections import defaultdict
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple, Union

from sqlalchemy import select, tuple_
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
            Callable[[], Union[AsyncSession, AsyncConnection]]
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
        if bind is not None:
            # For anyone coming here because of this warning:
            # Making blocking database calls from within an async function (the resolver) has
            # catastrophic performance implications. Not only will all resolvers be effectively
            # serialized, any other coroutines waiting on the event loop (e.g. concurrent requests
            # in a web server), will be blocked as well, grinding your entire service to a halt.
            self._logger.warning(
                "`bind` parameter is deprecated due to performance issues. Use `async_bind_factory` instead."
            )

    async def _scalars(self, *args, **kwargs):
        if self._async_bind_factory:
            async with self._async_bind_factory() as bind:
                return await bind.scalars(*args, **kwargs)
        else:
            # Deprecated, but supported for now.
            assert self._bind is not None
            return self._bind.scalars(*args, **kwargs)

    def loader_for(self, relationship: RelationshipProperty) -> DataLoader:
        """
        Retrieve or create a DataLoader for the given relationship
        """
        try:
            return self._loaders[relationship]
        except KeyError:
            related_model = relationship.entity.entity

            async def load_fn(keys: List[Tuple]) -> List[Any]:
                query = select(related_model).filter(
                    tuple_(
                        *[remote for _, remote in relationship.local_remote_pairs or []]
                    ).in_(keys)
                )
                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)
                rows = (await self._scalars(query)).all()

                def group_by_remote_key(row: Any) -> Tuple:
                    return tuple(
                        [
                            getattr(row, remote.key)
                            for _, remote in relationship.local_remote_pairs or []
                            if remote.key
                        ]
                    )

                grouped_keys: Mapping[Tuple, List[Any]] = defaultdict(list)
                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)
                if relationship.uselist:
                    return [grouped_keys[key] for key in keys]
                else:
                    return [
                        grouped_keys[key][0] if grouped_keys[key] else None
                        for key in keys
                    ]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
