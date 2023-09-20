import asyncio
import contextvars
import functools
from collections import defaultdict
from typing import Any, Dict, List, Mapping, Tuple, Union

from sqlalchemy import select, tuple_
from sqlalchemy.engine.base import Connection
from sqlalchemy.orm import RelationshipProperty, Session
from strawberry.dataloader import DataLoader


class StrawberrySQLAlchemyLoader:
    """
    Creates DataLoader instances on-the-fly for SQLAlchemy relationships
    """

    _loaders: Dict[RelationshipProperty, DataLoader]

    def __init__(self, bind: Union[Session, Connection], executor=None) -> None:
        self._loaders = {}
        self.bind = bind
        self.executor = executor

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

                loop = asyncio.events.get_running_loop()
                ctx = contextvars.copy_context()
                func_call = functools.partial(ctx.run, self.bind.scalars(query).all)
                rows = await loop.run_in_executor(self.executor, func_call)

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
