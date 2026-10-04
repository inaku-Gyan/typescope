"""Native structural assignability cases for Protocol member shapes."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from typescope import AssignabilityStatus, evaluate_assignability


class Named(Protocol):
    name: str

    @property
    def identifier(self) -> int: ...

    def render(self, width: int) -> str: ...


class NamedEquivalent(Protocol):
    name: str

    @property
    def identifier(self) -> int: ...

    def render(self, width: int) -> str: ...


class ChildNamed(Named, Protocol):
    age: int


class WrongName(Protocol):
    name: int

    @property
    def identifier(self) -> int: ...

    def render(self, width: int) -> str: ...


class ReadOnlyName(Protocol):
    @property
    def name(self) -> str: ...


class WritableName(Protocol):
    name: str


class CompleteSource:
    name: str

    @property
    def identifier(self) -> int:
        return 1

    def render(self, width: int) -> str:
        return str(width)


class MissingSource:
    name: str


class UnresolvedSource:
    value: "MissingSourceType"  # noqa: F821


if TYPE_CHECKING:
    MissingSourceType: object


class DynamicSource:
    value: int

    def __getattr__(self, name: str) -> object:
        return None


class UnsafeDescriptor:
    def __get__(self, instance: object, owner: type[object]) -> int:
        return 1


class UnsafeSource:
    value: int = UnsafeDescriptor()


@dataclass
class DataRecord:
    name: str
    identifier: int
    width: int

    def render(self, width: int) -> str:
        return str(width)


@dataclass
class OtherDataRecord:
    name: str
    identifier: int
    width: int


class RecursiveLeft(Protocol):
    next: "RecursiveLeft"


class RecursiveRight(Protocol):
    next: "RecursiveRight"


class NestedLeft(Protocol):
    value: int


class NestedRight(Protocol):
    value: int


class ParentLeft(Protocol):
    child: NestedLeft


class ParentRight(Protocol):
    child: NestedRight


class OptionalArgument(Protocol):
    def render(self, width: int, precision: int = 1) -> str: ...


class RequiredArgument(Protocol):
    def render(self, width: int, precision: int) -> str: ...


class UnresolvedProtocol(Protocol):
    value: "MissingProtocolValue"  # noqa: F821


if TYPE_CHECKING:
    MissingProtocolValue: object


def _status(source: object, destination: object) -> AssignabilityStatus:
    return evaluate_assignability(source, destination).status


def test_protocol_inheritance_and_equivalent_shapes_are_structural() -> None:
    assert _status(ChildNamed, Named) is AssignabilityStatus.ASSIGNABLE
    assert _status(Named, ChildNamed) is AssignabilityStatus.NOT_ASSIGNABLE
    assert _status(Named, NamedEquivalent) is AssignabilityStatus.ASSIGNABLE


def test_protocol_member_value_mismatch_is_not_assignable() -> None:
    assert _status(Named, WrongName) is AssignabilityStatus.NOT_ASSIGNABLE


def test_protocol_properties_obey_readonly_and_mutability() -> None:
    assert _status(WritableName, ReadOnlyName) is AssignabilityStatus.ASSIGNABLE
    assert _status(ReadOnlyName, WritableName) is AssignabilityStatus.NOT_ASSIGNABLE


def test_complete_concrete_class_can_satisfy_protocol() -> None:
    assert _status(CompleteSource, Named) is AssignabilityStatus.ASSIGNABLE


def test_known_missing_concrete_member_is_not_assignable() -> None:
    assert _status(MissingSource, Named) is AssignabilityStatus.NOT_ASSIGNABLE


def test_unresolved_or_dynamic_concrete_evidence_is_unknown() -> None:
    protocol = type("ValueProtocol", (Protocol,), {"__annotations__": {"value": int}})
    assert _status(UnresolvedSource, protocol) is AssignabilityStatus.UNKNOWN
    assert _status(DynamicSource, protocol) is AssignabilityStatus.UNKNOWN
    assert _status(UnsafeSource, protocol) is AssignabilityStatus.UNKNOWN


def test_dataclass_fields_are_controlled_protocol_source_evidence() -> None:
    assert _status(DataRecord, Named) is AssignabilityStatus.ASSIGNABLE


def test_dataclasses_remain_nominal_to_each_other() -> None:
    assert _status(DataRecord, OtherDataRecord) is AssignabilityStatus.NOT_ASSIGNABLE


def test_recursive_protocols_use_the_bounded_structural_relation() -> None:
    assert _status(RecursiveLeft, RecursiveRight) is AssignabilityStatus.ASSIGNABLE


def test_protocol_method_requiredness_is_checked() -> None:
    assert (
        _status(RequiredArgument, OptionalArgument)
        is AssignabilityStatus.NOT_ASSIGNABLE
    )


def test_nested_protocol_members_are_compared_structurally() -> None:
    assert _status(ParentLeft, ParentRight) is AssignabilityStatus.ASSIGNABLE


def test_incomplete_protocol_identity_remains_unknown() -> None:
    assert (
        _status(UnresolvedProtocol, UnresolvedProtocol) is AssignabilityStatus.UNKNOWN
    )
