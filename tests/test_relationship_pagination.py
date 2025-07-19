from typing import Any, List
import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import relationship, sessionmaker
from strawberry import relay
from strawberry.types import Info
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyLoader, StrawberrySQLAlchemyMapper


@pytest.fixture
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


def test_relationship_pagination(
    base: Any,
    engine: Engine,
    mapper: StrawberrySQLAlchemyMapper,
    sessionmaker: sessionmaker,
    author_book_tables,
):
    """Test pagination on relationship fields using first and after parameters."""
    base.metadata.create_all(engine)
    AuthorModel, BookModel = author_book_tables

    with sessionmaker() as session:

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
                return session.scalars(
                    select(AuthorModel).filter(AuthorModel.id == id)
                ).first()

        mapper.finalize()
        schema = strawberry.Schema(query=Query)

        # Create test data
        author = AuthorModel(name="Test Author")
        session.add(author)
        session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = BookModel(title=f"Book {i+1}", author_id=author.id)
            session.add(book)

        session.commit()

        # Query for first 3 books
        query = """
        query {
          author(id: 1) {
            id
            name
            books(first: 3) {
              edges {
                node {
                  id
                  title
                }
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

        result = schema.execute_sync(
            query,
            context_value={
                "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                    bind=session,
                ),
            },
        )
        assert result.errors is None

        # Check pagination results
        books_connection = result.data["author"]["books"]
        assert len(books_connection["edges"]) == 3
        assert books_connection["pageInfo"]["hasNextPage"] is True
        assert books_connection["pageInfo"]["hasPreviousPage"] is False

        # Store the end cursor for the next pagination query
        end_cursor = books_connection["pageInfo"]["endCursor"]

        # Query for next 4 books after the cursor
        query = """
        query($after: String!) {
          author(id: 1) {
            books(first: 4, after: $after) {
              edges {
                node {
                  id
                  title
                }
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

        result = schema.execute_sync(
            query,
            variable_values={"after": end_cursor},
            context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)}
        )
        assert result.errors is None

        # Check next page results
        books_connection = result.data["author"]["books"]
        assert len(books_connection["edges"]) == 4
        assert books_connection["pageInfo"]["hasNextPage"] is True
        assert books_connection["pageInfo"]["hasPreviousPage"] is True


@pytest.mark.asyncio
async def test_relationship_pagination_async(
    base: Any,
    async_engine: AsyncEngine,
    mapper: StrawberrySQLAlchemyMapper,
    async_sessionmaker,
    author_book_tables
):
    """Test pagination on relationship fields using async execution."""
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    async with async_sessionmaker(expire_on_commit=False) as session:

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
                session = info.context["session"]
                return session.get(AuthorModel, id)

        mapper.finalize()
        schema = strawberry.Schema(query=Query)

        # Create test data
        author = AuthorModel(name="Test Author")
        session.add(author)
        await session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = BookModel(title=f"Book {i+1}", author_id=author.id)
            session.add(book)

        await session.commit()
        author_id = author.id

        # Query for first 3 books
        query = """
        query {
          author(id: 1) {
            id
            name
            books(first: 3) {
              edges {
                node {
                  id
                  title
                }
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

        loader = StrawberrySQLAlchemyLoader(async_bind_factory=lambda: session)
        result = await schema.execute(
            query,
            context_value={
                "sqlalchemy_loader": loader,
                "session": session
            }
        )
        assert result.errors is None

        # Check pagination results
        books_connection = result.data["author"]["books"]
        assert len(books_connection["edges"]) == 3
        assert books_connection["pageInfo"]["hasNextPage"] is True
        assert books_connection["pageInfo"]["hasPreviousPage"] is False

        # Store the end cursor for the next pagination query
        end_cursor = books_connection["pageInfo"]["endCursor"]

        # Query for next 4 books after the cursor
        query = """
        query($after: String!) {
          author(id: 1) {
            books(first: 4, after: $after) {
              edges {
                node {
                  id
                  title
                }
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

        result = await schema.execute(
            query,
            variable_values={"after": end_cursor},
            context_value={
                "sqlalchemy_loader": loader,
                "session": session
            }
        )
        assert result.errors is None

        # Check next page results
        books_connection = result.data["author"]["books"]
        assert len(books_connection["edges"]) == 4
        assert books_connection["pageInfo"]["hasNextPage"] is True
        assert books_connection["pageInfo"]["hasPreviousPage"] is True


def test_relationship_pagination_last(
    base: Any,
    engine: Engine,
    mapper: StrawberrySQLAlchemyMapper,
    sessionmaker: sessionmaker,
    author_book_tables,
):
    """Test pagination on relationship fields using last and before parameters."""
    base.metadata.create_all(engine)
    AuthorModel, BookModel = author_book_tables

    with sessionmaker() as session:

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
                return session.scalars(
                    select(AuthorModel).filter(AuthorModel.id == id)
                ).first()

        mapper.finalize()
        schema = strawberry.Schema(query=Query)

        # Create test data
        author = AuthorModel(name="Test Author")
        session.add(author)
        session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = BookModel(title=f"Book {i+1}", author_id=author.id)
            session.add(book)

        session.commit()

        # Query for last 3 books (backward pagination)
        query = """
        query {
          author(id: 1) {
            id
            name
            books(last: 3) {
              edges {
                node {
                  id
                  title
                }
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

        result = schema.execute_sync(
            query,
            context_value={
                "sqlalchemy_loader": StrawberrySQLAlchemyLoader(
                    bind=session
                ),
            },
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

        # Query for previous 4 books before the cursor
        query = """
        query($before: String!) {
          author(id: 1) {
            books(last: 4, before: $before) {
              edges {
                node {
                  id
                  title
                }
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

        result = schema.execute_sync(
            query,
            variable_values={"before": start_cursor},
            context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)}
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
    base: Any,
    async_engine: AsyncEngine,
    mapper: StrawberrySQLAlchemyMapper,
    async_sessionmaker,
    author_book_tables,
):
    """Test backward pagination on relationship fields using async execution."""
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    AuthorModel, BookModel = author_book_tables

    async with async_sessionmaker(expire_on_commit=False) as session:

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
                session = info.context["session"]
                return session.get(AuthorModel, id)

        mapper.finalize()
        schema = strawberry.Schema(query=Query)

        # Create test data
        author = AuthorModel(name="Test Author")
        session.add(author)
        await session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = BookModel(title=f"Book {i+1}", author_id=author.id)
            session.add(book)

        await session.commit()
        author_id = author.id

        # Query for last 3 books (backward pagination)
        query = """
        query {
          author(id: 1) {
            id
            name
            books(last: 3) {
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

        loader = StrawberrySQLAlchemyLoader(async_bind_factory=lambda: session)
        result = await schema.execute(
            query,
            context_value={
                "sqlalchemy_loader": loader,
                "session": session
            }
        )
        assert result.errors is None

        # Check backward pagination results
        books_connection = result.data["author"]["books"]
        from pprint import pprint
        pprint(books_connection)
        assert len(books_connection["edges"]) == 3
        # When getting the last N items, there should be no next page
        assert books_connection["pageInfo"]["hasNextPage"] is False
        # But there should be previous items
        assert books_connection["pageInfo"]["hasPreviousPage"] is True

        # Get the start cursor for the before parameter
        start_cursor = books_connection["pageInfo"]["startCursor"]

        # Query for previous 4 books before the cursor
        query = """
        query($before: String!) {
          author(id: 1) {
            books(last: 4, before: $before) {
              edges {
                node {
                  id
                  title
                }
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

        result = await schema.execute(
            query,
            variable_values={"before": start_cursor},
            context_value={
                "sqlalchemy_loader": loader,
                "session": session
            }
        )
        assert result.errors is None

        # Check previous page results
        books_connection = result.data["author"]["books"]
        assert len(books_connection["edges"]) == 4
        assert books_connection["pageInfo"]["hasNextPage"] is True
        # If we have less than 7 books before the cursor, we should have previous page
        assert books_connection["pageInfo"]["hasPreviousPage"] is True
