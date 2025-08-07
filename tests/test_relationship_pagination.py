import asyncio
from typing import Any

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import Session, relationship, sessionmaker
from strawberry.types import Info
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader, StrawberrySQLAlchemyMapper


# Autouse this fixture within this module so that metadata is injected in base
@pytest.fixture(autouse=True)
def author_book_tables(base: Any):
    class Author(base):
        __tablename__ = "author"
        id = Column(Integer, autoincrement=True, primary_key=True)
        name = Column(String(50), nullable=False)
        books = relationship("Book", back_populates="author")

    class Book(base):
        __tablename__ = "book"
        id = Column(Integer, autoincrement=True, primary_key=True)
        title = Column(String(100), nullable=False)
        author_id = Column(Integer, ForeignKey("author.id"), nullable=False)
        author = relationship("Author", back_populates="books")

    return Author, Book


@pytest.fixture
def sync_session(sessionmaker: sessionmaker) -> Session:
    with sessionmaker() as session:
        yield session


@pytest.fixture
async def async_session(async_sessionmaker):
    async with async_sessionmaker(expire_on_commit=False) as session:
        yield session


@pytest.fixture
def sync_author(
    base: Any,
    engine: Engine,
    sync_session: Session,
    author_book_tables,
):
    AuthorModel, BookModel = author_book_tables
    base.metadata.create_all(engine)
    # Create test data
    author = AuthorModel(name="Test Author")
    sync_session.add(author)
    sync_session.flush()  # To get the author ID

    # Create 10 books for pagination testing
    for i in range(10):
        book = BookModel(title=f"Book {i + 1}", author_id=author.id)
        sync_session.add(book)

    sync_session.commit()
    return author


@pytest.fixture
async def async_author(
    base: Any,
    async_engine: AsyncEngine,
    async_session: AsyncSession,
    author_book_tables,
):
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    # Create test data
    AuthorModel, BookModel = author_book_tables
    author = AuthorModel(name="Test Author")
    async_session.add(author)
    await async_session.flush()  # To get the author ID

    # Create 10 books for pagination testing
    for i in range(10):
        book = BookModel(title=f"Book {i + 1}", author_id=author.id)
        async_session.add(book)

    await async_session.commit()
    return author


@pytest.fixture
def sync_session_schema(mapper: StrawberrySQLAlchemyMapper, sync_session, author_book_tables):
    AuthorModel, BookModel = author_book_tables

    @mapper.type(AuthorModel)
    class Author:
        pass

    @mapper.type(BookModel)
    class Book:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def author(self, info: Info, id: int) -> Author:
            return sync_session.scalars(select(AuthorModel).filter(AuthorModel.id == id)).first()

    mapper.finalize()
    return strawberry.Schema(query=Query)


@pytest.fixture
def async_session_schema(
    mapper: StrawberrySQLAlchemyMapper, async_session: AsyncSession, author_book_tables
):
    AuthorModel, BookModel = author_book_tables

    @mapper.type(AuthorModel)
    class Author:
        pass

    @mapper.type(BookModel)
    class Book:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        async def author(self, info: Info, id: int) -> Author:
            return (
                await async_session.scalars(select(AuthorModel).filter(AuthorModel.id == id))
            ).first()

    mapper.finalize()
    return strawberry.Schema(query=Query)


@pytest.fixture
def general_query() -> str:
    """General purpose query."""
    return """
    query($authorId: Int!, $first: Int, $after: String, $last: Int, $before: String) {
      author(id: $authorId) {
        id
        name
        books(first: $first, after: $after, last: $last, before: $before) {
          edges {
            node {
              id
              title
            }
            cursor
          }
          pageInfo {
            hasNextPage
            hasPreviousPage
            startCursor
            endCursor
          }
        }
      }
    }
    """


def test_relationship_pagination(
    sync_session: Session,
    sync_session_schema: strawberry.Schema,
    general_query: str,
    sync_author,
):
    """Test pagination on relationship fields using first and after parameters."""

    # TODO: get execute_sync to work
    result = asyncio.run(
        sync_session_schema.execute(
            general_query,
            variable_values={
                "authorId": sync_author.id,
                "first": 3,
            },
            context_value={
                "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                    bind=sync_session,
                ),
            },
        )
    )
    assert result.errors is None

    # Check pagination results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 3
    assert books_connection["pageInfo"]["hasNextPage"] is True
    assert books_connection["pageInfo"]["hasPreviousPage"] is False

    # Store the end cursor for the next pagination query
    end_cursor = books_connection["pageInfo"]["endCursor"]

    result = asyncio.run(
        sync_session_schema.execute(
            general_query,
            variable_values={"authorId": sync_author.id, "first": 4, "after": end_cursor},
            context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=sync_session)},
        )
    )
    assert result.errors is None

    # Check next page results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 4
    assert books_connection["pageInfo"]["hasNextPage"] is True
    assert books_connection["pageInfo"]["hasPreviousPage"] is True


