from typing import Any, Literal

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


def test_unknown_policy_defaults_to_an_exception() -> None:
    with pytest.raises(AssignabilityCapabilityError) as raised:
        is_assignable(list[int], list[str])

    assert raised.value.result.status is AssignabilityStatus.UNKNOWN
    assert raised.value.result.reason_code == "expression_unsupported"


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
    assert result.reason_code == "profile_unsupported"


def test_any_remains_assignable_in_the_native_profile() -> None:
    assert is_assignable(Any, int)
    assert is_assignable(int, Any)
