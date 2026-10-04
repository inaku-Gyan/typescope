"""Native structural assignability cases for ``TypedDict`` schemas."""

import typing
from typing import TypedDict

import pytest

from typescope import AssignabilityStatus, evaluate_assignability


class User(TypedDict):
    user_id: int
    display_name: str


class EquivalentUser(TypedDict):
    user_id: int
    display_name: str


class DifferentValue(TypedDict):
    user_id: str
    display_name: str


class UserWithExtraRequiredKey(TypedDict):
    user_id: int
    display_name: str
    email: str


class OptionalUser(TypedDict, total=False):
    user_id: int
    display_name: str


class RequiredUser(TypedDict):
    user_id: int


class OptionalUserId(TypedDict, total=False):
    user_id: int


def _status(source: object, destination: object) -> AssignabilityStatus:
    return evaluate_assignability(source, destination).status


def test_equivalent_typed_dict_schemas_are_assignable() -> None:
    assert _status(User, EquivalentUser) is AssignabilityStatus.ASSIGNABLE
    assert _status(EquivalentUser, User) is AssignabilityStatus.ASSIGNABLE


def test_typed_dict_value_mismatch_is_not_assignable() -> None:
    assert _status(User, DifferentValue) is AssignabilityStatus.NOT_ASSIGNABLE


def test_destination_required_key_must_be_present_in_source() -> None:
    assert _status(OptionalUserId, RequiredUser) is AssignabilityStatus.NOT_ASSIGNABLE


def test_destination_optional_keys_may_be_absent_from_source() -> None:
    assert _status(RequiredUser, OptionalUserId) is AssignabilityStatus.ASSIGNABLE


def test_source_extra_required_keys_are_safe() -> None:
    assert _status(UserWithExtraRequiredKey, User) is AssignabilityStatus.ASSIGNABLE


def test_ordinary_dict_is_not_a_typed_dict_schema() -> None:
    assert _status(dict[str, object], User) is AssignabilityStatus.NOT_ASSIGNABLE


if typing.TYPE_CHECKING:
    TypeNameThatDoesNotExist: object


UnresolvedValue = TypedDict(  # noqa: UP013
    "UnresolvedValue",
    {"value": "TypeNameThatDoesNotExist"},  # noqa: F821
)


def test_unresolved_typed_dict_value_is_capability_unknown() -> None:
    result = evaluate_assignability(UnresolvedValue, User)
    assert result.status is AssignabilityStatus.UNKNOWN


_ReadOnly = getattr(typing, "ReadOnly", None)


if _ReadOnly is not None:

    class ReadOnlyUser(TypedDict):
        user_id: _ReadOnly[int]

    class MutableUser(TypedDict):
        user_id: int


@pytest.mark.skipif(_ReadOnly is None, reason="ReadOnly is unavailable on this runtime")
def test_mutable_source_can_satisfy_read_only_destination() -> None:
    assert _status(MutableUser, ReadOnlyUser) is AssignabilityStatus.ASSIGNABLE


@pytest.mark.skipif(_ReadOnly is None, reason="ReadOnly is unavailable on this runtime")
def test_read_only_source_cannot_satisfy_mutable_destination() -> None:
    assert _status(ReadOnlyUser, MutableUser) is AssignabilityStatus.NOT_ASSIGNABLE
