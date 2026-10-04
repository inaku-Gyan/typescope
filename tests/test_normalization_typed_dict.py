"""TypedDict normalization and KeyShape evidence tests."""

import typing
from typing import ForwardRef, NotRequired, TypedDict

from typescope._normalization import (
    KeyShape,
    NormalizedKind,
    ShapeCompleteness,
    ShapeOpenness,
    normalize_type_expression,
)

_ReadOnly = getattr(typing, "ReadOnly", None)


class _ReadOnlyFallback:
    """Make the fixture parse on runtimes before the ReadOnly backport."""

    @classmethod
    def __class_getitem__(cls, item: object) -> object:
        return item


ReadOnly = _ReadOnly or _ReadOnlyFallback


class Profile(TypedDict):
    name: str
    alias: NotRequired[str]
    identifier: ReadOnly[int]


class EquivalentProfile(TypedDict):
    identifier: ReadOnly[int]
    alias: NotRequired[str]
    name: str


class UnresolvedProfile(TypedDict):
    value: ForwardRef("MissingType")


def test_typed_dict_normalizes_to_complete_immutable_key_shape() -> None:
    normalized = normalize_type_expression(Profile)

    assert normalized.kind is NormalizedKind.TYPED_DICT
    assert isinstance(normalized.value, KeyShape)
    shape = normalized.value
    assert shape.completeness is ShapeCompleteness.COMPLETE
    assert shape.openness is ShapeOpenness.OPEN
    assert tuple(name for name, _ in shape.keys) == ("alias", "identifier", "name")

    keys = dict(shape.keys)
    assert keys["name"].required
    assert not keys["alias"].required
    assert keys["identifier"].read_only is (_ReadOnly is not None)
    assert not keys["name"].read_only


def test_equivalent_typed_dict_shapes_share_semantic_identity() -> None:
    first = normalize_type_expression(Profile)
    second = normalize_type_expression(EquivalentProfile)

    assert first.kind is second.kind is NormalizedKind.TYPED_DICT
    assert first.value == second.value


def test_unresolved_typed_dict_annotation_is_incomplete_evidence() -> None:
    normalized = normalize_type_expression(UnresolvedProfile)

    assert isinstance(normalized.value, KeyShape)
    assert normalized.value.completeness is ShapeCompleteness.UNKNOWN
    assert (
        dict(normalized.value.keys)["value"].value_type.kind is NormalizedKind.SPECIAL
    )
