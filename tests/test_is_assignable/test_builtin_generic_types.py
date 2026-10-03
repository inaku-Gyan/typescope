# ruff: noqa: UP006, UP007, UP045

import typing
from collections.abc import Iterable, Mapping, MutableSequence, Sequence
from typing import Any, Literal, TypeVar

import pytest

from typescope import evaluate_assignability
from typescope import is_assignable as ia


def test_basic_builtin_generic_types() -> None:
    """Tests for basic builtin generic types like list, dict, etc."""
    assert not ia(list, list)
    assert not ia(list, dict)


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        (typing.List[int], list[int]),
        (list[int], typing.List[int]),
        (dict[str, int], typing.Dict[str, int]),
        (Sequence[int], Sequence[int]),
    ],
)
def test_equivalent_generic_carriers_share_semantics(
    source: object, destination: object
) -> None:
    assert ia(source, destination)


def test_invariant_builtin_generics_require_both_arguments_to_match() -> None:
    assert not ia(list[int], list[object])
    assert not ia(list[object], list[int])
    assert not ia(dict[str, int], dict[object, int])
    assert not ia(dict[str, object], dict[str, int])


def test_covariant_abstract_containers_accept_narrower_values() -> None:
    assert ia(Sequence[int], Sequence[object])
    assert ia(Iterable[int], Iterable[object])
    assert ia(Mapping[str, int], Mapping[object, object])
    assert not ia(Sequence[object], Sequence[int])


def test_contravariant_user_generic_reverses_argument_direction() -> None:
    consumer_type_contra = TypeVar("consumer_type_contra", contravariant=True)

    # A real Generic declaration exposes the same public TypeVar metadata while
    # avoiding a dependency on implementation-specific typing classes.
    from typing import Generic

    class GenericConsumer(Generic[consumer_type_contra]):
        pass

    assert ia(GenericConsumer[object], GenericConsumer[int])
    assert not ia(GenericConsumer[int], GenericConsumer[object])


def test_contravariant_destination_typevar_can_bind_argument_evidence() -> None:
    from typing import Generic

    destination_consumer_type_contra = TypeVar(
        "destination_consumer_type_contra", contravariant=True
    )

    class GenericConsumer(Generic[destination_consumer_type_contra]):
        pass

    assert ia(
        GenericConsumer[int], GenericConsumer[destination_consumer_type_contra]
    )


def test_contravariant_typevar_does_not_bind_implicit_unknown() -> None:
    from typing import Generic

    destination_unknown_consumer_type_contra = TypeVar(
        "destination_unknown_consumer_type_contra", contravariant=True
    )

    class GenericConsumer(Generic[destination_unknown_consumer_type_contra]):
        pass

    result = evaluate_assignability(
        GenericConsumer,
        GenericConsumer[destination_unknown_consumer_type_contra],
    )

    assert result.status == "not_assignable"
    assert result.reason_code == "assignability.unknown_type"


def test_covariant_user_generic_follows_typevar_metadata() -> None:
    from typing import Generic

    value_type_co = TypeVar("value_type_co", covariant=True)

    class Box(Generic[value_type_co]):
        pass

    assert ia(Box[int], Box[object])
    assert not ia(Box[object], Box[int])


def test_generic_inheritance_projects_arguments_to_abstract_destination() -> None:
    assert ia(list[int], Sequence[object])
    assert ia(dict[str, int], Mapping[object, object])
    assert ia(tuple[int, ...], Sequence[object])


def test_abstract_generic_inheritance_projects_arguments_between_abc_origins() -> None:
    assert ia(Sequence[int], Iterable[object])
    assert ia(MutableSequence[int], Sequence[object])
    assert ia(Mapping[str, int], Iterable[str])
    assert not ia(Mapping[str, int], Iterable[int])


def test_fixed_tuple_projects_its_element_union_to_sequence() -> None:
    assert ia(tuple[int, str], Sequence[object])
    assert not ia(tuple[int, str], Sequence[int])


def test_empty_tuple_is_a_fixed_shape_with_no_element_requirements() -> None:
    assert ia(tuple[()], Sequence[int])
    assert ia(tuple[()], tuple[int, ...])
    assert not ia(tuple[()], tuple[int])


