from typing import NewType

import strawberry

BigInt = NewType("BigInt", int)

strawberry_sqlalchemy_scalar_map = {
    BigInt: strawberry.scalar(
        name="BigInt",
        description="BigInt field",
        serialize=lambda v: int(v),
        parse_value=lambda v: str(v),
    ),
}
