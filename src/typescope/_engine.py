"""Native semantic evaluation for the initial TypeScope spine."""

from __future__ import annotations

import typing
from dataclasses import dataclass, field
from typing import Any

from ._assignability_config import (
    AssignabilityConfig,
    AssignabilityConfigDict,
    make_assignability_config,
)
from ._normalization import (
    NormalizationBudget,
    NormalizationError,
    NormalizedKind,
    NormalizedType,
    SpecialType,
    generic_variances,
    normalize_type_expression,
    project_generic_arguments,
)
from ._result import (
    NATIVE_PROFILE,
    UNKNOWN_AS_ANY_PROFILE,
    AssignabilityResult,
    AssignabilityStatus,
    RuleSource,
)

__all__ = ["evaluate_native"]


@dataclass(slots=True)
class EvaluationContext:
    """Bounded state for one native assignability evaluation."""

    profile: str
    config: AssignabilityConfig
    unknown_as_any: bool = False
    normalization_budget: NormalizationBudget = field(
        default_factory=NormalizationBudget
    )
    comparison_budget: int = 256
    visited_pairs: set[tuple[NormalizedType, NormalizedType]] = field(
        default_factory=set
    )
    typevar_bindings: dict[typing.TypeVar, NormalizedType] = field(default_factory=dict)
    current_rule_path: tuple[str, ...] = ()
    capability_evidence: list[str] = field(default_factory=list)
    representation_provenance: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Decision:
    status: AssignabilityStatus
    rule_source: RuleSource | None = None
    rule_path: tuple[str, ...] = ()
    reason_code: str | None = None
    detail: str | None = None

    def as_result(
        self,
        profile: str,
        *,
        provenance: tuple[str, ...] = (),
        evidence: tuple[str, ...] = (),
    ) -> AssignabilityResult:
        return AssignabilityResult(
            self.status,
            profile=profile,
            rule_source=self.rule_source,
            rule_path=self.rule_path,
            reason_code=self.reason_code,
            detail=self.detail,
            provenance=provenance,
            evidence=evidence,
        )


