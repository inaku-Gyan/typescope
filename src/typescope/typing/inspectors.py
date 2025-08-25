from types import NoneType
from typing import Any, TypeGuard, get_args

from .types import *  # noqa: F403

__all__ = ["is_union", "get_union_items", "is_none_type"]


def is_union(tp: Any) -> TypeGuard[StdUnionType]:
    """Check if a type is a Union type."""
    return isinstance(tp, StdUnionType)


def get_union_items(tp: StdUnionType) -> tuple[Any, ...]:
    """Get the items of a Union type."""
    return get_args(tp)


def is_none_type(tp: Any) -> TypeGuard[StdNoneType]:
    """Check if a type is NoneType or None."""
    return tp is None or tp is NoneType
