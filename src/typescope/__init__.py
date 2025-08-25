"""typescope - Runtime type-level assignability check"""

from typing import Any


def is_assignable(source: type[Any], target: type[Any]) -> bool:
    """Check if `source` type can be assigned to `target` type at runtime.

    Currently a placeholder that always returns False.
    """
    # TODO: replace with real subtyping logic
    return False


__all__ = ["is_assignable"]
