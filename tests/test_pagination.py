import random
from typing import Any, Dict, Optional

import hypothesis
import strawberry
from conftest import Model, TxManager
from hypothesis import given
from hypothesis import strategies as st
from sqlalchemy import Column, ForeignKey, Integer, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import relationship, selectinload

from strawberry_sqlalchemy_mapper import (
    StrawberrySQLAlchemyLoader,
    StrawberrySQLAlchemyMapper,
)
from strawberry_sqlalchemy_mapper.relay import (
    ConnectionMixin,
    Node,
    PageInput,
    connection,
    cursor_from_obj,
)

gql_mapper = StrawberrySQLAlchemyMapper(
    model_to_type_name=lambda name: f"{name.__name__}Type"
)


def session_context(session: AsyncSession) -> Dict[str, Any]:
    """Return a dict to merge into the execution context

    Args:
        session: The session used to build the context

    Returns:
        A dict to merge into the strawberry execution context
    """
    return {
        "session": session,
        "sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session),
    }


class Parent(Model):
    id = Column("id", Integer, primary_key=True)
    children = relationship("Child")


class Child(Model):
    id = Column("id", Integer, primary_key=True)
    parent_id = Column(Integer, ForeignKey("parent.id"))


@gql_mapper.type(Parent)
class ParentType(Node, ConnectionMixin):
    id: strawberry.ID


@gql_mapper.create_input(Parent)
class ParentCreate:
    __exclude__ = ["id"]


@gql_mapper.update_input(Parent)
class ParentUpdate:
    pass


@gql_mapper.type(Child)
class ChildType(Node):
    id: strawberry.ID


@gql_mapper.create_input(Child)
class ChildCreate:
    __exclude__ = ["id"]


@gql_mapper.update_input(Child)
class ChildUpdate:
    pass


@strawberry.type
class Query:
    @strawberry.field
    async def parents(info, page_input: Optional[PageInput]) -> ParentType.Connection:
        query = select(Parent).order_by(Parent.id)
        return await connection(
            query, page_input=page_input, connection=ParentType.Connection, info=info
        )


gql_mapper.finalize()
schema = strawberry.Schema(query=Query)


def page_input_st(cursors) -> st.SearchStrategy:
    forward_st = st.fixed_dictionaries(
        mapping={"first": st.integers(min_value=0, max_value=2**31 - 2)},
        optional={"after": st.sampled_from(cursors)} if cursors else None,
    )
    backward_st = st.fixed_dictionaries(
        mapping={"last": st.integers(min_value=0, max_value=2**31 - 2)},
        optional={"before": st.sampled_from(cursors)} if cursors else None,
    )
    return st.one_of(forward_st, backward_st)


def sub_page_input_st() -> st.SearchStrategy:
    forward_st = st.fixed_dictionaries(
        mapping={"first": st.integers(min_value=0, max_value=2**31 - 2)},
        optional={"after": st.integers(min_value=0, max_value=2**31 - 2)},
    )
    backward_st = st.fixed_dictionaries(
        mapping={"last": st.integers(min_value=0, max_value=2**31 - 2)},
        optional={"before": st.integers(min_value=-(2**31) - 2, max_value=-1)},
    )
    return st.one_of(forward_st, backward_st)


async def parents_from_page_input(
    page_input: PageInput, cursor_map: Dict[str, int], session: AsyncSession
):
    """Get parents objects corresponding to page_input.

    Args:
        page_input: Cursor page definition
        cursor_map: Cursors that can be used in after/before params
        session: AsyncSession to use when executing the query

    Returns:
        Scalar results matching the page_input
    """
    query = select(Parent).options(selectinload(Parent.children))

    if "after" in page_input:
        query = query.where(Parent.id > cursor_map[page_input["after"]])
    elif "before" in page_input:
        query = query.where(Parent.id < cursor_map[page_input["before"]])

    if "first" in page_input:
        query = query.order_by(Parent.id).limit(page_input["first"])
        result = await session.execute(query)
        return result.scalars().all()
    else:
        query = query.order_by(desc(Parent.id)).limit(page_input["last"])
        result = await session.execute(query)
        return reversed(result.scalars().all())


def assert_sub_pagination(objects: list, page: list, page_input: dict) -> None:
    """Assert page correspond to a sublist of objects defined by page_input.

    Args:
        objects: List from which the page is queried
        page: Page to assert
        page_input: Relative page definition (first/after, last/before)
    """
    expected_page = objects

    if "first" in page_input:
        start = page_input.get("after", 0)
        stop = start + page_input["first"]
    else:
        start = page_input.get("before", None)
        if start is not None:
            stop = start
            start = start - page_input["last"]
        else:
            start = max(len(objects) - page_input["last"], 0)
            stop = None

    expected_page = objects[start:stop]
    assert page == expected_page


@given(st.data(), st.integers(min_value=0, max_value=100))
async def test_pagination(transaction: TxManager, data: st.DataObject, size: int):
    query = """
        query($pageInput: PageInput) {
            parents(pageInput: $pageInput) {
                edges {
                    node {
                        id
                    }
                }
            }
        }
    """
    objects, cursors = [], []
    cursor_map: Dict[str, int] = {}

    for i in range(size):
        parent = Parent(id=i)
        objects.append(parent)
        cursor = cursor_from_obj(parent)
        cursors.append(cursor)
        cursor_map[cursor] = i

    page_input = data.draw(page_input_st(cursors))

    async with transaction() as session:
        session.add_all(objects)
        resp = await schema.execute(
            query,
            variable_values={"pageInput": page_input},
            context_value=session_context(session),
        )

        assert resp.errors is None

        expected = await parents_from_page_input(page_input, cursor_map, session)

        node_ids = [int(e["node"]["id"]) for e in resp.data["parents"]["edges"]]

        assert node_ids == [u.id for u in expected]


@hypothesis.settings(deadline=None)
@given(
    st.data(),
    sub_page_input_st(),
    st.integers(min_value=1, max_value=100),
    st.integers(min_value=0, max_value=200),
)
async def test_nested_pagination(
    transaction: TxManager,
    data,
    sub_page_input,
    parent_size: int,
    children_size: int,
):
    query = """
        query($pageInput: PageInput, $subPageInput: RelativePageInput) {
            parents(pageInput: $pageInput) {
                edges {
                    node {
                        id
                        children(pageInput: $subPageInput) {
                            edges {
                                node {
                                    id
                                }
                            }
                        }
                    }
                }
            }
        }
    """
    objects, p_cursors = [], []
    p_cursor_map: Dict[str, int] = {}

    for i in range(parent_size):
        parent = Parent(id=i)
        objects.append(parent)
        cursor = cursor_from_obj(parent)
        p_cursors.append(cursor)
        p_cursor_map[cursor] = i

    for i in range(children_size):
        child = Child(id=i, parent_id=random.randint(0, parent_size - 1))
        objects.append(child)

    page_input = data.draw(page_input_st(p_cursors))

    async with transaction() as session:
        session.add_all(objects)

        resp = await schema.execute(
            query,
            variable_values={
                "pageInput": page_input,
                "subPageInput": sub_page_input,
            },
            context_value=session_context(session),
        )

        assert resp.errors is None

        expected_parents = await parents_from_page_input(
            page_input, p_cursor_map, session
        )
        parent_map = {p.id: [c.id for c in p.children] for p in expected_parents}

        edges = resp.data["parents"]["edges"]

        for p in edges:
            parent_children = parent_map[int(p["node"]["id"])]
            assert_sub_pagination(
                parent_children,
                [int(c["node"]["id"]) for c in p["node"]["children"]["edges"]],
                sub_page_input,
            )