def evaluate_native(
    source: Any,
    destination: Any,
    *,
    profile: str = NATIVE_PROFILE,
    config: AssignabilityConfigDict | None = None,
) -> AssignabilityResult:
    """Evaluate two expressions under the native semantic profile."""

    context = EvaluationContext(
        profile=profile,
        config=make_assignability_config(config),
        unknown_as_any=profile == UNKNOWN_AS_ANY_PROFILE,
    )
    try:
        normalized_source = normalize_type_expression(
            source,
            budget_state=context.normalization_budget,
        )
        context.representation_provenance.append(normalized_source.provenance.carrier)
        normalized_destination = normalize_type_expression(
            destination,
            budget_state=context.normalization_budget,
        )
        context.representation_provenance.append(
            normalized_destination.provenance.carrier
        )
    except NormalizationError as exc:
        context.capability_evidence.append(exc.reason_code)
        return _Decision(
            AssignabilityStatus.UNKNOWN,
            rule_source=RuleSource.EXTENSION,
            rule_path=("normalization",),
            reason_code=exc.reason_code,
            detail=exc.detail,
        ).as_result(
            profile,
            provenance=tuple(context.representation_provenance),
            evidence=tuple(context.capability_evidence),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        context.capability_evidence.append("normalization.expression_unsupported")
        return _Decision(
            AssignabilityStatus.UNKNOWN,
            rule_source=RuleSource.EXTENSION,
            rule_path=("normalization",),
            reason_code="normalization.expression_unsupported",
            detail=str(exc) or type(exc).__name__,
        ).as_result(
            profile,
            provenance=tuple(context.representation_provenance),
            evidence=tuple(context.capability_evidence),
        )

    try:
        decision = _evaluate(normalized_source, normalized_destination, context)
    except NormalizationError as exc:
        context.capability_evidence.append(exc.reason_code)
        decision = _Decision(
            AssignabilityStatus.UNKNOWN,
            rule_source=RuleSource.EXTENSION,
            rule_path=("normalization",),
            reason_code=exc.reason_code,
            detail=exc.detail,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        context.capability_evidence.append("normalization.expression_unsupported")
        decision = _Decision(
            AssignabilityStatus.UNKNOWN,
            rule_source=RuleSource.EXTENSION,
            rule_path=("normalization",),
            reason_code="normalization.expression_unsupported",
            detail=str(exc) or type(exc).__name__,
        )
    return decision.as_result(
        profile,
        provenance=tuple(context.representation_provenance),
        evidence=tuple(context.capability_evidence),
    )


def _evaluate(  # noqa: PLR0911 - ordered semantic dispatch
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...] = (),
) -> _Decision:
    context.current_rule_path = path
    if context.comparison_budget <= 0:
        return _unknown(
            context,
            path,
            "evaluation.budget_exhausted",
            "assignability evaluation exceeded its comparison budget",
        )
    context.comparison_budget -= 1

    pair = (source, destination)
    if pair in context.visited_pairs:
        return _unknown(
            context,
            path,
            "evaluation.cycle",
            "assignability evaluation encountered a recursive comparison",
        )
    context.visited_pairs.add(pair)
    try:
        special = _evaluate_specials(source, destination, context, path)
        if special is not None:
            return special

        union = _evaluate_unions(source, destination, context, path)
        if union is not None:
            return union

        generic = _evaluate_generics(source, destination, context, path)
        if generic is not None:
            return generic

        typevar = _evaluate_typevars(source, destination, context, path)
        if typevar is not None:
            return typevar

        return _evaluate_classes(source, destination, context, path)
    finally:
        context.visited_pairs.remove(pair)


def _evaluate_specials(  # noqa: PLR0911 - ordered special-type dispatch
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision | None:
    if _contains_special(source, SpecialType.UNKNOWN) or _contains_special(
        destination, SpecialType.UNKNOWN
    ):
        if context.unknown_as_any:
            return _assignable(
                path + ("special.unknown_as_any",),
                rule_source=RuleSource.CHECKER,
            )
        return _not_assignable(
            path + ("special.unknown",),
            reason_code="assignability.unknown_type",
            rule_source=RuleSource.EXTENSION,
        )
    if _is_special(source, SpecialType.ANY) or _is_special(
        destination, SpecialType.ANY
    ):
        return _assignable(path + ("special.any",))
    if source == destination and not (
        _contains_special(source, SpecialType.UNKNOWN)
        or _contains_special(destination, SpecialType.UNKNOWN)
    ):
        return _assignable(path + ("identity",))
    if _is_special(source, SpecialType.NEVER):
        return _assignable(path + ("special.never.source",))
    if _is_special(destination, SpecialType.NEVER):
        return _not_assignable(path + ("special.never.destination",))
    return _evaluate_none(source, destination, path)


def _evaluate_generics(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision | None:
    source_is_generic = source.kind is NormalizedKind.GENERIC
    destination_is_generic = destination.kind is NormalizedKind.GENERIC
    if not source_is_generic and not destination_is_generic:
        return None

    if source_is_generic and destination_is_generic:
        return _evaluate_generic_to_generic(source, destination, context, path)

    if source_is_generic:
        return _evaluate_generic_to_class(source, destination, context, path)

    # A bare class carries no evidence for the destination's type arguments.
    # Keep nominal subclassing useful, but never invent an argument binding.
    return _evaluate_class_to_generic(source, destination, context, path)


def _evaluate_generic_to_generic(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    source_origin = source.value
    destination_origin = destination.value
    assert isinstance(source_origin, type)
    assert isinstance(destination_origin, type)

    projected = project_generic_arguments(
        source_origin,
        source.members,
        destination_origin,
        budget_state=context.normalization_budget,
    )
    if projected is not None:
        return _compare_generic_arguments(
            projected,
            destination.members,
            destination_origin,
            context,
            path,
        )

    try:
        related = issubclass(source_origin, destination_origin)
    except TypeError:
        related = False
    if related:
        return _unknown(
            context,
            path + ("generic.inheritance",),
            "generic.inheritance_unknown",
            "generic inheritance arguments could not be projected",
        )
    return _not_assignable(path + ("generic.origin_mismatch",))


def _evaluate_generic_to_class(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    source_origin = source.value
    destination_class = destination.value
    assert isinstance(source_origin, type)
    if destination.kind is not NormalizedKind.CLASS:
        return _unknown(
            context,
            path,
            "normalization.expression_unsupported",
            "the normalized generic destination is outside the native spine",
        )
    assert isinstance(destination_class, type)
    try:
        related = issubclass(source_origin, destination_class)
    except TypeError as exc:
        return _unknown(context, path, "normalization.expression_unsupported", str(exc))
    return (
        _assignable(path + ("generic.nominal",))
        if related
        else _not_assignable(path + ("nominal.mismatch",))
    )


def _evaluate_class_to_generic(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    source_class = source.value
    destination_origin = destination.value
    assert isinstance(source_class, type)
    assert isinstance(destination_origin, type)
    try:
        related = issubclass(source_class, destination_origin)
    except TypeError as exc:
        return _unknown(context, path, "normalization.expression_unsupported", str(exc))
    if not related:
        return _not_assignable(path + ("generic.origin_mismatch",))
    return _unknown(
        context,
        path + ("generic.arguments",),
        "generic.arguments_missing",
        "the source class has no runtime evidence for generic arguments",
    )


def _evaluate_typevars(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision | None:
    source_is_typevar = source.kind is NormalizedKind.TYPEVAR
    destination_is_typevar = destination.kind is NormalizedKind.TYPEVAR
    if not source_is_typevar and not destination_is_typevar:
        return None
    if source_is_typevar and destination_is_typevar:
        return _unknown(
            context,
            path + ("typevar.identity",),
            "typevar.binding_unknown",
            "independent TypeVars cannot be unified without binding evidence",
        )

    if destination_is_typevar:
        typevar = destination.value
        assert isinstance(typevar, typing.TypeVar)
        return _typevar_accepts(source, typevar, context, path)

    typevar = source.value
    assert isinstance(typevar, typing.TypeVar)
    return _typevar_produces(typevar, destination, context, path)


def _typevar_accepts(  # noqa: PLR0911 - explicit constraint branches
    source: NormalizedType,
    typevar: typing.TypeVar,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    constraints = typevar.__constraints__
    existing = context.typevar_bindings.get(typevar)
    if existing is not None:
        return _evaluate(source, existing, context, path + ("typevar.binding",))
    if constraints:
        candidates: list[NormalizedType] = []
        unknown: _Decision | None = None
        for index, constraint in enumerate(constraints):
            candidate = _normalize_typevar_target(constraint, context)
            bindings_before = dict(context.typevar_bindings)
            decision = _evaluate(
                source,
                candidate,
                context,
                path + (f"typevar.constraint[{index}]",),
            )
            context.typevar_bindings.clear()
            context.typevar_bindings.update(bindings_before)
            if decision.status is AssignabilityStatus.ASSIGNABLE:
                candidates.append(candidate)
            if decision.status is AssignabilityStatus.UNKNOWN:
                unknown = decision
        if not candidates:
            return unknown or _not_assignable(path + ("typevar.constraints",))
        if len(candidates) > 1:
            exact = [candidate for candidate in candidates if candidate == source]
            if len(exact) != 1:
                if _is_special(source, SpecialType.ANY):
                    context.typevar_bindings[typevar] = source
                    return _assignable(path + ("typevar.bind",))
                return _unknown(
                    context,
                    path + ("typevar.binding",),
                    "typevar.binding_unknown",
                    "multiple TypeVar constraints accept the source expression",
                )
            selected = exact[0]
        else:
            selected = candidates[0]
        context.typevar_bindings[typevar] = selected
        return _assignable(path + ("typevar.bind",))

    if typevar.__bound__ is not None:
        bound = _normalize_typevar_target(typevar.__bound__, context)
        decision = _evaluate(source, bound, context, path + ("typevar.bound",))
        if decision.status is not AssignabilityStatus.ASSIGNABLE:
            return decision
    context.typevar_bindings[typevar] = source
    return _assignable(path + ("typevar.bind",))


def _typevar_produces(  # noqa: PLR0911 - ordered TypeVar evidence rules
    typevar: typing.TypeVar,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    existing = context.typevar_bindings.get(typevar)
    if existing is not None:
        return _evaluate(existing, destination, context, path + ("typevar.binding",))

    constraints = typevar.__constraints__
    if constraints:
        unknown: _Decision | None = None
        assignable = False
        not_assignable = False
        for index, constraint in enumerate(constraints):
            decision = _evaluate(
                _normalize_typevar_target(constraint, context),
                destination,
                context,
                path + (f"typevar.constraint[{index}]",),
            )
            if decision.status is AssignabilityStatus.ASSIGNABLE:
                assignable = True
            elif decision.status is AssignabilityStatus.NOT_ASSIGNABLE:
                not_assignable = True
            if decision.status is AssignabilityStatus.UNKNOWN:
                unknown = decision
        if unknown is not None:
            return unknown
        if assignable and not_assignable:
            return _unknown(
                context,
                path + ("typevar.binding",),
                "typevar.binding_unknown",
                "not every constrained TypeVar instantiation satisfies the destination",
            )
        if not_assignable:
            return _not_assignable(path + ("typevar.constraints",))
        return _assignable(path + ("typevar.constraints",))

    if typevar.__bound__ is not None:
        return _evaluate(
            _normalize_typevar_target(typevar.__bound__, context),
            destination,
            context,
            path + ("typevar.bound",),
        )

    no_default = getattr(typing, "NoDefault", object())
    default = getattr(typevar, "__default__", no_default)
    if default is not no_default:
        return _evaluate(
            _normalize_typevar_target(default, context),
            destination,
            context,
            path + ("typevar.default",),
        )
    return _unknown(
        context,
        path + ("typevar",),
        "typevar.binding_unknown",
        "a free source TypeVar has no bound, constraint, or default",
    )


def _normalize_typevar_target(
    expression: Any,
    context: EvaluationContext,
) -> NormalizedType:
    return normalize_type_expression(
        expression,
        budget_state=context.normalization_budget,
    )


def _normalize_runtime_value(
    expression: object,
    context: EvaluationContext,
) -> NormalizedType:
    return normalize_type_expression(
        expression,
        budget_state=context.normalization_budget,
    )


def _compare_generic_arguments(  # noqa: PLR0911, PLR0912 - variance branches
    source: tuple[NormalizedType, ...],
    destination: tuple[NormalizedType, ...],
    destination_origin: type[Any],
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    source_args, destination_args = _expand_generic_shape(source, destination)
    if source_args is None or destination_args is None:
        return _unknown(
            context,
            path + ("generic.arguments",),
            "generic.arity_unknown",
            "generic argument arity could not be compared safely",
        )
    if len(source_args) != len(destination_args):
        return _not_assignable(path + ("generic.arity",))

    variances = generic_variances(destination_origin)
    if variances is not None and len(variances) == 1 and len(destination_args) > 1:
        variances = variances * len(destination_args)
    if variances is None or len(variances) != len(destination_args):
        return _unknown(
            context,
            path + ("generic.arguments",),
            "generic.variance_unknown",
            "generic variance metadata is unavailable",
        )

    unknown: _Decision | None = None
    rule_source = RuleSource.STANDARD
    for index, (source_arg, destination_arg, variance) in enumerate(
        zip(source_args, destination_args, variances, strict=True)
    ):
        argument_path = path + (f"generic.argument[{index}]",)
        if variance == "covariant":
            decision = _evaluate(source_arg, destination_arg, context, argument_path)
        elif variance == "contravariant":
            if source_arg.kind is NormalizedKind.TYPEVAR:
                typevar = source_arg.value
                assert isinstance(typevar, typing.TypeVar)
                decision = _evaluate_source_typevar_contravariant(
                    typevar, destination_arg, context, argument_path
                )
            elif destination_arg.kind is NormalizedKind.TYPEVAR:
                typevar = destination_arg.value
                assert isinstance(typevar, typing.TypeVar)
                decision = _typevar_accepts_reverse(
                    source_arg, typevar, context, argument_path
                )
            else:
                decision = _evaluate(
                    destination_arg, source_arg, context, argument_path
                )
        else:
            forward = _evaluate(source_arg, destination_arg, context, argument_path)
            reverse = (
                forward
                if source_arg == destination_arg
                else _evaluate(destination_arg, source_arg, context, argument_path)
            )
            if (
                forward.status is AssignabilityStatus.NOT_ASSIGNABLE
                or reverse.status is AssignabilityStatus.NOT_ASSIGNABLE
            ):
                if any(
                    decision.reason_code == "assignability.unknown_type"
                    for decision in (forward, reverse)
                ):
                    return _not_assignable(
                        argument_path + ("invariant",),
                        reason_code="assignability.unknown_type",
                        rule_source=RuleSource.EXTENSION,
                    )
                return _not_assignable(argument_path + ("invariant",))
            decision = (
                forward if forward.status is AssignabilityStatus.UNKNOWN else reverse
            )
        if decision.status is AssignabilityStatus.NOT_ASSIGNABLE:
            return decision
        if decision.status is AssignabilityStatus.UNKNOWN:
            unknown = decision
        if decision.rule_source is RuleSource.CHECKER:
            rule_source = RuleSource.CHECKER
    return unknown or _assignable(path + ("generic",), rule_source=rule_source)


def _evaluate_source_typevar_contravariant(  # noqa: PLR0911 - ordered TypeVar rules
    typevar: typing.TypeVar,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    """Keep a source TypeVar unbound when a contravariant edge is reversed."""

    if _is_special(destination, SpecialType.ANY):
        return _assignable(path + ("special.any",))
    if _is_special(destination, SpecialType.NEVER):
        return _assignable(path + ("special.never.source",))
    if _is_special(destination, SpecialType.UNKNOWN):
        return (
            _assignable(
                path + ("special.unknown_as_any",),
                rule_source=RuleSource.CHECKER,
            )
            if context.unknown_as_any
            else _not_assignable(
                path + ("special.unknown",),
                reason_code="assignability.unknown_type",
                rule_source=RuleSource.EXTENSION,
            )
        )

    constraints = typevar.__constraints__
    if constraints:
        unknown = False
        for constraint in constraints:
            candidate = _normalize_typevar_target(constraint, context)
            decision = _evaluate(destination, candidate, context, path)
            if decision.status is AssignabilityStatus.UNKNOWN:
                unknown = True
            elif decision.status is AssignabilityStatus.NOT_ASSIGNABLE:
                unknown = True
        if unknown:
            return _unknown(
                context,
                path + ("typevar.binding",),
                "typevar.binding_unknown",
                "a source TypeVar is not proven for every contravariant instantiation",
            )
        return _assignable(path + ("typevar.constraints",))

    no_default = getattr(typing, "NoDefault", object())
    default = getattr(typevar, "__default__", no_default)
    if default is not no_default:
        return _evaluate(
            destination,
            _normalize_typevar_target(default, context),
            context,
            path + ("typevar.default",),
        )
    return _unknown(
        context,
        path + ("typevar.binding",),
        "typevar.binding_unknown",
        "a source TypeVar cannot be bound from contravariant destination evidence",
    )


def _typevar_accepts_reverse(  # noqa: PLR0911, PLR0912 - explicit constraint branches
    source: NormalizedType,
    typevar: typing.TypeVar,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    """Bind a destination TypeVar discovered through a contravariant edge."""

    if _is_special(source, SpecialType.UNKNOWN):
        typevar_expression = NormalizedType(
            NormalizedKind.TYPEVAR,
            typevar,
        )
        return _evaluate(typevar_expression, source, context, path)
    if _is_special(source, SpecialType.ANY):
        context.typevar_bindings[typevar] = source
        return _assignable(path + ("typevar.bind",))

    existing = context.typevar_bindings.get(typevar)
    if existing is not None:
        return _evaluate(existing, source, context, path + ("typevar.binding",))

    constraints = typevar.__constraints__
    if constraints:
        candidates: list[NormalizedType] = []
        unknown: _Decision | None = None
        for index, constraint in enumerate(constraints):
            candidate = _normalize_typevar_target(constraint, context)
            bindings_before = dict(context.typevar_bindings)
            decision = _evaluate(
                candidate,
                source,
                context,
                path + (f"typevar.constraint[{index}]",),
            )
            context.typevar_bindings.clear()
            context.typevar_bindings.update(bindings_before)
            if decision.status is AssignabilityStatus.ASSIGNABLE:
                candidates.append(candidate)
            elif decision.status is AssignabilityStatus.UNKNOWN:
                unknown = decision
        if not candidates:
            return unknown or _not_assignable(path + ("typevar.constraints",))
        if len(candidates) > 1:
            exact = [candidate for candidate in candidates if candidate == source]
            if len(exact) != 1:
                return _unknown(
                    context,
                    path + ("typevar.binding",),
                    "typevar.binding_unknown",
                    "multiple TypeVar constraints accept the contravariant evidence",
                )
            selected = exact[0]
        else:
            selected = candidates[0]
        context.typevar_bindings[typevar] = selected
        return _assignable(path + ("typevar.bind",))

    if typevar.__bound__ is not None:
        bound = _normalize_typevar_target(typevar.__bound__, context)
        source_to_bound = _evaluate(source, bound, context, path + ("typevar.bound",))
        if source_to_bound.status is AssignabilityStatus.ASSIGNABLE:
            context.typevar_bindings[typevar] = source
            return _assignable(path + ("typevar.bind",))
        bound_to_source = _evaluate(bound, source, context, path + ("typevar.bound",))
        if bound_to_source.status is AssignabilityStatus.ASSIGNABLE:
            context.typevar_bindings[typevar] = bound
            return _assignable(path + ("typevar.bind",))
        if (
            source_to_bound.status is AssignabilityStatus.UNKNOWN
            or bound_to_source.status is AssignabilityStatus.UNKNOWN
        ):
            return (
                source_to_bound
                if source_to_bound.status is AssignabilityStatus.UNKNOWN
                else bound_to_source
            )
        return _not_assignable(path + ("typevar.bound",))

    context.typevar_bindings[typevar] = source
    return _assignable(path + ("typevar.bind",))


def _expand_generic_shape(
    source: tuple[NormalizedType, ...],
    destination: tuple[NormalizedType, ...],
) -> tuple[tuple[NormalizedType, ...] | None, tuple[NormalizedType, ...] | None]:
    source_variadic = _is_ellipsis_argument(source)
    destination_variadic = _is_ellipsis_argument(destination)
    if destination_variadic:
        destination_item = destination[0]
        if source_variadic:
            return (source[:1], (destination_item,))
        if not source:
            empty_source = NormalizedType(
                NormalizedKind.SPECIAL,
                SpecialType.NEVER,
                provenance=destination_item.provenance,
            )
            return ((empty_source,), (destination_item,))
        return (source, (destination_item,) * len(source))
    if source_variadic:
        return (None, None)
    return source, destination


def _is_ellipsis_argument(arguments: tuple[NormalizedType, ...]) -> bool:
    return bool(arguments) and _is_special(arguments[-1], SpecialType.ELLIPSIS)


def _evaluate_none(
    source: NormalizedType,
    destination: NormalizedType,
    path: tuple[str, ...],
) -> _Decision | None:
    if source.kind is NormalizedKind.UNION or destination.kind is NormalizedKind.UNION:
        return None
    if _is_special(source, SpecialType.NONE):
        if destination.kind is NormalizedKind.CLASS and destination.value is object:
            return _assignable(path + ("special.none_to_object",))
        return _not_assignable(path + ("special.none",))
    if _is_special(destination, SpecialType.NONE):
        return _not_assignable(path + ("special.none",))
    return None


def _evaluate_unions(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision | None:
    if source.kind is NormalizedKind.UNION:
        return _evaluate_source_union(source, destination, context, path)
    if destination.kind is NormalizedKind.UNION:
        return _evaluate_destination_union(source, destination, context, path)
    return None


def _evaluate_source_union(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    unknown: _Decision | None = None
    for index, member in enumerate(source.members):
        decision = _evaluate(
            member,
            destination,
            context,
            path + (f"union.member[{index}]",),
        )
        if decision.status is AssignabilityStatus.NOT_ASSIGNABLE:
            return decision
        if decision.status is AssignabilityStatus.UNKNOWN:
            unknown = decision
    return unknown or _assignable(path + ("union.source",))


def _evaluate_destination_union(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    unknown: _Decision | None = None
    for index, member in enumerate(destination.members):
        decision = _evaluate(
            source,
            member,
            context,
            path + (f"union.member[{index}]",),
        )
        if decision.status is AssignabilityStatus.ASSIGNABLE:
            return decision
        if decision.status is AssignabilityStatus.UNKNOWN:
            unknown = decision
    return unknown or _not_assignable(path + ("union.destination",))


def _evaluate_classes(
    source: NormalizedType,
    destination: NormalizedType,
    context: EvaluationContext,
    path: tuple[str, ...],
) -> _Decision:
    if (
        source.kind is not NormalizedKind.CLASS
        or destination.kind is not NormalizedKind.CLASS
    ):
        return _unknown(
            context,
            path,
            "normalization.expression_unsupported",
            "the normalized expression is outside the native evaluation spine",
        )

    source_class = source.value
    destination_class = destination.value
    assert isinstance(source_class, type)
    assert isinstance(destination_class, type)

    if source_class is bool and destination_class is int:
        return (
            _assignable(path + ("nominal.bool_to_int",))
            if context.config.allow_bool_to_int
            else _not_assignable(path + ("nominal.bool_to_int",))
        )

    if (source_class, destination_class) in {
        (int, float),
        (int, complex),
        (float, complex),
    }:
        return _assignable(path + ("numeric.promotion",))

    try:
        assignable = issubclass(source_class, destination_class)
    except TypeError as exc:
        return _unknown(
            context,
            path,
            "normalization.expression_unsupported",
            str(exc),
        )
    if assignable:
        return _assignable(path + ("nominal.inheritance",))
    return _not_assignable(path + ("nominal.mismatch",))


def _is_special(expression: NormalizedType, special: SpecialType) -> bool:
    return expression.kind is NormalizedKind.SPECIAL and expression.value is special


def _contains_special(expression: NormalizedType, special: SpecialType) -> bool:
    return _is_special(expression, special) or any(
        _contains_special(member, special) for member in expression.members
    )


def _assignable(
    path: tuple[str, ...],
    *,
    rule_source: RuleSource = RuleSource.STANDARD,
) -> _Decision:
    return _Decision(
        AssignabilityStatus.ASSIGNABLE,
        rule_source=rule_source,
        rule_path=path,
    )


def _not_assignable(
    path: tuple[str, ...],
    *,
    reason_code: str = "assignability.not_assignable",
    rule_source: RuleSource = RuleSource.STANDARD,
) -> _Decision:
    return _Decision(
        AssignabilityStatus.NOT_ASSIGNABLE,
        rule_source=rule_source,
        rule_path=path,
        reason_code=reason_code,
    )


def _unknown(
    context: EvaluationContext,
    path: tuple[str, ...],
    reason_code: str,
    detail: str,
) -> _Decision:
    context.capability_evidence.append(reason_code)
    return _Decision(
        AssignabilityStatus.UNKNOWN,
        rule_source=RuleSource.EXTENSION,
        rule_path=path,
        reason_code=reason_code,
        detail=detail,
    )
