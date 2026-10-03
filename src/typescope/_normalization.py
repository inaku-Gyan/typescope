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
            if _generic_parameters(expression):
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
        arguments = typing.get_args(expression)
        if origin is tuple and not arguments and _is_empty_tuple_expression(expression):
            arguments = (_EMPTY_TUPLE,)
        return _normalize_generic(
            origin,
            arguments,
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
_EMPTY_TUPLE = object()
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
    return origin in _KNOWN_GENERIC_VARIANCES or bool(_generic_parameters(origin))


def _has_generic_base(origin: type[Any]) -> bool:
    return any(
        typing.get_origin(base) is not None
        for base in getattr(origin, "__orig_bases__", ())
    )


def _generic_variances(origin: type[Any]) -> tuple[str, ...] | None:
    known = _KNOWN_GENERIC_VARIANCES.get(origin)
    if known is not None:
        return known

    parameters = _generic_parameters(origin)
    if not parameters:
        return None
    variances: list[str] = []
    for parameter in parameters:
        if getattr(parameter, "__infer_variance__", False):
            # PEP 695's inferred variance is not exposed as a stable public
            # result on every supported runtime.  Do not guess invariant.
            return None
        if getattr(parameter, "__covariant__", False):
            variances.append("covariant")
        elif getattr(parameter, "__contravariant__", False):
            variances.append("contravariant")
        else:
            variances.append("invariant")
    return tuple(variances)


def _generic_parameters(origin: type[Any]) -> tuple[Any, ...]:
    """Read generic parameters across the supported runtime spellings."""

    parameters = getattr(origin, "__parameters__", ())
    if parameters:
        return tuple(parameters)
    # PEP 695 exposes the declaration parameters through __type_params__.
    # Feature-detect it so Python 3.11 remains importable.
    return tuple(getattr(origin, "__type_params__", ()))


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
    if len(arguments) == 1 and arguments[0] is _EMPTY_TUPLE:
        return NormalizedType(
            NormalizedKind.GENERIC,
            origin,
            members=(),
            provenance=provenance,
        )
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


def _is_empty_tuple_expression(expression: Any) -> bool:
    """Recognize the public empty-tuple spellings without carrier checks."""

    return getattr(expression, "__args__", None) == ()


_PROJECTION_IDENTITY = "identity"
_PROJECTION_ELEMENTS = "elements"
_PROJECTION_KEYS = "keys"


def _projection_kind(
    source_origin: type[Any], destination_origin: type[Any]
) -> str | None:
    """Return the argument transformation for a known generic edge."""

    identity_destinations: dict[type[Any], tuple[type[Any], ...]] = {
        list: (
            collections_abc.MutableSequence,
            collections_abc.Sequence,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.MutableSequence: (
            collections_abc.Sequence,
            collections_abc.Reversible,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.Sequence: (
            collections_abc.Reversible,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.Iterator: (collections_abc.Iterable,),
        dict: (collections_abc.MutableMapping, collections_abc.Mapping),
        collections_abc.MutableMapping: (collections_abc.Mapping,),
        set: (
            collections_abc.MutableSet,
            collections_abc.Set,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.MutableSet: (
            collections_abc.Set,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.Set: (
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        frozenset: (
            collections_abc.Set,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
    }
    if destination_origin in identity_destinations.get(source_origin, ()):
        return _PROJECTION_IDENTITY

    element_destinations = {
        tuple: (
            collections_abc.Sequence,
            collections_abc.Reversible,
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
    }
    if destination_origin in element_destinations.get(source_origin, ()):
        return _PROJECTION_ELEMENTS

    key_destinations: dict[type[Any], tuple[type[Any], ...]] = {
        dict: (
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.MutableMapping: (
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
        collections_abc.Mapping: (
            collections_abc.Collection,
            collections_abc.Container,
            collections_abc.Iterable,
        ),
    }
    if destination_origin in key_destinations.get(source_origin, ()):
        return _PROJECTION_KEYS
    return None


def _project_builtin_arguments(  # noqa: PLR0911 - explicit projection branches
    source_origin: type[Any],
    source_arguments: tuple[NormalizedType, ...],
    destination_origin: type[Any],
) -> tuple[NormalizedType, ...] | None:
    kind = _projection_kind(source_origin, destination_origin)
    if kind is None:
        return None
    if kind == _PROJECTION_IDENTITY:
        return source_arguments
    if kind == _PROJECTION_KEYS:
        if len(source_arguments) != 2:
            return None
        return (source_arguments[0],)

    # A tuple's fixed shape becomes the union of its element types when it is
    # viewed through a homogeneous sequence/iterable interface.
    if _is_ellipsis_argument(source_arguments):
        return source_arguments[:1]
    if not source_arguments:
        return (
            NormalizedType(
                NormalizedKind.SPECIAL,
                SpecialType.NEVER,
                provenance=RepresentationProvenance("typescope.projected.never"),
            ),
        )
    if len(source_arguments) == 1:
        return source_arguments
    return (_make_union(source_arguments),)


def _make_union(members: tuple[NormalizedType, ...]) -> NormalizedType:
    unique_members = tuple(sorted(set(members), key=_semantic_sort_key))
    if len(unique_members) == 1:
        return unique_members[0]
    return NormalizedType(
        NormalizedKind.UNION,
        members=unique_members,
        provenance=RepresentationProvenance("typescope.projected.union"),
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

    builtin_projection = _project_builtin_arguments(
        source_origin, source_arguments, destination_origin
    )
    if builtin_projection is not None:
        return builtin_projection

    parameters = _generic_parameters(source_origin)
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
            base_parameters = _generic_parameters(base_origin)
            base_arguments = typing.get_args(base)
            if base_parameters and not base_arguments:
                # A generic edge without arguments cannot provide a safe
                # substitution.  Let the evaluator report capability unknown.
                continue
            if base_parameters and len(base_parameters) != len(base_arguments):
                continue
            resolved = tuple(
                _resolve_projection_argument(argument, mapping, budget_state)
                for argument in base_arguments
            )
            next_mapping = dict(zip(base_parameters, resolved, strict=False))
            if base_origin is destination_origin:
                if _generic_parameters(base_origin) and not base_arguments:
                    return None
                if _generic_parameters(base_origin) and len(resolved) != len(
                    _generic_parameters(base_origin)
                ):
                    return None
                return resolved
            if base_parameters or getattr(base_origin, "__orig_bases__", ()):
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
    normalized = normalize_type_expression(argument, budget_state=budget_state)
    return _substitute_normalized_type(normalized, mapping)


def _substitute_normalized_type(
    expression: NormalizedType,
    mapping: dict[Any, NormalizedType],
    resolving: frozenset[Any] = frozenset(),
) -> NormalizedType:
    """Apply a generic inheritance substitution to a normalized expression."""

    if expression.kind is NormalizedKind.TYPEVAR:
        value = expression.value
        if value in mapping and value not in resolving:
            return _substitute_normalized_type(
                mapping[value], mapping, resolving | {value}
            )
        return expression
    if not expression.members:
        return expression
    members = tuple(
        _substitute_normalized_type(member, mapping, resolving)
        for member in expression.members
    )
    if members == expression.members:
        return expression
    return NormalizedType(
        expression.kind,
        expression.value,
        members=members,
        provenance=expression.provenance,
    )


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
