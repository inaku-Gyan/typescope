"""Protocol MemberShape normalization tests."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from typescope._normalization import (
    MemberKind,
    MemberShape,
    NormalizedKind,
    ShapeCompleteness,
    normalize_type_expression,
)


class Named(Protocol):
    name: str

    @property
    def identifier(self) -> int: ...

    def render(self, width: int) -> str: ...


class EquivalentNamed(Protocol):
    name: str

    @property
    def identifier(self) -> int: ...

    def render(self, width: int) -> str: ...


class ChildNamed(Named, Protocol):
    age: int


class ConflictLeft(Protocol):
    value: int


class ConflictRight(Protocol):
    value: str


class Conflicting(ConflictLeft, ConflictRight, Protocol):
    pass


class Unresolved(Protocol):
    value: "MissingProtocolType"  # noqa: F821


if TYPE_CHECKING:
    MissingProtocolType: object


class Dynamic(Protocol):
    value: int

    def __getattr__(self, name: str) -> object: ...


@dataclass(frozen=True)
class FrozenRecord:
    value: int


def test_protocol_normalizes_inherited_members_to_immutable_member_shape() -> None:
    normalized = normalize_type_expression(ChildNamed)

    assert normalized.kind is NormalizedKind.PROTOCOL
    assert isinstance(normalized.value, MemberShape)
    shape = normalized.value
    assert shape.completeness is ShapeCompleteness.COMPLETE
    assert tuple(name for name, _ in shape.members) == (
        "age",
        "identifier",
        "name",
        "render",
    )
    members = dict(shape.members)
    assert members["identifier"].kind is MemberKind.PROPERTY
    assert members["identifier"].read_only
    assert members["render"].kind is MemberKind.METHOD
    assert shape.as_mapping()["name"].value_type is not None


def test_equivalent_protocol_shapes_share_semantic_identity() -> None:
    first = normalize_type_expression(Named)
    second = normalize_type_expression(EquivalentNamed)

    assert first.kind is second.kind is NormalizedKind.PROTOCOL
    assert first.value == second.value


def test_unresolved_and_dynamic_protocol_evidence_is_incomplete() -> None:
    unresolved = normalize_type_expression(Unresolved)
    dynamic = normalize_type_expression(Dynamic)

    assert unresolved.value.completeness is ShapeCompleteness.UNKNOWN
    assert dynamic.value.completeness is ShapeCompleteness.UNKNOWN


def test_conflicting_inherited_protocol_members_are_incomplete() -> None:
    normalized = normalize_type_expression(Conflicting)

    assert normalized.value.completeness is ShapeCompleteness.UNKNOWN


def test_dataclass_normalization_remains_nominal() -> None:
    normalized = normalize_type_expression(FrozenRecord)

    assert normalized.kind is NormalizedKind.CLASS
    assert normalized.member_shape is not None
    assert normalized.member_shape.completeness is ShapeCompleteness.COMPLETE
