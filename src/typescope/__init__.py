"""typescope - Runtime type-level assignability check"""

from typing import Any


def is_assignable(source_type: type[Any], target_type: type[Any]) -> bool:
    """Check if `source` type can be assigned to `target` type at runtime.

    Currently a placeholder that always returns False.
    """
    # TODO: replace with real subtyping logic
    return issubclass(source_type, target_type)


__all__ = ["is_assignable"]
