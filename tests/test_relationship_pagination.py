from typing import Any, List
import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String
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
    base: Any, engine: Engine, sessionmaker: sessionmaker, author_book_tables
):
    """Test pagination on relationship fields using first and after parameters."""
    base.metadata.create_all(engine)
    Author, Book = author_book_tables

    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(Author)
    class AuthorType(relay.Node):
        id: relay.NodeID[int]
        name: str

    @mapper.type(Book)
    class BookType(relay.Node):
        id: relay.NodeID[int]
        title: str

    @strawberry.type
    class Query:
        @strawberry.field
        def author(self, info: Info, id: int) -> AuthorType:
            with sessionmaker() as session:
                return session.query(Author).filter(Author.id == id).first()

    schema = strawberry.Schema(query=Query)

    with sessionmaker() as session:
        # Create test data
        author = Author(name="Test Author")
        session.add(author)
        session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = Book(title=f"Book {i+1}", author_id=author.id)
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

        result = schema.execute_sync(query, context_value={"sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=session)})
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
    base: Any, async_engine: AsyncEngine, async_sessionmaker, author_book_tables
):
    """Test pagination on relationship fields using async execution."""
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

    Author, Book = author_book_tables
    mapper = StrawberrySQLAlchemyMapper()

    @mapper.type(Author)
    class AuthorType(relay.Node):
        id: relay.NodeID[int]
        name: str

    @mapper.type(Book)
    class BookType(relay.Node):
        id: relay.NodeID[int]
        title: str

    @strawberry.type
    class Query:
        @strawberry.field
        def author(self, info: Info, id: int) -> AuthorType:
            session = info.context["session"]
            return session.get(Author, id)

    schema = strawberry.Schema(query=Query)

    async with async_sessionmaker(expire_on_commit=False) as session:
        # Create test data
        author = Author(name="Test Author")
        session.add(author)
        await session.flush()  # To get the author ID

        # Create 10 books for pagination testing
        for i in range(10):
            book = Book(title=f"Book {i+1}", author_id=author.id)
            session.add(book)

        await session.commit()
        author_id = author.id

    async with async_sessionmaker(expire_on_commit=False) as session:
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
