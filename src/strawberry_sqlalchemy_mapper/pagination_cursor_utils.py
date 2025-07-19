from typing import Optional

from strawberry import relay


def decode_cursor_index(cursor: str) -> Optional[int]:
    """Convert an array connection cursor into the relevant row index."""
    try:
        start, str_index = relay.from_base64(cursor)
        if start == "arrayconnection":
            return int(str_index)
    except (ValueError, IndexError):
        # If decoding fails, default to no offset
        pass
    return None


def encode_cursor_index(cursor_index: int) -> str:
    """Convert an array connection cursor into the relevant row index."""
    return relay.to_base64("arrayconnection", cursor_index)