def test_user_generic_inheritance_projects_typevar_bindings() -> None:
    from typing import Generic

    inherited_value_type = TypeVar("inherited_value_type")

    class Base(Generic[inherited_value_type]):
        pass

    class Child(Base[inherited_value_type], Generic[inherited_value_type]):
        pass

    assert ia(Child[int], Base[int])
    assert not ia(Child[int], Base[str])


def test_nested_generic_inheritance_substitutes_typevar_arguments() -> None:
    from typing import Generic

    nested_inherited_value_type = TypeVar("nested_inherited_value_type")

    class NestedBase(Generic[nested_inherited_value_type]):
        pass

    class NestedChild(
        NestedBase[list[nested_inherited_value_type]],
        Generic[nested_inherited_value_type],
    ):
        pass

    assert ia(NestedChild[int], NestedBase[list[int]])
    assert not ia(NestedChild[int], NestedBase[list[str]])


def test_unresolvable_generic_inheritance_is_structured_unknown() -> None:
    from typing import Generic

    value_type = TypeVar("value_type")

    class Base(Generic[value_type]):
        pass

    class Broken(Base[Literal[1]]):
        pass

    result = evaluate_assignability(Broken, Base[int])

    assert result.status == "unknown"
    assert result.reason_code == "normalization.expression_unsupported"


def test_missing_generic_inheritance_arguments_are_unknown() -> None:
    from typing import Generic

    value_type = TypeVar("value_type")

    class Base(Generic[value_type]):
        pass

    class Child(Base, Generic[value_type]):
        pass

    result = evaluate_assignability(Child[int], Base[int])

    assert result.status == "unknown"
    assert result.reason_code == "generic.inheritance_unknown"


def test_typevar_identity_bounds_and_constraints_are_preserved() -> None:
    bounded_type = TypeVar("bounded_type", bound=int)
    constrained_type = TypeVar("constrained_type", int, str)
    free_type = TypeVar("free_type")

    assert ia(bounded_type, bounded_type)
    assert ia(int, bounded_type)
    assert ia(bounded_type, int)
    assert not ia(bounded_type, str)
    assert ia(constrained_type, object)
    assert not ia(bool, constrained_type)
    assert ia(free_type, int, on_unknown="return_none") is None


def test_source_typevar_constraints_require_every_permitted_instantiation() -> None:
    source_constrained_type = TypeVar("source_constrained_type", int, str)

    result = evaluate_assignability(source_constrained_type, int)

    assert result.status == "unknown"
    assert result.reason_code == "typevar.binding_unknown"
    assert ia(source_constrained_type, object)


def test_repeated_constrained_destination_typevar_rejects_conflicting_bindings() -> None:
    from typing import Generic

    constrained_first_type = TypeVar("constrained_first_type")
    constrained_second_type = TypeVar("constrained_second_type")
    repeated_constrained_type = TypeVar("repeated_constrained_type", int, str)

    class Pair(Generic[constrained_first_type, constrained_second_type]):
        pass

    assert ia(Pair[int, int], Pair[repeated_constrained_type, repeated_constrained_type])
    assert not ia(
        Pair[int, str], Pair[repeated_constrained_type, repeated_constrained_type]
    )


def test_repeated_destination_typevar_uses_one_binding() -> None:
    from typing import Generic

    first_type = TypeVar("first_type")
    second_type = TypeVar("second_type")
    shared_type = TypeVar("shared_type")

    class Pair(Generic[first_type, second_type]):
        pass

    class SharedPair(Generic[shared_type]):
        pass

    assert ia(Pair[int, int], Pair[shared_type, shared_type])
    assert not ia(Pair[int, str], Pair[shared_type, shared_type])


def test_omitted_generic_arguments_are_distinct_from_explicit_any() -> None:
    result = evaluate_assignability(typing.List, typing.List[int])

    assert not ia(typing.List, typing.List[int])
    assert not ia(typing.List, typing.List)
    assert not ia(list, list[int])
    assert not ia(list[int], list)
    assert result.rule_source == "extension"
    assert result.reason_code == "assignability.unknown_type"
    assert ia(list[Any], list[int])
    assert ia(list[int], list[Any])
