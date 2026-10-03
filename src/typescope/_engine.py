"""Native semantic evaluation for the initial TypeScope spine."""

from __future__ import annotations

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
    normalize_type_expression,
)
from ._result import (
    NATIVE_PROFILE,
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
    normalization_budget: NormalizationBudget = field(
        default_factory=NormalizationBudget
    )
    comparison_budget: int = 256
    visited_pairs: set[tuple[NormalizedType, NormalizedType]] = field(
        default_factory=set
    )
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

    return _evaluate(normalized_source, normalized_destination, context).as_result(
        profile,
        provenance=tuple(context.representation_provenance),
        evidence=tuple(context.capability_evidence),
    )


def _evaluate(
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

    special = _evaluate_specials(source, destination, path)
    if special is not None:
        return special

    union = _evaluate_unions(source, destination, context, path)
    if union is not None:
        return union

    return _evaluate_classes(source, destination, context, path)


def _evaluate_specials(
    source: NormalizedType,
    destination: NormalizedType,
    path: tuple[str, ...],
) -> _Decision | None:
    if _is_special(source, SpecialType.ANY) or _is_special(
        destination, SpecialType.ANY
    ):
        return _assignable(path + ("special.any",))
    if source == destination:
        return _assignable(path + ("identity",))
    if _is_special(source, SpecialType.NEVER):
        return _assignable(path + ("special.never.source",))
    if _is_special(destination, SpecialType.NEVER):
        return _not_assignable(path + ("special.never.destination",))
    return _evaluate_none(source, destination, path)


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


def _assignable(path: tuple[str, ...]) -> _Decision:
    return _Decision(
        AssignabilityStatus.ASSIGNABLE,
        rule_source=RuleSource.STANDARD,
        rule_path=path,
    )


def _not_assignable(path: tuple[str, ...]) -> _Decision:
    return _Decision(
        AssignabilityStatus.NOT_ASSIGNABLE,
        rule_source=RuleSource.STANDARD,
        rule_path=path,
        reason_code="assignability.not_assignable",
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
