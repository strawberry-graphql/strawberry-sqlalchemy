import textwrap

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)


@pytest.fixture
def inheritance_table(base):
    class ModelA(base):
        __tablename__ = "a"

        id: Mapped[str] = mapped_column(primary_key=True)

        relationshipB_id: Mapped[str] = mapped_column(ForeignKey("b.id"))
        relationshipB: Mapped["ModelB"] = relationship()

    class ModelB(base):
        __tablename__ = "b"

        id: Mapped[str] = mapped_column(primary_key=True)

        parent_id: Mapped[str] = mapped_column(ForeignKey("b.id"))
        parent: Mapped["ModelB"] = relationship(
            "ModelB", remote_side="ModelB.id", backref="children"
        )

        related_a: Mapped[list["ModelA"]] = relationship("ModelA", back_populates="relationshipB")

    return ModelA, ModelB


def test_types_with_inheritance(inheritance_table, mapper):
    ModelA, ModelB = inheritance_table

    @mapper.type(ModelA)
    class ApiA:
        pass

    @mapper.type(ModelB)
    class ApiB(ApiA):
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def apisb(self) -> ApiB: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = _get_test_types_with_inheritance_schema()
    assert str(schema) == textwrap.dedent(expected).strip()


def _get_test_types_with_inheritance_schema():
    return '''
type ApiB {
  id: String!
  relationshipBId: String!
  relationshipB: ModelB!
  parentId: String!
  parent: ModelB!
  relatedA: ModelAConnection!
  children: ModelBConnection!
}

type ModelA {
  id: String!
  relationshipBId: String!
  relationshipB: ModelB!
}

type ModelAConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [ModelAEdge!]!
}

type ModelAEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: ModelA!
}

type ModelB {
  id: String!
  parentId: String!
  parent: ModelB!
  relatedA: ModelAConnection!
  children: ModelBConnection!
}

type ModelBConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [ModelBEdge!]!
}

type ModelBEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: ModelB!
}

"""Information to aid in pagination."""
type PageInfo {
  """When paginating forwards, are there more items?"""
  hasNextPage: Boolean!

  """When paginating backwards, are there more items?"""
  hasPreviousPage: Boolean!

  """When paginating backwards, the cursor to continue."""
  startCursor: String

  """When paginating forwards, the cursor to continue."""
  endCursor: String
}

type Query {
  apisb: ApiB!
}


    '''


def test_types_with_inheritance_should_respect_exclude_fields(inheritance_table, mapper):
    ModelA, ModelB = inheritance_table

    @mapper.type(ModelA)
    class ApiA:
        __exclude__ = ["relationshipB_id"]

    @mapper.type(ModelB)
    class ApiB(ApiA):
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def apisb(self) -> ApiB: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = _get_test_types_with_inheritance_schema_should_respect_exclude_fields()
    assert str(schema) == textwrap.dedent(expected).strip()


def _get_test_types_with_inheritance_schema_should_respect_exclude_fields():
    return '''
type ApiB {
  id: String!
  relationshipB: ModelB!
  parentId: String!
  parent: ModelB!
  relatedA: ModelAConnection!
  children: ModelBConnection!
}

type ModelA {
  id: String!
  relationshipBId: String!
  relationshipB: ModelB!
}

type ModelAConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [ModelAEdge!]!
}

type ModelAEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: ModelA!
}

type ModelB {
  id: String!
  parentId: String!
  parent: ModelB!
  relatedA: ModelAConnection!
  children: ModelBConnection!
}

type ModelBConnection {
  """Pagination data for this connection"""
  pageInfo: PageInfo!
  edges: [ModelBEdge!]!
}

type ModelBEdge {
  """A cursor for use in pagination"""
  cursor: String!

  """The item at the end of the edge"""
  node: ModelB!
}

"""Information to aid in pagination."""
type PageInfo {
  """When paginating forwards, are there more items?"""
  hasNextPage: Boolean!

  """When paginating backwards, are there more items?"""
  hasPreviousPage: Boolean!

  """When paginating backwards, the cursor to continue."""
  startCursor: String

  """When paginating forwards, the cursor to continue."""
  endCursor: String
}

type Query {
  apisb: ApiB!
}


    '''


@pytest.fixture
def inheritance_table_with_duplicated_fields(base):
    class ModelA(base):
        __tablename__ = "a"

        id: Mapped[str] = mapped_column(primary_key=True)

        example_field = Column(String(50))

    class ModelB(base):
        __tablename__ = "b"

        id: Mapped[str] = mapped_column(primary_key=True)

        example_field = Column(Integer, autoincrement=True, primary_key=True)

    return ModelA, ModelB


def test_types_with_inheritance_should_override_inherited_fields_when_duplicated(
    inheritance_table_with_duplicated_fields, mapper
):
    ModelA, ModelB = inheritance_table_with_duplicated_fields

    @mapper.type(ModelA)
    class ApiA:
        pass

    @mapper.type(ModelB)
    class ApiB(ApiA):
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def apisb(self) -> ApiB: ...

        @strawberry.field
        def apisa(self) -> ApiA: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = _get_test_types_with_inheritance_and_duplicated_fields()
    assert str(schema) == textwrap.dedent(expected).strip()


def _get_test_types_with_inheritance_and_duplicated_fields():
    return """
type ApiA {
  id: String!
  exampleField: String
}

type ApiB {
  id: String!
  exampleField: Int!
}

type Query {
  apisb: ApiB!
  apisa: ApiA!
}

"""


# TODO: test inheritance with a empty (class)
