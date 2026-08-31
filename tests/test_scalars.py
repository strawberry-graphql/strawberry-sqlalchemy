import pytest
import strawberry
from sqlalchemy import BigInteger, Column, Integer
from strawberry.schema.config import StrawberryConfig
from strawberry_sqlalchemy_mapper import strawberry_sqlalchemy_scalar_map


@pytest.fixture
def measurement_table(base):
    class Measurement(base):
        __tablename__ = "measurement"
        id = Column(Integer, autoincrement=True, primary_key=True)
        value = Column(BigInteger, nullable=False)
        optional_value = Column(BigInteger)

    return Measurement


def test_big_int_serializes_values_larger_than_32_bits(measurement_table, mapper):
    @mapper.type(measurement_table)
    class Measurement:
        pass

    @strawberry.type
    class Query:
        @strawberry.field
        def measurement(self) -> Measurement:
            return measurement_table(id=1, value=2**53 + 1, optional_value=None)

    mapper.finalize()
    schema = strawberry.Schema(
        query=Query,
        config=StrawberryConfig(scalar_map=strawberry_sqlalchemy_scalar_map),
    )
    assert "scalar BigInt" in str(schema)

    result = schema.execute_sync("{ measurement { value optionalValue } }")

    assert result.errors is None
    assert result.data == {"measurement": {"value": 2**53 + 1, "optionalValue": None}}
