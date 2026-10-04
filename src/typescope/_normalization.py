"""Normalize the small set of type expressions supported by the native spine."""

from __future__ import annotations

import dataclasses
import inspect
import types
import typing
from collections import abc as collections_abc
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

__all__ = [
    "NormalizationError",
    "NormalizationBudget",
    "NormalizedKind",
    "NormalizedType",
    "RepresentationProvenance",
    "ShapeCompleteness",
    "ShapeOpenness",
    "Completeness",
    "Openness",
    "KeySpec",
    "KeyShape",
    "MemberKind",
    "ParameterSpec",
    "CallableShape",
    "MemberSpec",
    "MemberShape",
    "ProtocolReference",
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
    TYPED_DICT = "typeddict"
    PROTOCOL = "protocol"
    PROTOCOL_REFERENCE = "protocol_reference"


class SpecialType(StrEnum):
    """Special type forms handled before nominal class rules."""

    ANY = "any"
    NEVER = "never"
    NONE = "none"
    UNKNOWN = "unknown"
    ELLIPSIS = "ellipsis"


class ShapeCompleteness(StrEnum):
    """Evidence state for a structural shape.

    ``partial`` is reserved for a shape that is known to be incomplete (for
    example, metadata omitted by a provider).  ``unknown`` means that one or
    more fields could not be resolved safely.  Neither state permits a
    structural assignability decision in the native profile.
    """

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class ShapeOpenness(StrEnum):
    """Supported openness evidence for a mapping schema."""

    OPEN = "open"
    CLOSED = "closed"
    EXTRA_ITEMS = "extra_items"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RepresentationProvenance:
    """Stable carrier metadata retained separately from semantic identity."""

    carrier: str


@dataclass(slots=True)
class NormalizationBudget:
    """Mutable budget shared by both operands in one evaluation."""

    remaining: int = 64
    protocol_shapes: dict[type[Any], MemberShape] = field(default_factory=dict)
    protocol_stack: set[type[Any]] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class NormalizedType:
    """Version-independent semantic input to the evaluator."""

    kind: NormalizedKind
    value: object | None = field(default=None, compare=True, hash=True)
    members: tuple[NormalizedType, ...] = field(default=(), compare=True)
    provenance: RepresentationProvenance = field(
        default=RepresentationProvenance("unknown"), compare=False, hash=False
    )
    shape: KeyShape | MemberShape | None = field(
        default=None, compare=False, hash=False
    )
    member_shape: MemberShape | None = field(default=None, compare=False, hash=False)


@dataclass(frozen=True, slots=True)
class KeySpec:
    """Immutable evidence describing one TypedDict key."""

    value_type: NormalizedType
    required: bool
    read_only: bool
    provenance: RepresentationProvenance | None = field(
        default=None, compare=False, hash=False
    )


@dataclass(frozen=True, slots=True)
class KeyShape:
    """Immutable mapping-schema evidence extracted from a TypedDict."""

    keys: tuple[tuple[str, KeySpec], ...]
    openness: ShapeOpenness
    extra_items: KeySpec | None = None
    completeness: ShapeCompleteness = ShapeCompleteness.COMPLETE
    provenance: RepresentationProvenance = field(
        default=RepresentationProvenance("unknown"), compare=False, hash=False
    )

    def __post_init__(self) -> None:
        # A tuple is the public immutable representation.  Reject duplicate
        # names early so malformed provider evidence cannot be ambiguous.
        names = tuple(name for name, _ in self.keys)
        if len(names) != len(set(names)):
            raise ValueError("TypedDict KeyShape contains duplicate keys")
        if any(not isinstance(name, str) for name in names):
            raise TypeError("TypedDict KeyShape key names must be strings")

    def as_mapping(self) -> Mapping[str, KeySpec]:
        """Return a read-only mapping view for callers that need lookup."""

        return MappingProxyType(dict(self.keys))


class MemberKind(StrEnum):
    """Kinds of members represented by a structural object shape."""

    ATTRIBUTE = "attribute"
    PROPERTY = "property"
    METHOD = "method"


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    """Immutable evidence for one callable parameter."""

    name: str
    kind: str
    value_type: NormalizedType | None
    required: bool
    provenance: RepresentationProvenance | None = field(
        default=None, compare=False, hash=False
    )


@dataclass(frozen=True, slots=True)
class CallableShape:
    """Immutable, bounded evidence for a callable member signature."""

    parameters: tuple[ParameterSpec, ...]
    return_type: NormalizedType | None
    completeness: ShapeCompleteness = ShapeCompleteness.COMPLETE
    provenance: RepresentationProvenance = field(
        default=RepresentationProvenance("unknown"), compare=False, hash=False
    )


@dataclass(frozen=True, slots=True)
class MemberSpec:
    """Immutable evidence describing one object member."""

    value_type: NormalizedType | None
    kind: MemberKind
    read_only: bool = False
    required: bool = True
    signature: CallableShape | None = None
    provenance: RepresentationProvenance | None = field(
        default=None, compare=False, hash=False
    )


@dataclass(frozen=True, slots=True)
class MemberShape:
    """Immutable structural evidence for Protocols and safe class sources."""

    members: tuple[tuple[str, MemberSpec], ...]
    completeness: ShapeCompleteness = ShapeCompleteness.COMPLETE
    provenance: RepresentationProvenance = field(
        default=RepresentationProvenance("unknown"), compare=False, hash=False
    )
    provider: str = "protocol"
    declaration: type[Any] | None = field(default=None, compare=False, hash=False)

    def __post_init__(self) -> None:
        names = tuple(name for name, _ in self.members)
        if len(names) != len(set(names)):
            raise ValueError("MemberShape contains duplicate members")
        if any(not isinstance(name, str) for name in names):
            raise TypeError("MemberShape member names must be strings")

    def as_mapping(self) -> Mapping[str, MemberSpec]:
        """Return a read-only mapping view for member lookup."""

        return MappingProxyType(dict(self.members))


@dataclass(frozen=True, slots=True)
class ProtocolReference:
    """Lazy normalized reference used for recursive Protocol members."""

    declaration: type[Any] = field(compare=False, hash=False)
    shape: MemberShape | None = field(default=None, compare=False, hash=False)


# Short aliases keep the vocabulary convenient for callers while the prefixed
# names make it clear these enums describe shape evidence rather than result
# status.  Both spellings are exported as part of the normalization boundary.
Completeness = ShapeCompleteness
Openness = ShapeOpenness


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

    if _is_typed_dict(expression):
        shape = _normalize_typed_dict(expression, state=state, provenance=provenance)
        # The shape is the semantic identity.  Keeping it in ``value`` means
        # equivalent stdlib and backport declarations compare equal even though
        # their runtime classes (and carriers) differ.  ``shape`` is also
        # exposed explicitly for structural evaluators that need its fields.
        return NormalizedType(
            NormalizedKind.TYPED_DICT,
            shape,
            provenance=provenance,
            shape=shape,
        )

    if _is_protocol(expression):
        if expression in state.protocol_shapes:
            shape = state.protocol_shapes[expression]
            return NormalizedType(
                NormalizedKind.PROTOCOL,
                shape,
                provenance=provenance,
                shape=shape,
                member_shape=shape,
            )
        if expression in state.protocol_stack:
            return NormalizedType(
                NormalizedKind.PROTOCOL_REFERENCE,
                ProtocolReference(expression),
                provenance=provenance,
            )
        state.protocol_stack.add(expression)
        shape = _normalize_member_shape(
            expression,
            state=state,
            provenance=provenance,
            provider="protocol",
        )
        state.protocol_stack.remove(expression)
        state.protocol_shapes[expression] = shape
        return NormalizedType(
            NormalizedKind.PROTOCOL,
            shape,
            provenance=provenance,
            shape=shape,
            member_shape=shape,
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
        member_shape = _normalize_class_member_shape(
            expression, state=state, provenance=provenance
        )
        return NormalizedType(
            NormalizedKind.CLASS,
            expression,
            provenance=provenance,
            member_shape=member_shape,
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


def _is_protocol(expression: Any) -> bool:
    """Detect Protocol declarations through feature-detected public helpers."""

    for module in (
        typing,
        _typing_extensions if "_typing_extensions" in globals() else None,
    ):
        detector = getattr(module, "is_protocol", None)
        if detector is None:
            continue
        try:
            if detector(expression):
                return True
        except (AttributeError, TypeError):
            continue
    # Python 3.11/3.12 have no public detector.  The private marker is used
    # only as a compatibility probe; it never becomes semantic identity.
    return isinstance(expression, type) and bool(
        getattr(expression, "_is_protocol", False)
    )


def _protocol_member_names(expression: type[Any]) -> tuple[tuple[str, ...], bool]:
    """Return declared and inherited Protocol member names plus evidence state."""

    for module in (typing, _typing_extensions):
        getter = getattr(module, "get_protocol_members", None)
        if getter is None:
            continue
        try:
            names = getter(expression)
        except (AttributeError, TypeError):
            continue
        if isinstance(names, (set, frozenset, tuple, list)) and all(
            isinstance(name, str) for name in names
        ):
            return tuple(sorted(names)), True

    names: set[str] = set()
    for base in getattr(expression, "__mro__", (expression,)):
        if base in {typing.Protocol, typing.Generic, object}:
            continue
        annotations = vars(base).get("__annotations__", {})
        if isinstance(annotations, Mapping):
            names.update(name for name in annotations if isinstance(name, str))
        names.update(
            name
            for name in vars(base)
            if isinstance(name, str)
            and (
                not name.startswith("_")
                or name in {"__call__", "__getattr__", "__getattribute__"}
            )
        )
    # An empty Protocol is complete evidence, not a missing member listing.
    return tuple(sorted(names)), True


def _normalize_class_member_shape(
    expression: type[Any],
    *,
    state: NormalizationBudget,
    provenance: RepresentationProvenance,
) -> MemberShape | None:
    """Extract safe static evidence for a concrete class when available."""

    if expression.__module__ == "builtins":
        return None
    provider = "dataclass" if dataclasses.is_dataclass(expression) else "class"
    transformed = any(
        "__dataclass_transform__" in vars(base)
        for base in getattr(expression, "__mro__", (expression,))
    )
    if transformed and provider != "dataclass":
        return MemberShape(
            (),
            completeness=ShapeCompleteness.UNKNOWN,
            provenance=provenance,
            provider="unregistered",
        )
    names: set[str] = set()
    for base in getattr(expression, "__mro__", (expression,)):
        if base is object:
            continue
        annotations = vars(base).get("__annotations__", {})
        if isinstance(annotations, Mapping):
            names.update(name for name in annotations if isinstance(name, str))
        names.update(
            name
            for name, value in vars(base).items()
            if isinstance(name, str)
            and (not name.startswith("_") or name == "__call__")
            and (
                isinstance(value, (property, staticmethod, classmethod))
                or inspect.isfunction(value)
            )
        )
    if dataclasses.is_dataclass(expression):
        try:
            names.update(field.name for field in dataclasses.fields(expression))
        except (TypeError, ValueError):
            return MemberShape(
                (),
                completeness=ShapeCompleteness.UNKNOWN,
                provenance=provenance,
                provider=provider,
            )
    shape = _build_member_shape(
        expression,
        tuple(sorted(names)),
        state=state,
        provenance=provenance,
        provider=provider,
        declaration=expression,
    )
    if any(
        name in vars(base)
        for base in getattr(expression, "__mro__", (expression,))
        if base is not object
        for name in ("__getattr__", "__getattribute__")
    ):
        return MemberShape(
            shape.members,
            completeness=ShapeCompleteness.UNKNOWN,
            provenance=shape.provenance,
            provider=shape.provider,
            declaration=shape.declaration,
        )
    return shape


def _normalize_member_shape(
    expression: type[Any],
    *,
    state: NormalizationBudget,
    provenance: RepresentationProvenance,
    provider: str,
) -> MemberShape:
    names, names_complete = _protocol_member_names(expression)
    return _build_member_shape(
        expression,
        names,
        state=state,
        provenance=provenance,
        provider=provider,
        names_complete=names_complete,
        declaration=expression,
    )


def _build_member_shape(  # noqa: PLR0913 - shape extraction carries explicit evidence
    expression: type[Any],
    names: tuple[str, ...],
    *,
    state: NormalizationBudget,
    provenance: RepresentationProvenance,
    provider: str,
    names_complete: bool = True,
    declaration: type[Any] | None = None,
) -> MemberShape:
    """Build a MemberShape without executing descriptors or annotations."""

    completeness = (
        ShapeCompleteness.COMPLETE if names_complete else ShapeCompleteness.UNKNOWN
    )
    if any(name in {"__getattr__", "__getattribute__"} for name in names):
        completeness = ShapeCompleteness.UNKNOWN
    members: list[tuple[str, MemberSpec]] = []
    declarations: dict[str, list[MemberSpec]] = {}
    for base in getattr(expression, "__mro__", (expression,)):
        if base in {object, typing.Protocol, typing.Generic}:
            continue
        base_names = set(vars(base).get("__annotations__", {}))
        base_names.update(
            name
            for name in vars(base)
            if isinstance(name, str)
            and (not name.startswith("_") or name == "__call__")
        )
        for name in names:
            if name not in base_names:
                continue
            spec, spec_complete = _extract_member_spec(
                base, name, state=state, annotation_owner=expression
            )
            if spec is not None:
                declarations.setdefault(name, []).append(spec)
            if not spec_complete:
                completeness = ShapeCompleteness.UNKNOWN

    for name in names:
        specs = declarations.get(name, [])
        if not specs:
            completeness = ShapeCompleteness.UNKNOWN
            continue
        selected = specs[0]
        # A member explicitly redeclared on the concrete Protocol wins through
        # normal MRO.  Conflicts among inherited declarations are unsafe.
        declared_here = name in vars(expression).get(
            "__annotations__", {}
        ) or name in vars(expression)
        if not declared_here and any(spec != selected for spec in specs[1:]):
            completeness = ShapeCompleteness.UNKNOWN
        members.append((name, selected))

    return MemberShape(
        tuple(sorted(members)),
        completeness=completeness,
        provenance=provenance,
        provider=provider,
        declaration=declaration,
    )


def _extract_member_spec(  # noqa: PLR0911 - ordered descriptor branches
    declaring: type[Any],
    name: str,
    *,
    state: NormalizationBudget,
    annotation_owner: type[Any],
) -> tuple[MemberSpec | None, bool]:
    """Extract one member from a class dictionary using static metadata."""

    annotations = vars(declaring).get("__annotations__", {})
    annotation = (
        annotations.get(name, _MISSING)
        if isinstance(annotations, Mapping)
        else _MISSING
    )
    raw = vars(declaring).get(name, _MISSING)
    member_provenance = RepresentationProvenance(
        f"{declaring.__module__}.{declaring.__qualname__}.{name}"
    )
    if isinstance(raw, property):
        signature, complete = _normalize_property(
            raw, state=state, owner=annotation_owner
        )
        value_type = signature.return_type if signature is not None else None
        return (
            MemberSpec(
                value_type=value_type,
                kind=MemberKind.PROPERTY,
                read_only=raw.fset is None,
                signature=signature,
                provenance=member_provenance,
            ),
            complete,
        )
    if isinstance(raw, staticmethod):
        signature, complete = _normalize_callable_shape(
            raw.__func__, state=state, skip_first=False, owner=annotation_owner
        )
        return MemberSpec(
            None, MemberKind.METHOD, signature=signature, provenance=member_provenance
        ), complete
    if isinstance(raw, classmethod):
        signature, complete = _normalize_callable_shape(
            raw.__func__, state=state, skip_first=True, owner=annotation_owner
        )
        return MemberSpec(
            None, MemberKind.METHOD, signature=signature, provenance=member_provenance
        ), complete
    if inspect.isfunction(raw):
        signature, complete = _normalize_callable_shape(
            raw, state=state, skip_first=True, owner=annotation_owner
        )
        return MemberSpec(
            None, MemberKind.METHOD, signature=signature, provenance=member_provenance
        ), complete
    if annotation is _MISSING:
        if raw is _MISSING:
            return None, False
        return None, False
    if raw is not _MISSING and _is_unsafe_descriptor(raw):
        # Accessing arbitrary descriptors could execute user code and does not
        # provide a safe static member type.
        return None, False
    if _is_unsupported_member_qualifier(annotation):
        return None, False
    value_type, complete = _normalize_member_annotation(
        annotation, owner=annotation_owner, state=state
    )
    if dataclasses.is_dataclass(declaring):
        try:
            field = next(
                (item for item in dataclasses.fields(declaring) if item.name == name),
                None,
            )
        except (TypeError, ValueError):
            field = None
        if field is None and name not in annotations:
            return None, False
        params = getattr(declaring, "__dataclass_params__", None)
        frozen = bool(params and getattr(params, "frozen", False))
    else:
        frozen = False
    return MemberSpec(
        value_type, MemberKind.ATTRIBUTE, read_only=frozen, provenance=member_provenance
    ), complete


def _is_unsafe_descriptor(value: object) -> bool:
    """Detect descriptor protocols from static class dictionaries only."""

    return any(
        name in vars(base)
        for base in type(value).__mro__
        for name in ("__get__", "__set__", "__delete__")
    )


def _is_unsupported_member_qualifier(annotation: Any) -> bool:
    origin = typing.get_origin(annotation)
    return origin in {
        getattr(typing, "ClassVar", object()),
        getattr(typing, "Final", object()),
    }


def _normalize_member_annotation(  # noqa: PLR0911 - ordered annotation boundary
    annotation: Any,
    *,
    owner: type[Any],
    state: NormalizationBudget,
) -> tuple[NormalizedType, bool]:
    if isinstance(annotation, str):
        if annotation in {owner.__name__, owner.__qualname__}:
            return (
                NormalizedType(
                    NormalizedKind.PROTOCOL_REFERENCE,
                    ProtocolReference(owner),
                ),
                True,
            )
        return _unknown_normalized_type(annotation), False
    forward_arg = getattr(annotation, "__forward_arg__", None)
    if isinstance(forward_arg, str):
        if forward_arg in {owner.__name__, owner.__qualname__}:
            return (
                NormalizedType(
                    NormalizedKind.PROTOCOL_REFERENCE,
                    ProtocolReference(owner),
                ),
                True,
            )
        return _unknown_normalized_type(annotation), False
    if isinstance(annotation, type) and _is_protocol(annotation):
        normalized = _normalize(annotation, state=state)
        return normalized, True
    try:
        return _normalize(annotation, state=state), True
    except (NormalizationError, AttributeError, TypeError, ValueError):
        return _unknown_normalized_type(annotation), False


def _normalize_callable_shape(
    function: Any,
    *,
    state: NormalizationBudget,
    skip_first: bool,
    owner: type[Any],
) -> tuple[CallableShape, bool]:
    try:
        signature = inspect.signature(function, eval_str=False)
    except (TypeError, ValueError):
        return CallableShape((), None, ShapeCompleteness.UNKNOWN), False
    parameters = list(signature.parameters.values())
    if skip_first and parameters:
        parameters = parameters[1:]
    complete = True
    normalized_parameters: list[ParameterSpec] = []
    for parameter in parameters:
        if parameter.annotation is inspect.Parameter.empty:
            value_type = _unknown_normalized_type(parameter.name)
            complete = False
        else:
            value_type, parameter_complete = _normalize_member_annotation(
                parameter.annotation, owner=owner, state=state
            )
            complete = complete and parameter_complete
        normalized_parameters.append(
            ParameterSpec(
                parameter.name,
                parameter.kind.name,
                value_type,
                parameter.default is inspect.Parameter.empty
                and parameter.kind
                not in {
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                },
                RepresentationProvenance(_carrier_name(parameter.annotation))
                if parameter.annotation is not inspect.Parameter.empty
                else None,
            )
        )
    if signature.return_annotation is inspect.Signature.empty:
        return_type = None
        complete = False
    else:
        return_type, return_complete = _normalize_member_annotation(
            signature.return_annotation, owner=owner, state=state
        )
        complete = complete and return_complete
    shape = CallableShape(
        tuple(normalized_parameters),
        return_type,
        completeness=ShapeCompleteness.COMPLETE
        if complete
        else ShapeCompleteness.UNKNOWN,
        provenance=RepresentationProvenance(_carrier_name(function)),
    )
    return shape, complete


def _normalize_property(
    property_object: property,
    *,
    state: NormalizationBudget,
    owner: type[Any],
) -> tuple[CallableShape | None, bool]:
    if property_object.fget is None:
        return None, False
    getter, complete = _normalize_callable_shape(
        property_object.fget, state=state, skip_first=True, owner=owner
    )
    if property_object.fset is not None:
        setter, setter_complete = _normalize_callable_shape(
            property_object.fset, state=state, skip_first=True, owner=owner
        )
        complete = complete and setter_complete
        if (
            getter.return_type is not None
            and setter.parameters
            and setter.parameters[0].value_type is not None
            and getter.return_type != setter.parameters[0].value_type
        ):
            complete = False
    return getter, complete


_MISSING = object()
try:  # ``typing_extensions`` is optional and must not be a runtime dependency.
    import typing_extensions as _typing_extensions
except ImportError:  # pragma: no cover - exercised on minimal installations.
    _typing_extensions = None


def _is_typed_dict(expression: Any) -> bool:
    """Detect stdlib and available backport TypedDict declarations."""

    for module in (typing, _typing_extensions):
        detector = getattr(module, "is_typeddict", None)
        if detector is None:
            continue
        try:
            if detector(expression):
                return True
        except (AttributeError, TypeError):
            continue
    return False


def _metadata_name_set(expression: Any, name: str) -> tuple[set[str] | None, bool]:
    """Read a public key-set attribute, returning ``(value, valid)``."""

    raw = getattr(expression, name, _MISSING)
    if raw is _MISSING:
        return None, True
    if isinstance(raw, (set, frozenset, tuple, list)) and all(
        isinstance(item, str) for item in raw
    ):
        return set(raw), True
    return set(), False


def _qualifier_matches(origin: object, name: str) -> bool:
    """Match stdlib and optional-backport typing qualifiers by identity."""

    candidates = [getattr(typing, name, None)]
    if _typing_extensions is not None:
        candidates.append(getattr(_typing_extensions, name, None))
    return any(
        candidate is not None and origin is candidate for candidate in candidates
    )


def _unwrap_typed_dict_annotation(
    annotation: Any,
) -> tuple[Any, bool | None, bool | None, bool]:
    """Strip Required/NotRequired/ReadOnly wrappers from one key annotation."""

    required: bool | None = None
    read_only: bool | None = None
    invalid = False
    current = annotation
    while True:
        origin = typing.get_origin(current)
        if origin is None:
            break
        if _qualifier_matches(origin, "Required"):
            marker = True
        elif _qualifier_matches(origin, "NotRequired"):
            marker = False
        else:
            marker = None
        if marker is not None:
            if required is not None and required != marker:
                invalid = True
            required = marker
        elif _qualifier_matches(origin, "ReadOnly"):
            if read_only is True:
                invalid = True
            read_only = True
        else:
            break
        args = typing.get_args(current)
        if len(args) != 1:
            invalid = True
            break
        current = args[0]
    return current, required, read_only, invalid


def _unknown_normalized_type(annotation: Any) -> NormalizedType:
    return NormalizedType(
        NormalizedKind.SPECIAL,
        SpecialType.UNKNOWN,
        provenance=RepresentationProvenance(_carrier_name(annotation)),
    )


def _normalize_typed_dict(  # noqa: PLR0912, PLR0915 - ordered metadata boundary
    expression: type[Any],
    *,
    state: NormalizationBudget,
    provenance: RepresentationProvenance,
) -> KeyShape:
    """Extract a TypedDict ``KeyShape`` from public runtime metadata."""

    completeness = ShapeCompleteness.COMPLETE
    annotations = getattr(expression, "__annotations__", _MISSING)
    if not isinstance(annotations, Mapping):
        return KeyShape(
            (),
            ShapeOpenness.UNKNOWN,
            completeness=ShapeCompleteness.UNKNOWN,
            provenance=provenance,
        )
    annotation_items = sorted(annotations.items(), key=lambda item: str(item[0]))
    names = {name for name, _ in annotation_items if isinstance(name, str)}
    if len(names) != len(annotation_items):
        completeness = ShapeCompleteness.UNKNOWN

    required_keys, required_valid = _metadata_name_set(expression, "__required_keys__")
    optional_keys, optional_valid = _metadata_name_set(expression, "__optional_keys__")
    if required_keys is None or optional_keys is None:
        completeness = ShapeCompleteness.UNKNOWN
        required_keys = required_keys or set()
        optional_keys = optional_keys or set()
    if not required_valid or not optional_valid:
        completeness = ShapeCompleteness.UNKNOWN
    if required_keys & optional_keys:
        completeness = ShapeCompleteness.UNKNOWN
    if (required_keys | optional_keys) != names:
        completeness = ShapeCompleteness.UNKNOWN

    readonly_keys, readonly_valid = _metadata_name_set(expression, "__readonly_keys__")
    mutable_keys, mutable_valid = _metadata_name_set(expression, "__mutable_keys__")
    if not readonly_valid or not mutable_valid:
        completeness = ShapeCompleteness.UNKNOWN
    if readonly_keys is not None and mutable_keys is not None:
        if readonly_keys & mutable_keys or (readonly_keys | mutable_keys) != names:
            completeness = ShapeCompleteness.UNKNOWN
    elif readonly_keys is not None and not readonly_keys <= names:
        completeness = ShapeCompleteness.UNKNOWN
    elif mutable_keys is not None and not mutable_keys <= names:
        completeness = ShapeCompleteness.UNKNOWN

    specs: list[tuple[str, KeySpec]] = []
    for name, annotation in annotation_items:
        if not isinstance(name, str):
            continue
        value_annotation, required_marker, read_only_marker, invalid = (
            _unwrap_typed_dict_annotation(annotation)
        )
        if invalid:
            completeness = ShapeCompleteness.UNKNOWN
        try:
            value_type = _normalize(value_annotation, state=state)
        except NormalizationError:
            value_type = _unknown_normalized_type(value_annotation)
            completeness = ShapeCompleteness.UNKNOWN

        if required_marker is not None:
            required = required_marker
            if required_marker and name not in required_keys:
                completeness = ShapeCompleteness.UNKNOWN
            if not required_marker and name not in optional_keys:
                completeness = ShapeCompleteness.UNKNOWN
        else:
            required = name in required_keys

        if readonly_keys is not None or mutable_keys is not None:
            read_only = name in (readonly_keys or set())
            if mutable_keys is not None and name in mutable_keys:
                read_only = False
        else:
            read_only = bool(read_only_marker)
            if read_only_marker is not None:
                # A ReadOnly qualifier without the public key-set metadata
                # cannot prove that this runtime exposes its mutability
                # semantics (notably on older backport combinations).
                completeness = ShapeCompleteness.UNKNOWN
        if read_only_marker is not None and read_only_marker != read_only:
            completeness = ShapeCompleteness.UNKNOWN
        specs.append(
            (
                name,
                KeySpec(
                    value_type=value_type,
                    required=required,
                    read_only=read_only,
                    provenance=RepresentationProvenance(_carrier_name(annotation)),
                ),
            )
        )

    openness, extra_items, openness_complete = _normalize_typed_dict_openness(
        expression, state=state, provenance=provenance
    )
    if not openness_complete:
        completeness = ShapeCompleteness.UNKNOWN
    return KeyShape(
        tuple(specs),
        openness,
        extra_items=extra_items,
        completeness=completeness,
        provenance=provenance,
    )


def _normalize_typed_dict_openness(  # noqa: PLR0911 - explicit openness branches
    expression: type[Any],
    *,
    state: NormalizationBudget,
    provenance: RepresentationProvenance,
) -> tuple[ShapeOpenness, KeySpec | None, bool]:
    """Read optional closed/extra-items metadata without guessing."""

    closed = getattr(expression, "__closed__", _MISSING)
    extra = getattr(expression, "__extra_items__", _MISSING)
    no_extra_items = _no_extra_items_sentinel()
    if closed is _MISSING and extra is _MISSING:
        # Legacy TypedDict declarations are open by specification.  The
        # absence of newer closed/extra metadata is therefore known evidence.
        return ShapeOpenness.OPEN, None, True
    if closed is not _MISSING and closed is not None and not isinstance(closed, bool):
        return ShapeOpenness.UNKNOWN, None, False
    if extra is _MISSING or extra is None or extra is no_extra_items:
        return (
            ShapeOpenness.CLOSED if closed is True else ShapeOpenness.OPEN,
            None,
            True,
        )
    if _is_never_type(extra):
        return ShapeOpenness.CLOSED, None, True
    value_annotation, _, read_only_marker, invalid = _unwrap_typed_dict_annotation(
        extra
    )
    if invalid:
        return ShapeOpenness.UNKNOWN, None, False
    if read_only_marker and (
        getattr(expression, "__readonly_keys__", _MISSING) is _MISSING
        or getattr(expression, "__mutable_keys__", _MISSING) is _MISSING
    ):
        return ShapeOpenness.UNKNOWN, None, False
    try:
        value_type = _normalize(value_annotation, state=state)
    except NormalizationError:
        return ShapeOpenness.UNKNOWN, None, False
    spec = KeySpec(
        value_type=value_type,
        required=False,
        read_only=bool(read_only_marker),
        provenance=RepresentationProvenance(_carrier_name(extra)),
    )
    return ShapeOpenness.EXTRA_ITEMS, spec, True


def _no_extra_items_sentinel() -> object:
    """Return the optional typing sentinel used by PEP 728 backports."""

    for module in (typing, _typing_extensions):
        sentinel = getattr(module, "NoExtraItems", _MISSING)
        if sentinel is not _MISSING:
            return sentinel
    return _MISSING


def _is_never_type(expression: object) -> bool:
    """Recognize ``Never`` sentinels used for closed extra-item metadata."""

    return any(
        expression is getattr(module, name, None)
        for module in (typing, _typing_extensions)
        for name in ("Never", "NoReturn")
    )


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
    parameters = _generic_parameters(origin)
    if parameters:
        return len(parameters)
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
    else:
        _validate_generic_arguments(origin, arguments)

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

    bare_tuple = getattr(typing, "Tuple", None)
    return expression is not bare_tuple and not typing.get_args(expression)


def _validate_generic_arguments(origin: type[Any], arguments: tuple[Any, ...]) -> None:
    """Reject malformed fixed-arity forms before semantic comparison."""

    if origin is tuple:
        has_ellipsis = any(argument is Ellipsis for argument in arguments)
        if has_ellipsis and not (
            len(arguments) == 1 or (len(arguments) == 2 and arguments[-1] is Ellipsis)
        ):
            raise NormalizationError(
                "normalization.generic_arity",
                "tuple ellipsis must be the second and final argument",
            )
        return

    arity = _generic_arity(origin)
    if arity and len(arguments) != arity:
        raise NormalizationError(
            "normalization.generic_arity",
            f"{origin!r} expects {arity} generic argument(s), got {len(arguments)}",
        )


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
            collections_abc.Reversible,
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
            collections_abc.Reversible,
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
            projected_base = _project_builtin_arguments(
                base_origin, resolved, destination_origin
            )
            if projected_base is not None:
                return projected_base
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
        shape=expression.shape,
        member_shape=expression.member_shape,
    )


def _semantic_sort_key(  # noqa: PLR0911 - one branch per normalized kind
    expression: NormalizedType,
) -> tuple[str, str]:
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
    if expression.kind is NormalizedKind.TYPED_DICT:
        shape = expression.value
        assert isinstance(shape, KeyShape)
        keys = ",".join(
            f"{name}:{int(spec.required)}:{int(spec.read_only)}:"
            f"{':'.join(_semantic_sort_key(spec.value_type))}"
            for name, spec in shape.keys
        )
        extra = ""
        if shape.extra_items is not None:
            extra = (
                ":extra="
                f"{int(shape.extra_items.read_only)}:"
                f"{':'.join(_semantic_sort_key(shape.extra_items.value_type))}"
            )
        return (
            expression.kind.value,
            f"{shape.openness.value}:{shape.completeness.value}:{keys}{extra}",
        )
    if expression.kind is NormalizedKind.PROTOCOL:
        shape = expression.value
        assert isinstance(shape, MemberShape)
        members = ",".join(
            f"{name}:{spec.kind.value}:{int(spec.read_only)}:"
            f"{':'.join(_semantic_sort_key(spec.value_type)) if spec.value_type is not None else ''}:"
            f"{_callable_sort_key(spec.signature)}"
            for name, spec in shape.members
        )
        return (
            expression.kind.value,
            f"{shape.completeness.value}:{members}",
        )
    if expression.kind is NormalizedKind.PROTOCOL_REFERENCE:
        reference = expression.value
        assert isinstance(reference, ProtocolReference)
        return (
            expression.kind.value,
            f"{reference.declaration.__module__}.{reference.declaration.__qualname__}",
        )
    return (
        expression.kind.value,
        ",".join(":".join(_semantic_sort_key(member)) for member in expression.members),
    )


def _callable_sort_key(signature: CallableShape | None) -> str:
    if signature is None:
        return ""
    parameters = ",".join(
        f"{parameter.name}:{parameter.kind}:{int(parameter.required)}:"
        f"{':'.join(_semantic_sort_key(parameter.value_type)) if parameter.value_type is not None else ''}"
        for parameter in signature.parameters
    )
    result = (
        ":".join(_semantic_sort_key(signature.return_type))
        if signature.return_type is not None
        else ""
    )
    return f"{signature.completeness.value}:{parameters}->{result}"
