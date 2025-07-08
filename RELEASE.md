Release type: patch

This release improves how types inherit fields from other mapped types using `@mapper.type(...)`.
You can now safely inherit from another mapped type, and the resulting GraphQL type will include all expected fields with predictable conflict resolution.

Some examples:

- Basic Inheritance:

```python
@mapper.type(ModelA)
class ApiA:
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # ApiB inherits all fields declared in ApiA
    pass
```


- The `__exclude__` option continues working:

```python
@mapper.type(ModelA)
class ApiA:
    __exclude__ = ["relationshipB_id"]


@mapper.type(ModelB)
class ApiB(ApiA):
    # ApiB will have all fields declared in ApiA, except "relationshipB_id"
    pass
```

- If two SQLAlchemy models define fields with the same name, the field from the model inside `.type(...)` takes precedence:

```python
class ModelA(base):
    __tablename__ = "a"

    id = Column(String, primary_key=True)
    example_field = Column(String(50))


class ModelB(base):
    __tablename__ = "b"

    id = Column(String, primary_key=True)
    example_field = Column(Integer, autoincrement=True)


@mapper.type(ModelA)
class ApiA:
    # example_field will be a String
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # example_field will be taken from ModelB and will be an Integer
    pass
```


- If a field is explicitly declared in the mapped type, it will override any inherited or model-based definition:

```python
class ModelA(base):
    __tablename__ = "a"

    id = Column(String, primary_key=True)
    example_field = Column(String(50))


class ModelB(base):
    __tablename__ = "b"

    id = Column(String, primary_key=True)
    example_field = Column(Integer, autoincrement=True)


@mapper.type(ModelA)
class ApiA:
    pass


@mapper.type(ModelB)
class ApiB(ApiA):
    # example_field will be a Float
    example_field: float = strawberry.field(name="exampleField")
```
