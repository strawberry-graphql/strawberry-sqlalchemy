import textwrap

import pytest
import strawberry
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


@pytest.fixture
def inheritance_table(base):
    class ModelA(base):
        __tablename__ = "a"

        id = Column(String, primary_key=True)

        relationshipB_id = Column(String, ForeignKey("b.id"))
        relationshipB = relationship("ModelB", back_populates="related_a")

    class ModelB(base):
        __tablename__ = "b"

        id = Column(String, primary_key=True)

        parent_id = Column(String, ForeignKey("b.id"))
        parent = relationship("ModelB", remote_side="ModelB.id", backref="children")

        related_a = relationship("ModelA", back_populates="relationshipB")

    return ModelA, ModelB


def test_types_with_inheritance(inheritance_table, mapper, schema_with_inheritance):
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

    expected = schema_with_inheritance
    assert str(schema) == textwrap.dedent(expected).strip()


@pytest.fixture
def schema_with_inheritance():
    return '''
type ApiB {
  id: String!
  relationshipBId: String
  relationshipB: ModelB
  parentId: String
  parent: ModelB
  relatedA(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelAConnection!
  children(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelBConnection!
}

type ModelA {
  id: String!
  relationshipBId: String
  relationshipB: ModelB
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
  parentId: String
  parent: ModelB
  relatedA(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelAConnection!
  children(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelBConnection!
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

    '''  # noqa: E501 - long lines needed for exact string matches


def test_types_with_inheritance_should_respect_exclude_fields(
    inheritance_table, mapper, schema_with_excluded_fields
):
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

    expected = schema_with_excluded_fields
    assert str(schema) == textwrap.dedent(expected).strip()


@pytest.fixture
def schema_with_excluded_fields():
    return '''
type ApiB {
  id: String!
  relationshipB: ModelB
  parentId: String
  parent: ModelB
  relatedA(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelAConnection!
  children(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelBConnection!
}

type ModelA {
  id: String!
  relationshipBId: String
  relationshipB: ModelB
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
  parentId: String
  parent: ModelB
  relatedA(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelAConnection!
  children(first: Int = null, after: String = null, last: Int = null, before: String = null): ModelBConnection!
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

    '''  # noqa: E501 - long lines needed for exact string matches


@pytest.fixture
def inheritance_table_with_duplicated_fields(base):
    class ModelA(base):
        __tablename__ = "a"

        id = Column(String, primary_key=True)
        example_field = Column(String(50))

    class ModelB(base):
        __tablename__ = "b"

        id = Column(String, primary_key=True)
        example_field = Column(Integer, autoincrement=True)
        name = Column(String(50))

    return ModelA, ModelB


def test_types_with_inheritance_should_override_inherited_fields_when_duplicated(
    inheritance_table_with_duplicated_fields, mapper, schema_with_duplicated_fields
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

    expected = schema_with_duplicated_fields
    assert str(schema) == textwrap.dedent(expected).strip()


@pytest.fixture
def schema_with_duplicated_fields():
    return """
type ApiA {
  id: String!
  exampleField: String
}

type ApiB {
  id: String!
  exampleField: Int
  name: String
}

type Query {
  apisb: ApiB!
  apisa: ApiA!
}

"""


def test_types_with_inheritance_should_override_inherited_fields_when_declared(
    inheritance_table_with_duplicated_fields, mapper, schema_with_declared_fields
):
    ModelA, ModelB = inheritance_table_with_duplicated_fields

    @mapper.type(ModelA)
    class ApiA:
        pass

    @mapper.type(ModelB)
    class ApiB(ApiA):
        example_field: float = strawberry.field(name="exampleField")

    @strawberry.type
    class Query:
        @strawberry.field
        def apisb(self) -> ApiB: ...

        @strawberry.field
        def apisa(self) -> ApiA: ...

    mapper.finalize()
    schema = strawberry.Schema(query=Query)

    expected = schema_with_declared_fields
    assert str(schema) == textwrap.dedent(expected).strip()


@pytest.fixture
def schema_with_declared_fields():
    return """
type ApiA {
  id: String!
  exampleField: String
}

type ApiB {
  id: String!
  exampleField: Float!
  name: String
}

type Query {
  apisb: ApiB!
  apisa: ApiA!
}

"""