@pytest.mark.asyncio
async def test_relationship_pagination_async(
    async_session: AsyncSession,
    async_session_schema: strawberry.Schema,
    general_query: str,
    async_author,
):
    """Test pagination on relationship fields using async execution."""

    loader = StrawberrySQLAlchemyLoader(async_bind_factory=lambda: async_session)
    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "first": 3},
        context_value={"sqlalchemy_loader": loader},
    )
    assert result.errors is None

    # Check pagination results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 3
    assert books_connection["pageInfo"]["hasNextPage"] is True
    assert books_connection["pageInfo"]["hasPreviousPage"] is False

    # Store the end cursor for the next pagination query
    end_cursor = books_connection["pageInfo"]["endCursor"]

    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "first": 4, "after": end_cursor},
        context_value={"sqlalchemy_loader": loader},
    )
    assert result.errors is None

    # Check next page results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 4
    assert books_connection["pageInfo"]["hasNextPage"] is True
    assert books_connection["pageInfo"]["hasPreviousPage"] is True


def test_relationship_pagination_last(
    sync_session: Session,
    sync_session_schema: strawberry.Schema,
    general_query: str,
    sync_author,
):
    """Test pagination on relationship fields using last and before parameters."""

    result = asyncio.run(
        sync_session_schema.execute(
            general_query,
            variable_values={
                "authorId": sync_author.id,
                "last": 3,
            },
            context_value={
                "sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=sync_session),
            },
        )
    )
    assert result.errors is None

    # Check backward pagination results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 3
    # When getting the last N items, there should be no next page
    assert books_connection["pageInfo"]["hasNextPage"] is False
    # But there should be previous items
    assert books_connection["pageInfo"]["hasPreviousPage"] is True

    # Get the start cursor for the before parameter
    start_cursor = books_connection["pageInfo"]["startCursor"]

    result = asyncio.run(
        sync_session_schema.execute(
            general_query,
            variable_values={"authorId": sync_author.id, "last": 4, "before": start_cursor},
            context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=sync_session)},
        )
    )
    assert result.errors is None

    # Check previous page results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 4
    assert books_connection["pageInfo"]["hasNextPage"] is True
    # If we have less than 7 books before the cursor, we should have previous page
    assert books_connection["pageInfo"]["hasPreviousPage"] is True


@pytest.mark.asyncio
async def test_relationship_pagination_last_async(
    async_session: AsyncSession,
    async_session_schema: strawberry.Schema,
    general_query: str,
    async_author,
):
    """Test backward pagination on relationship fields using async execution."""

    loader = StrawberrySQLAlchemyLoader(async_bind_factory=lambda: async_session)
    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "last": 3},
        context_value={"sqlalchemy_loader": loader},
    )
    assert result.errors is None

    # Check backward pagination results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 3
    # When getting the last N items, there should be no next page
    assert books_connection["pageInfo"]["hasNextPage"] is False
    # But there should be previous items
    assert books_connection["pageInfo"]["hasPreviousPage"] is True

    # Get the start cursor for the before parameter
    start_cursor = books_connection["pageInfo"]["startCursor"]

    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "last": 4, "before": start_cursor},
        context_value={"sqlalchemy_loader": loader},
    )
    assert result.errors is None

    # Check previous page results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 4
    assert books_connection["pageInfo"]["hasNextPage"] is True
    # If we have less than 7 books before the cursor, we should have previous page
    assert books_connection["pageInfo"]["hasPreviousPage"] is True


@pytest.mark.asyncio
async def test_relationship_pagination_invalid_args(
    async_session: AsyncSession,
    async_session_schema: strawberry.Schema,
    async_author,
    general_query,
):
    """Test invalid pagination args."""
    loader = StrawberrySQLAlchemyLoader(async_bind_factory=lambda: async_session)
    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "first": 3},
        context_value={"sqlalchemy_loader": loader},
    )
    assert result.errors is None

    # Check pagination results
    books_connection = result.data["author"]["books"]
    assert len(books_connection["edges"]) == 3
    assert books_connection["pageInfo"]["hasNextPage"] is True
    assert books_connection["pageInfo"]["hasPreviousPage"] is False

    # Store the end cursor for the next pagination query
    end_cursor = books_connection["pageInfo"]["endCursor"]

    result = await async_session_schema.execute(
        general_query,
        variable_values={"authorId": async_author.id, "first": 2, "before": end_cursor},
    )
    assert result.errors is not None, "First and before should cause error"

    result = await async_session_schema.execute(
        general_query, variable_values={"authorId": async_author.id, "last": 2, "after": end_cursor}
    )
    assert result.errors is not None, "Last and after should cause error"

    result = await async_session_schema.execute(
        general_query, variable_values={"authorId": async_author.id, "first": 2, "last": 3}
    )
    assert result.errors is not None, "First and last should cause error"
