"""Public API for structured and Boolean assignability checks."""

from typing import Any, Literal, overload

from ._assignability_config import AssignabilityConfigDict
from ._engine import evaluate_native
from ._result import (
    NATIVE_PROFILE,
    AssignabilityCapabilityError,
    AssignabilityResult,
    AssignabilityStatus,
    RuleSource,
    UnknownPolicy,
)

__all__ = ["evaluate_assignability", "is_assignable"]

_UNKNOWN_POLICIES = frozenset(("return_none", "return_true", "return_false", "raise"))


def evaluate_assignability(
    source: Any,
    destination: Any,
    *,
    profile: str = NATIVE_PROFILE,
) -> AssignabilityResult:
    """Evaluate whether ``source`` can be assigned to ``destination``.

    The first reconstruction accepts resolved runtime type expressions. Unsupported
    profiles and expressions produce an ``unknown`` result instead of being treated
    as a definite negative answer.
    """

    if profile != NATIVE_PROFILE:
        return AssignabilityResult(
            AssignabilityStatus.UNKNOWN,
            profile=profile,
            rule_source=RuleSource.EXTENSION,
            rule_path=("profile",),
            reason_code="profile.unsupported",
            detail=f"unsupported semantic profile: {profile!r}",
            evidence=("profile.unsupported",),
        )

    return evaluate_native(source, destination, profile=profile)


def _evaluate_with_config(
    source: Any,
    destination: Any,
    profile: str,
    config: AssignabilityConfigDict | None,
) -> AssignabilityResult:
    """Evaluate with the temporary compatibility config used by old callers."""

    if profile != NATIVE_PROFILE:
        return AssignabilityResult(
            AssignabilityStatus.UNKNOWN,
            profile=profile,
            rule_source=RuleSource.EXTENSION,
            rule_path=("profile",),
            reason_code="profile.unsupported",
            detail=f"unsupported semantic profile: {profile!r}",
            evidence=("profile.unsupported",),
        )
    evaluation_profile = profile
    if config and config.get("allow_bool_to_int"):
        evaluation_profile = f"{profile}+compat.allow_bool_to_int"
    return evaluate_native(
        source,
        destination,
        profile=evaluation_profile,
        config=config,
    )


@overload
def is_assignable(
    source: Any,
    destination: Any,
    config: AssignabilityConfigDict | None = None,
    *,
    profile: str = NATIVE_PROFILE,
    on_unknown: Literal["return_none"],
) -> bool | None: ...


@overload
def is_assignable(
    source: Any,
    destination: Any,
    config: AssignabilityConfigDict | None = None,
    *,
    profile: str = NATIVE_PROFILE,
    on_unknown: Literal["raise", "return_true", "return_false"] = "raise",
) -> bool: ...


def is_assignable(
    source: Any,
    destination: Any,
    config: AssignabilityConfigDict | None = None,
    *,
    profile: str = NATIVE_PROFILE,
    on_unknown: UnknownPolicy = "raise",
) -> bool | None:
    """Return the Boolean projection of :func:`evaluate_assignability`.

    ``on_unknown`` controls the explicit fallback for an indeterminate result.
    The default, ``"raise"``, preserves the distinction between unknown and
    definitely not assignable.

    ``config`` is retained as a temporary compatibility argument for the old
    release and is not part of the native semantic profile contract.
    """

    if on_unknown not in _UNKNOWN_POLICIES:
        raise ValueError(
            "on_unknown must be one of: " + ", ".join(sorted(_UNKNOWN_POLICIES))
        )

    result = _evaluate_with_config(source, destination, profile, config)
    if result.status is AssignabilityStatus.ASSIGNABLE:
        return True
    if result.status is AssignabilityStatus.NOT_ASSIGNABLE:
        return False

    if on_unknown == "raise":
        raise AssignabilityCapabilityError(result)
    if on_unknown == "return_none":
        return None
    return on_unknown == "return_true"
