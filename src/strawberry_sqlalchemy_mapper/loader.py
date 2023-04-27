from collections import defaultdict
import functools
from typing import Any, Dict, List, Mapping, Tuple

from sqlalchemy import select, tuple_
from sqlalchemy.orm import RelationshipProperty
from strawberry.dataloader import DataLoader


class StrawberrySQLAlchemyLoader:
    """
    Creates DataLoader instances on-the-fly for SQLAlchemy relationships
    """

    _loaders: Dict[RelationshipProperty, DataLoader]

    def __init__(self, bind) -> None:
        self._loaders = {}
        self.bind = bind

    def loader_for_mapped_type(
        self, relationship: RelationshipProperty, mapper: Any, **kwargs
    ) -> DataLoader:
        def constructor(row):
            # Does this work for interfaces?
            # We need to calculate type_ here, rather than outside the closure, so as not
            # to depend on the order of type mapping. The relationship type might not be
            # mapped at the point the loader is created, but should be by the time it runs.
            type_ = mapper.mapped_types[
                mapper.model_to_type_name(relationship.entity.entity)
            ]
            return type_.from_row(row, **kwargs)

        return self.loader_for(relationship, constructor=constructor)

    def loader_for(
        self, relationship: RelationshipProperty, constructor=None
    ) -> DataLoader:
        """
        Retrieve or create a DataLoader for the given relationship
        """
        if constructor is None:
            constructor = lambda x: x
        try:
            return self._loaders[relationship]
        except KeyError:
            related_model = relationship.entity.entity

            async def load_fn(keys: List[Tuple]) -> List[Any]:
                query = select(related_model).filter(
                    tuple_(
                        *[remote for _, remote in relationship.local_remote_pairs]
                    ).in_(keys)
                )
                if relationship.order_by:
                    query = query.order_by(*relationship.order_by)
                rows = self.bind.scalars(query).all()

                def group_by_remote_key(row: Any) -> Tuple:
                    return tuple(
                        [
                            getattr(row, remote.key)
                            for _, remote in relationship.local_remote_pairs
                        ]
                    )

                grouped_keys: Mapping[Tuple, List[Any]] = defaultdict(list)
                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)
                if relationship.uselist:
                    return [constructor(grouped_keys[key]) for key in keys]
                else:
                    return [
                        constructor(grouped_keys[key][0]) if grouped_keys[key] else None
                        for key in keys
                    ]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
