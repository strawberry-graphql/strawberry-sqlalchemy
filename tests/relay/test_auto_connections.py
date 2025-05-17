from typing import Any

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import relationship
from strawberry.relay.utils import to_base64
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper
from strawberry_sqlalchemy_mapper.loader import StrawberrySQLAlchemyLoader


@pytest.fixture
def user_and_group_tables(base: Any):
    class User(base):
        __tablename__ = "user"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String(50), nullable=False)
        group_id = Column(Integer, ForeignKey("group.id"))
        group = relationship("Group", back_populates="users")

    class Group(base):
        __tablename__ = "group"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String, nullable=False)
        users = relationship("User", back_populates="group")

    return User, Group


@pytest.mark.asyncio
async def test_query_auto_generated_connection(
    base: Any,
    async_engine: AsyncEngine,
    async_sessionmaker,
    user_and_group_tables,
):
    user_table, group_table = user_and_group_tables

    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    mapper = StrawberrySQLAlchemyMapper()

    global User, Group
    try:

        @mapper.type(user_table)
        class User: ...

        @mapper.type(group_table)
        class Group: ...

        @strawberry.type
        class Query:
            @strawberry.field
            async def group(self, id: strawberry.ID) -> Group:
                session = async_sessionmaker()
                return await session.get(group_table, int(id))

        schema = strawberry.Schema(query=Query)

        query = """\
        query GetGroup ($id: ID!) {
          group(id: $id) {
            id
            name
            users {
              pageInfo {
                hasNextPage
                hasPreviousPage
                startCursor
                endCursor
              }
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
        }
        """

        async with async_sessionmaker(expire_on_commit=False) as session:
            group = group_table(name="Foo Bar")
            user1 = user_table(name="User 1", group=group)
            user2 = user_table(name="User 2", group=group)
            user3 = user_table(name="User 3", group=group)
            session.add_all([group, user1, user2, user3])
            await session.commit()

            result = await schema.execute(
                query,
                variable_values={"id": group.id},
                context_value={
                    "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                        async_bind_factory=async_sessionmaker
                    )
                },
            )
            assert result.errors is None
            assert result.data == {
                "group": {
                    "id": group.id,
                    "name": "Foo Bar",
                    "users": {
                        "pageInfo": {
                            "hasNextPage": False,
                            "hasPreviousPage": False,
                            "startCursor": to_base64("arrayconnection", "0"),
                            "endCursor": to_base64("arrayconnection", "2"),
                        },
                        "edges": [
                            {"node": {"id": user1.id, "name": "User 1"}},
                            {"node": {"id": user2.id, "name": "User 2"}},
                            {"node": {"id": user3.id, "name": "User 3"}},
                        ],
                    },
                },
            }
    finally:
        del User, Group
