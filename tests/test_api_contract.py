from typing import Any, Literal, Never, NoReturn

import pytest

from typescope import (
    NATIVE_PROFILE,
    AssignabilityCapabilityError,
    AssignabilityStatus,
    evaluate_assignability,
    is_assignable,
)


def test_structured_evaluation_preserves_a_definite_result() -> None:
    result = evaluate_assignability(int, object)

    assert result.status is AssignabilityStatus.ASSIGNABLE
    assert result.profile == NATIVE_PROFILE
    assert result.rule_source == "standard"
    assert result.rule_path
    assert result.provenance == ("builtins.type", "builtins.type")


def test_unknown_policy_defaults_to_an_exception() -> None:
    with pytest.raises(AssignabilityCapabilityError) as raised:
        is_assignable(list[int], list[str])

    assert raised.value.result.status is AssignabilityStatus.UNKNOWN
    assert raised.value.result.reason_code == "normalization.expression_unsupported"


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("return_none", None), ("return_true", True), ("return_false", False)],
)
def test_unknown_policy_can_be_selected(
    policy: Literal["return_none", "return_true", "return_false"],
    expected: bool | None,
) -> None:
    assert is_assignable(list[int], list[str], on_unknown=policy) is expected


def test_unknown_profile_is_not_a_definite_negative() -> None:
    result = evaluate_assignability(int, object, profile="checker/pyright")

    assert result.status is AssignabilityStatus.UNKNOWN
    assert result.reason_code == "profile.unsupported"
    assert result.rule_source == "extension"
    assert result.rule_path == ("profile",)
    assert result.evidence == ("profile.unsupported",)


def test_any_remains_assignable_in_the_native_profile() -> None:
    assert is_assignable(Any, int)
    assert is_assignable(int, Any)


def test_never_is_a_bottom_type() -> None:
    assert is_assignable(Never, int)
    assert is_assignable(NoReturn, str)
    assert not is_assignable(int, Never)
    assert is_assignable(Never, Never)


def test_native_numeric_promotions_are_explicit() -> None:
    assert is_assignable(int, float)
    assert is_assignable(int, complex)
    assert is_assignable(float, complex)
    assert not is_assignable(float, int)
    assert not is_assignable(complex, float)


def test_unsupported_runtime_expressions_are_capability_unknown() -> None:
    result = evaluate_assignability(object(), int)

    assert result.status is AssignabilityStatus.UNKNOWN
    assert result.reason_code == "normalization.expression_unsupported"
    assert result.rule_source == "extension"
    assert result.rule_path == ("normalization",)
    assert result.evidence == ("normalization.expression_unsupported",)


def test_unknown_preserves_provenance_for_the_resolved_operand() -> None:
    result = evaluate_assignability(int, object())

    assert result.status is AssignabilityStatus.UNKNOWN
    assert result.provenance == ("builtins.type",)


def test_legacy_boolean_compatibility_is_visible_in_profile_identity() -> None:
    with pytest.raises(AssignabilityCapabilityError) as raised:
        is_assignable(object(), int, {"allow_bool_to_int": True})

    assert raised.value.result.profile == f"{NATIVE_PROFILE}+compat.allow_bool_to_int"
    assert is_assignable(object(), int, on_unknown="return_none") is None
