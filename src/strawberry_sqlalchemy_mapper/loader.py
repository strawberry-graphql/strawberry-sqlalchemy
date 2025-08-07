from __future__ import annotations

import logging
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
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

from sqlalchemy import func, select, tuple_
from strawberry.dataloader import DataLoader

from strawberry_sqlalchemy_mapper.pagination_cursor_utils import (
    decode_cursor_index,
)

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession
    from sqlalchemy.orm import RelationshipProperty, Session


class PaginatedLoader:
    """
    Wrapper around DataLoader that supports pagination arguments
    """

    def __init__(
        self,
        relationship: RelationshipProperty,
        load_implementation: Callable,
    ):
        self.relationship: RelationshipProperty = relationship
        self.load_implementation: Callable = load_implementation
        self._loaders: Dict[Tuple, DataLoader] = {}

    def loader_for(
        self,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
    ) -> DataLoader:
        # Filter out None values for the key
        pagination_key = tuple(
            item
            for item in (
                ("first", first) if first is not None else None,
                ("after", after) if after is not None else None,
                ("last", last) if last is not None else None,
                ("before", before) if before is not None else None,
            )
            if item is not None
        )

        # Create or retrieve a DataLoader for this specific pagination
        # configuration
        if pagination_key not in self._loaders:
            # Create a loader with a scoped load function that has access to
            # pagination args
            async def load_fn(keys: List[Any]) -> List[Any]:
                return await self.load_implementation(
                    keys=keys,
                    first=first,
                    after=after,
                    last=last,
                    before=before,
                )

            self._loaders[pagination_key] = DataLoader(load_fn=load_fn)
        return self._loaders[pagination_key]

    async def load(
        self,
        key: Any,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
    ) -> Any:
        # Use the appropriate loader
        return await self.loader_for(
            first=first,
            after=after,
            last=last,
            before=before,
        ).load(key)


class StrawberrySQLAlchemyLoader:
    """
    Creates DataLoader instances on-the-fly for SQLAlchemy relationships
    """

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
        self._loaders: Dict[RelationshipProperty, PaginatedLoader] = {}
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

    async def _scalar_one(self, *args, **kwargs):
        if self._async_bind_factory:
            async with self._async_bind_factory() as bind:
                return await bind.scalar(*args, **kwargs)
        else:
            assert self._bind is not None
            return self._bind.scalar(*args, **kwargs)

    async def _get_relationship_record_count_for_keys(
        self,
        relationship: RelationshipProperty,
        keys: List[Tuple[object, ...]],
    ) -> int:
        related_model = relationship.entity.entity
        count_query = select(func.count()).select_from(
            select(related_model)
            .filter(
                tuple_(
                    *[remote for _, remote in relationship.local_remote_pairs or []],
                ).in_(
                    keys,
                ),
            )
            .subquery(),
        )
        sub_result = await self._scalar_one(count_query)
        return cast("int", sub_result or 0)

    async def get_relationship_record_count_for_key(
        self,
        relationship: RelationshipProperty,
        key: Tuple[object, ...],
    ) -> int:
        return await self._get_relationship_record_count_for_keys(relationship, [key])

    async def _get_pagination_offset_limit(
        self,
        keys: List[Tuple[object, ...]],
        relationship: RelationshipProperty,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
    ) -> Tuple[int, int]:
        """Returns [offset, limit] for pagination.

        If either is 0, it should not be applied to the query.
        """
        # Extract offset from cursor if provided
        offset: int = 0
        limit: int = 0
        if after:
            decoded_after = decode_cursor_index(after)
            if decoded_after is not None and decoded_after >= 0:
                offset = decoded_after + 1

        # For before/last pagination, we need to handle differently
        # First, we need to determine the total count and before index
        before_index: Optional[int] = None
        if before:
            decoded_before = decode_cursor_index(before)
            if decoded_before is not None:
                before_index = decoded_before

        if last is not None:
            # For just 'last' without 'before', we need the last N items
            # Get total count first
            total_count = await self._get_relationship_record_count_for_keys(
                relationship,
                keys,
            )

            if before_index is not None:
                # If before_index is provided, we need to calculate how
                # many items are before that index
                items_before_cursor = min(before_index, total_count)

                # Calculate the offset to get last N items before the cursor
                offset = max(0, items_before_cursor - last)
                limit = min(last, items_before_cursor)
            else:
                # Calculate offset for last N items
                offset = max(0, total_count - last)
                limit = min(last, total_count)
        elif before_index is not None:
            # If just 'before' without 'last', retrieve all items
            # before the cursor
            if before_index > 0:
                limit = before_index
        else:
            # Standard forward-pagination
            if first is not None and first >= 0:
                limit = first
        return offset, limit

    def loader_for(self, relationship: RelationshipProperty) -> PaginatedLoader:
        """Retrieve or create a PaginatedLoader for the given relationship."""
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
                # Validate input combinations according to Relay spec
                if first is not None and last is not None:
                    raise ValueError("Cannot provide both 'first' and 'last'")
                if first is not None and before is not None:
                    raise ValueError("Cannot provide both 'first' and 'before'")
                if last is not None and after is not None:
                    raise ValueError("Cannot provide both 'last' and 'after'")
                query = select(related_model).filter(
                    tuple_(
                        *[remote for _, remote in relationship.local_remote_pairs or []],
                    ).in_(
                        keys,
                    ),
                )
                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)

                offset, limit = await self._get_pagination_offset_limit(
                    keys,
                    relationship,
                    first=first,
                    after=after,
                    last=last,
                    before=before,
                )

                # Apply the calculated offset and limit
                if offset > 0:
                    query = query.offset(offset)
                if limit > 0:
                    query = query.limit(limit)

                rows = await self._scalars_all(query)

                def group_by_remote_key(row: Any) -> Tuple:
                    return tuple(
                        [
                            getattr(row, remote.key)
                            for _, remote in relationship.local_remote_pairs or []
                            if remote.key
                        ],
                    )

                grouped_keys: Mapping[Tuple, List[Any]] = defaultdict(list)
                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)
                if relationship.uselist:
                    return [grouped_keys[key] for key in keys]
                return [grouped_keys[key][0] if grouped_keys[key] else None for key in keys]

            self._loaders[relationship] = PaginatedLoader(
                relationship=relationship,
                load_implementation=load_fn,
            )
            return self._loaders[relationship]
