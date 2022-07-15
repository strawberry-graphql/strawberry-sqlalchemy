from collections import defaultdict
from typing import Any, Dict, List, Mapping, Tuple

from sqlalchemy import desc, func, literal_column, over, select, tuple_
from sqlalchemy.orm import RelationshipProperty, aliased
from strawberry.dataloader import DataLoader

from strawberry_sqlalchemy_mapper.relay import (
    PageInfo,
    PagingList,
    RelativePageInput,
    cursor_from_obj,
)


class StrawberrySQLAlchemyLoader:
    """
    Creates DataLoader instances on-the-fly for SQLAlchemy relationships
    """

    _loaders: Dict[RelationshipProperty, DataLoader]

    def __init__(self, bind) -> None:
        self._loaders = {}
        self.bind = bind

    def loader_for(self, relationship: RelationshipProperty) -> DataLoader:
        """
        Retrieve or create a DataLoader for the given relationship
        """
        try:
            return self._loaders[relationship]
        except KeyError:
            related_model = relationship.entity.entity

            async def load_fn(keys: List[Tuple]) -> List[Any]:
                page_input: RelativePageInput = keys[0][0]

                keys = [k[1] for k in keys]
                query = select(related_model).filter(
                    tuple_(
                        *[remote for _, remote in relationship.local_remote_pairs]
                    ).in_(keys)
                )

                if page_input:
                    after = 0
                    # Create a page_input to get all desired pages in a single one.
                    # The idea is to group rows by position for each keys.
                    #
                    # Given a set of 3 keys, the result order should look like this:
                    # 1 - row 1 for key 1
                    # 2 - row 1 for key 2
                    # 3 - row 1 for key 3
                    # 4 - row 2 for key 1
                    # 5 - row 2 for key 2
                    # .
                    # .
                    # n - row n//3 + 1 for key n%3 * (n%3/max(n%3, 1) or 3)
                    #
                    # Given this order,
                    # we can add row count column (using row_number())
                    # on which a where clause will be used to find rows
                    # after/before relative position.
                    if page_input.first is not None:
                        first = page_input.first
                        if page_input.after is not None:
                            after = page_input.after
                        backward = False

                    else:
                        # mypy
                        assert page_input.last is not None

                        first = page_input.last
                        if page_input.before is not None:
                            after = abs(page_input.before)

                        backward = True

                    # Add a column to enumerate related objects for each parent
                    remote_key = relationship.local_remote_pairs[0][1]
                    related_mapper = related_model.__mapper__
                    pks = [
                        related_mapper.get_property_by_column(col)
                        for col in related_mapper.primary_key
                    ]
                    if backward:
                        order_by = desc(pks[0])
                    else:
                        order_by = pks[0]
                    group_num = over(
                        func.row_number(), partition_by=remote_key, order_by=order_by
                    ).label("group_num")
                    query_a = query.add_columns(group_num)
                    query_a = query_a.order_by(group_num, remote_key).cte("base_query")

                    # Final query
                    # use aliased to construct orm instances from subquery results
                    statement = select(
                        aliased(related_model, query_a), literal_column("group_num")
                    ).order_by("group_num", remote_key.name)

                    extra_firsts = 1

                    if after:
                        statement = statement.where(
                            query_a.c.group_num >= max(after - 1, 0)
                        )
                        extra_firsts += 1
                    statement = statement.where(
                        query_a.c.group_num <= first + extra_firsts
                    )

                    res = await self.bind.execute(statement)
                    rows = res.all()
                else:
                    if relationship.order_by:
                        query = query.order_by(*relationship.order_by)

                    res = await self.bind.execute(query)
                    rows = res.all()

                def group_by_remote_key(row: Any) -> Tuple:
                    return tuple(
                        [
                            getattr(row[0], remote.key)
                            for _, remote in relationship.local_remote_pairs
                        ]
                    )

                def key_page(objects: PagingList) -> PagingList:
                    """Paginate each list to trim extra rows that were
                    fetched for has_next/has_previous.
                    """
                    if not page_input or not objects:
                        return PagingList([o[0] for o in objects])

                    page_info = PageInfo.empty_page()
                    page = PagingList()

                    for obj, group_num in objects:
                        if group_num <= after:
                            page_info.has_previous_page = True
                        elif group_num > after + first:
                            page_info.has_next_page = True
                        elif isinstance(obj, tuple):
                            page.append(obj[0])
                        else:
                            page.append(obj)

                    if backward:
                        page_info.has_previous_page = not page_info.has_previous_page
                        page_info.has_next_page = not page_info.has_next_page
                        page.reverse()

                    if page:
                        page_info.start_cursor = cursor_from_obj(page[0])
                        page_info.end_cursor = cursor_from_obj(page[-1])

                    page.set_page_info(page_info)
                    return page

                grouped_keys: Mapping[Tuple, PagingList] = defaultdict(PagingList)

                for row in rows:
                    grouped_keys[group_by_remote_key(row)].append(row)
                if relationship.uselist:
                    return [key_page(grouped_keys[key]) for key in keys]
                else:
                    return [
                        grouped_keys[key][0][0] if grouped_keys[key] else None
                        for key in keys
                    ]

            self._loaders[relationship] = DataLoader(load_fn=load_fn)
            return self._loaders[relationship]
