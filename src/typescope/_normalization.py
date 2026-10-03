"""Normalize the small set of type expressions supported by the native spine."""

from __future__ import annotations

import types
import typing
from collections import abc as collections_abc
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "NormalizationError",
    "NormalizationBudget",
    "NormalizedKind",
    "NormalizedType",
    "generic_variances",
    "normalize_type_expression",
    "project_generic_arguments",
]


class NormalizedKind(StrEnum):
    """Semantic categories understood by the native evaluation spine."""

    CLASS = "class"
    GENERIC = "generic"
    SPECIAL = "special"
    TYPEVAR = "typevar"
    UNION = "union"


class SpecialType(StrEnum):
    """Special type forms handled before nominal class rules."""

    ANY = "any"
    NEVER = "never"
    NONE = "none"
    UNKNOWN = "unknown"
    ELLIPSIS = "ellipsis"


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


def _normalize(  # noqa: PLR0911, PLR0912 - ordered typing-form boundary
    expression: Any, *, state: NormalizationBudget
) -> NormalizedType:
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

    if isinstance(expression, typing.TypeVar):
        return NormalizedType(
            NormalizedKind.TYPEVAR,
            expression,
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
        if _is_generic_origin(expression):
            return _normalize_generic(
                expression,
                (),
                provenance=provenance,
                state=state,
            )
        if _has_generic_base(expression):
            if getattr(expression, "__parameters__", ()):
                return _normalize_generic(
                    expression,
                    (),
                    provenance=provenance,
                    state=state,
                )
            return NormalizedType(
                NormalizedKind.GENERIC,
                expression,
                provenance=provenance,
            )
        return NormalizedType(
            NormalizedKind.CLASS,
            expression,
            provenance=provenance,
        )

    if origin is not None and _is_generic_origin(origin):
        return _normalize_generic(
            origin,
            typing.get_args(expression),
            provenance=provenance,
            state=state,
        )

    raise NormalizationError(
        "normalization.expression_unsupported",
        f"unsupported type expression: {_carrier_name(expression)}",
    )


def _carrier_name(expression: Any) -> str:
    carrier = type(expression)
    return f"{carrier.__module__}.{carrier.__qualname__}"


# The standard library does not expose variance metadata for built-in generic
# classes at runtime.  Keep that compatibility table at the normalization
# boundary so the evaluator only sees normalized semantic arguments.
_INVARIANT = ("invariant",)
_COVARIANT = ("covariant",)
_IMPLICIT_UNKNOWN = object()
_KNOWN_GENERIC_VARIANCES: dict[type[Any], tuple[str, ...]] = {
    list: _INVARIANT,
    dict: ("invariant", "invariant"),
    set: _INVARIANT,
    frozenset: _COVARIANT,
    tuple: _COVARIANT,
    type: _COVARIANT,
    collections_abc.Iterable: _COVARIANT,
    collections_abc.Iterator: _COVARIANT,
    collections_abc.Collection: _COVARIANT,
    collections_abc.Container: _COVARIANT,
    collections_abc.Reversible: _COVARIANT,
    collections_abc.Sequence: _COVARIANT,
    collections_abc.MutableSequence: _INVARIANT,
    collections_abc.Set: _COVARIANT,
    collections_abc.MutableSet: _INVARIANT,
    collections_abc.Mapping: ("covariant", "covariant"),
    collections_abc.MutableMapping: ("invariant", "invariant"),
}


def _is_generic_origin(origin: object) -> bool:
    if not isinstance(origin, type):
        return False
    return origin in _KNOWN_GENERIC_VARIANCES or bool(
        getattr(origin, "__parameters__", ())
    )


def _has_generic_base(origin: type[Any]) -> bool:
    return any(
        typing.get_origin(base) is not None
        for base in getattr(origin, "__orig_bases__", ())
    )


def _generic_variances(origin: type[Any]) -> tuple[str, ...] | None:
    known = _KNOWN_GENERIC_VARIANCES.get(origin)
    if known is not None:
        return known

    parameters = getattr(origin, "__parameters__", ())
    if not parameters:
        return None
    return tuple(
        "covariant"
        if getattr(parameter, "__covariant__", False)
        else "contravariant"
        if getattr(parameter, "__contravariant__", False)
        else "invariant"
        for parameter in parameters
    )


def generic_variances(origin: type[Any]) -> tuple[str, ...] | None:
    """Return the declared variance for a normalized generic origin."""

    return _generic_variances(origin)


def _generic_arity(origin: type[Any]) -> int:
    variances = _generic_variances(origin)
    if variances is not None:
        return len(variances)
    return 0


def _implicit_arguments(origin: type[Any]) -> tuple[Any, ...]:
    arity = _generic_arity(origin)
    if arity:
        return (_IMPLICIT_UNKNOWN,) * arity
    # Tuple and other variadic forms have no fixed runtime arity. One implicit
    # slot lets the evaluator retain the omission without inventing a shape.
    return (_IMPLICIT_UNKNOWN,)


def _normalize_generic(
    origin: type[Any],
    arguments: tuple[Any, ...],
    *,
    provenance: RepresentationProvenance,
    state: NormalizationBudget,
) -> NormalizedType:
    if not arguments:
        arguments = _implicit_arguments(origin)

    normalized_arguments: list[NormalizedType] = []
    for argument in arguments:
        if argument is _IMPLICIT_UNKNOWN:
            normalized_arguments.append(
                NormalizedType(
                    NormalizedKind.SPECIAL,
                    SpecialType.UNKNOWN,
                    provenance=RepresentationProvenance("typescope.unknown"),
                )
            )
        elif argument is Ellipsis:
            normalized_arguments.append(
                NormalizedType(
                    NormalizedKind.SPECIAL,
                    SpecialType.ELLIPSIS,
                    provenance=RepresentationProvenance("builtins.ellipsis"),
                )
            )
        else:
            normalized_arguments.append(_normalize(argument, state=state))

    return NormalizedType(
        NormalizedKind.GENERIC,
        origin,
        members=tuple(normalized_arguments),
        provenance=provenance,
    )


def project_generic_arguments(  # noqa: PLR0911, PLR0912 - explicit failure paths
    source_origin: type[Any],
    source_arguments: tuple[NormalizedType, ...],
    destination_origin: type[Any],
    *,
    budget_state: NormalizationBudget,
) -> tuple[NormalizedType, ...] | None:
    """Project normalized arguments through a generic inheritance edge.

    Runtime carrier inspection belongs to this normalization boundary. The
    evaluator receives either already-normalized arguments or ``None`` when a
    projection cannot be recovered safely.
    """

    if source_origin is destination_origin:
        return source_arguments

    projections: dict[type[Any], dict[type[Any], bool]] = {
        list: {
            collections_abc.MutableSequence: True,
            collections_abc.Sequence: True,
            collections_abc.Collection: True,
            collections_abc.Iterable: True,
        },
        dict: {
            collections_abc.MutableMapping: True,
            collections_abc.Mapping: True,
        },
        set: {
            collections_abc.MutableSet: True,
            collections_abc.Set: True,
            collections_abc.Collection: True,
            collections_abc.Iterable: True,
        },
        frozenset: {
            collections_abc.Set: True,
            collections_abc.Collection: True,
            collections_abc.Iterable: True,
        },
        tuple: {
            collections_abc.Sequence: True,
            collections_abc.Collection: True,
            collections_abc.Iterable: True,
        },
    }
    if projections.get(source_origin, {}).get(destination_origin):
        if source_origin is tuple and len(source_arguments) != 1:
            if _is_ellipsis_argument(source_arguments):
                return source_arguments[:1]
            return None
        return source_arguments

    parameters = getattr(source_origin, "__parameters__", ())
    if not parameters and not getattr(source_origin, "__orig_bases__", ()):
        return None
    if parameters and len(parameters) != len(source_arguments):
        return None
    substitutions = dict(zip(parameters, source_arguments, strict=True))
    queue: list[tuple[type[Any], dict[Any, NormalizedType]]] = [
        (source_origin, substitutions)
    ]
    visited: set[type[Any]] = set()
    while queue:
        current, mapping = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        for base in getattr(current, "__orig_bases__", ()):
            base_origin = typing.get_origin(base) or base
            if not isinstance(base_origin, type) or base_origin is typing.Generic:
                continue
            base_parameters = getattr(base_origin, "__parameters__", ())
            base_arguments = typing.get_args(base)
            resolved = tuple(
                _resolve_projection_argument(argument, mapping, budget_state)
                for argument in base_arguments
            )
            next_mapping = dict(zip(base_parameters, resolved, strict=False))
            if base_origin is destination_origin:
                if getattr(base_origin, "__parameters__", ()) and not base_arguments:
                    return None
                return resolved
            if base_parameters:
                queue.append((base_origin, next_mapping))
    return None


def _is_ellipsis_argument(arguments: tuple[NormalizedType, ...]) -> bool:
    return bool(
        arguments
        and arguments[-1].kind is NormalizedKind.SPECIAL
        and arguments[-1].value is SpecialType.ELLIPSIS
    )


def _resolve_projection_argument(
    argument: Any,
    mapping: dict[Any, NormalizedType],
    budget_state: NormalizationBudget,
) -> NormalizedType:
    if argument in mapping:
        return mapping[argument]
    return normalize_type_expression(argument, budget_state=budget_state)


def _semantic_sort_key(expression: NormalizedType) -> tuple[str, str]:
    if expression.kind is NormalizedKind.CLASS:
        value = expression.value
        assert isinstance(value, type)
        return (expression.kind.value, f"{value.__module__}.{value.__qualname__}")
    if expression.kind is NormalizedKind.GENERIC:
        value = expression.value
        assert isinstance(value, type)
        members = ",".join(
            ":".join(_semantic_sort_key(member)) for member in expression.members
        )
        return (
            expression.kind.value,
            f"{value.__module__}.{value.__qualname__}[{members}]",
        )
    if expression.kind is NormalizedKind.TYPEVAR:
        value = expression.value
        assert isinstance(value, typing.TypeVar)
        return (expression.kind.value, value.__name__)
    if expression.kind is NormalizedKind.SPECIAL:
        return (expression.kind.value, str(expression.value))
    return (
        expression.kind.value,
        ",".join(":".join(_semantic_sort_key(member)) for member in expression.members),
    )
