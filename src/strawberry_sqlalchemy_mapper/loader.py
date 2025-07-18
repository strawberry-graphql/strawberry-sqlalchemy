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
    cast,
)

from sqlalchemy import select, tuple_, func
from sqlalchemy.engine.base import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
from sqlalchemy.orm import RelationshipProperty, Session
from strawberry import relay
from strawberry.dataloader import DataLoader
from base64 import b64decode


def _decode_cursor_index(cursor: str) -> Optional[int]:
    try:
        cursor = b64decode(cursor).decode('utf-8')
        if cursor.startswith('arrayconnection:'):
            return int(cursor.split(':')[1])
    except (ValueError, IndexError):
        # If decoding fails, default to no offset
        pass
    return None


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

    async def _scalars_all(self, *args, **kwargs):
        if self._async_bind_factory:
            async with self._async_bind_factory() as bind:
                return (await bind.scalars(*args, **kwargs)).all()
        else:
            assert self._bind is not None
            return self._bind.scalars(*args, **kwargs).all()

    def loader_for(self, relationship: RelationshipProperty) -> DataLoader:
        """
        Retrieve or create a DataLoader for the given relationship
        """
        try:
            return self._loaders[relationship]
        except KeyError:
            related_model = relationship.entity.entity

            async def load_fn(
                keys: List[Tuple],
                first: Optional[int] = None,
                after: Optional[str] = None,
                last: Optional[int] = None,
                before: Optional[str] = None,
            ) -> List[Any]:
                query = select(related_model).filter(
                    tuple_(*[remote for _, remote in relationship.local_remote_pairs or []]).in_(
                        keys
                    )
                )
                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)

                # Validate input combinations according to Relay spec
                if first is not None and last is not None:
                    raise ValueError("Cannot provide both 'first' and 'last'")
                if first is not None and before is not None:
                    raise ValueError("Cannot provide both 'first' and 'before'")
                if last is not None and after is not None:
                    raise ValueError("Cannot provide both 'last' and 'after'")

                # Extract offset from cursor if provided
                offset = 0
                if after:
                    decoded_after = _decode_cursor_index(after)
                    if decoded_after is not None and decoded_after >= 0:
                        offset = decoded_after + 1

                # For before/last pagination, we need to handle differently
                # First, we need to determine the total count and before index
                before_index: Optional[int] = None
                if before:
                    decoded_before = _decode_cursor_index(before)
                    if decoded_before is not None:
                        before_index = decoded_before

                if last is not None:
                    # For just 'last' without 'before', we need the last N items
                    # Get total count first
                    count_query = select(func.count()).select_from(
                        select(related_model).filter(
                            tuple_(*[remote for _, remote in relationship.local_remote_pairs or []]).in_(
                                keys
                            )
                        ).subquery()
                    )
                    sub_result = await self._scalars_all(count_query)
                    total_count = sub_result[0] if sub_result else 0

                    if before_index is not None:
                        # If before_index is provided, we need to calculate how many items are before that index
                        items_before_cursor = min(before_index, total_count)

                        # Calculate the offset to get last N items before the cursor
                        offset = max(0, items_before_cursor - last)
                        limit = min(last, items_before_cursor)

                        # Apply the calculated offset and limit
                        if offset > 0:
                            query = query.offset(offset)
                        if limit > 0:
                            query = query.limit(limit)

                    else:

                        # Calculate offset for last N items
                        offset = max(0, total_count - last)
                        if offset > 0:
                            query = query.offset(offset)
                        if last > 0:
                            query = query.limit(last)

                elif before_index is not None:
                    # If just 'before' without 'last', retrieve all items before the cursor
                    if before_index > 0:
                        query = query.limit(before_index)

                else:
                    # Standard forward pagination with first/after
                    if offset > 0:
                        query = query.offset(offset)
                    if first is not None and first >= 0:
                        query = query.limit(first)

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
                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)
                if relationship.uselist:
                    return [grouped_keys[key] for key in keys]
                else:
                    return [grouped_keys[key][0] if grouped_keys[key] else None for key in keys]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
