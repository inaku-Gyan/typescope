"""Normalize the small set of type expressions supported by the native spine."""

from __future__ import annotations

import types
import typing
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "NormalizationError",
    "NormalizationBudget",
    "NormalizedKind",
    "NormalizedType",
    "normalize_type_expression",
]


class NormalizedKind(StrEnum):
    """Semantic categories understood by the native evaluation spine."""

    CLASS = "class"
    SPECIAL = "special"
    UNION = "union"


class SpecialType(StrEnum):
    """Special type forms handled before nominal class rules."""

    ANY = "any"
    NEVER = "never"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class RepresentationProvenance:
    """Stable carrier metadata retained separately from semantic identity."""

    carrier: str


@dataclass(slots=True)
class NormalizationBudget:
    """Mutable budget shared by both operands in one evaluation."""

    remaining: int = 64


@dataclass(frozen=True, slots=True)
class NormalizedType:
    """Version-independent semantic input to the evaluator."""

    kind: NormalizedKind
    value: object | None = field(default=None, compare=True, hash=True)
    members: tuple[NormalizedType, ...] = field(default=(), compare=True)
    provenance: RepresentationProvenance = field(
        default=RepresentationProvenance("unknown"), compare=False, hash=False
    )


class NormalizationError(TypeError):
    """Raised when a type expression cannot be safely normalized."""

    def __init__(self, reason_code: str, detail: str) -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(detail)


def normalize_type_expression(
    expression: Any,
    *,
    budget: int = 64,
    budget_state: NormalizationBudget | None = None,
) -> NormalizedType:
    """Normalize a supported runtime type expression.

    This boundary intentionally uses public ``typing`` introspection. Runtime
    carrier classes are retained only as provenance and never determine the
    normalized semantic identity.
    """

    state = budget_state or NormalizationBudget(budget)
    return _normalize(expression, state=state)


def _normalize(expression: Any, *, state: NormalizationBudget) -> NormalizedType:
    if state.remaining <= 0:
        raise NormalizationError(
            "normalization.budget_exhausted",
            "type expression normalization exceeded its budget",
        )
    state.remaining -= 1

    provenance = RepresentationProvenance(_carrier_name(expression))

    if expression is typing.Any:
        return NormalizedType(
            NormalizedKind.SPECIAL,
            SpecialType.ANY,
            provenance=provenance,
        )

    never = getattr(typing, "Never", None)
    no_return = getattr(typing, "NoReturn", None)
    if expression is never or expression is no_return:
        return NormalizedType(
            NormalizedKind.SPECIAL,
            SpecialType.NEVER,
            provenance=provenance,
        )

    if expression is None or expression is types.NoneType:
        return NormalizedType(
            NormalizedKind.SPECIAL,
            SpecialType.NONE,
            provenance=provenance,
        )

    origin = typing.get_origin(expression)
    if origin is typing.Union or origin is types.UnionType:
        members: list[NormalizedType] = []
        for argument in typing.get_args(expression):
            member = _normalize(argument, state=state)
            if member.kind is NormalizedKind.UNION:
                members.extend(member.members)
            else:
                members.append(member)

        unique_members = tuple(sorted(set(members), key=_semantic_sort_key))
        if len(unique_members) == 1:
            return unique_members[0]
        return NormalizedType(
            NormalizedKind.UNION,
            members=unique_members,
            provenance=provenance,
        )

    if isinstance(expression, type):
        return NormalizedType(
            NormalizedKind.CLASS,
            expression,
            provenance=provenance,
        )

    raise NormalizationError(
        "normalization.expression_unsupported",
        f"unsupported type expression: {_carrier_name(expression)}",
    )


def _carrier_name(expression: Any) -> str:
    carrier = type(expression)
    return f"{carrier.__module__}.{carrier.__qualname__}"


def _semantic_sort_key(expression: NormalizedType) -> tuple[str, str]:
    if expression.kind is NormalizedKind.CLASS:
        value = expression.value
        assert isinstance(value, type)
        return (expression.kind.value, f"{value.__module__}.{value.__qualname__}")
    if expression.kind is NormalizedKind.SPECIAL:
        return (expression.kind.value, str(expression.value))
    return (expression.kind.value, ",".join(map(str, expression.members)))
