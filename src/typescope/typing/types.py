import types
import typing

__all__ = [
    "StdUnionType",
    "StdNoneType",
]

StdUnionType = types.UnionType | typing._GenericAlias  # pyright: ignore[reportAttributeAccessIssue]

StdNoneType = type[types.NoneType | None]
