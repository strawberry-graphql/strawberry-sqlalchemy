from typing import Union

import strawberry

Int64 = strawberry.scalar(
    Union[int, str],  # type: ignore
    serialize=lambda v: int(v),
    parse_value=lambda v: str(v),
    description="Int64 field",
)
