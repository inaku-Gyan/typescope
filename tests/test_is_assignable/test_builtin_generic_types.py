# ruff: noqa: UP006, UP007, UP045

import typing
from collections.abc import Iterable, Mapping, MutableSequence, Reversible, Sequence
from typing import Any, Generic, Literal, Never, TypeVar

import pytest

from typescope import evaluate_assignability
from typescope import is_assignable as ia


def test_basic_builtin_generic_types() -> None:
    """Tests for basic builtin generic types like list, dict, etc."""
    assert not ia(list, list)
    assert not ia(list, dict)


@pytest.mark.parametrize(
    "expression",
    [list[int, str], dict[int], type[int, str], tuple[int, str, ...]],
)
def test_malformed_fixed_arity_generics_are_capability_unknown(
    expression: object,
) -> None:
    result = evaluate_assignability(expression, expression)

    assert result.status == "unknown"
    assert result.reason_code == "normalization.generic_arity"


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
    class GenericConsumer(Generic[consumer_type_contra]):
        pass

    assert ia(GenericConsumer[object], GenericConsumer[int])
    assert not ia(GenericConsumer[int], GenericConsumer[object])


def test_contravariant_destination_typevar_can_bind_argument_evidence() -> None:
    destination_consumer_type_contra = TypeVar(
        "destination_consumer_type_contra", contravariant=True
    )

    class GenericConsumer(Generic[destination_consumer_type_contra]):
        pass

    assert ia(GenericConsumer[int], GenericConsumer[destination_consumer_type_contra])


def test_contravariant_source_typevar_is_not_bound_from_destination_evidence() -> None:
    source_consumer_type_contra = TypeVar(
        "source_consumer_type_contra", contravariant=True
    )

    class GenericConsumer(Generic[source_consumer_type_contra]):
        pass

    result = evaluate_assignability(
        GenericConsumer[source_consumer_type_contra], GenericConsumer[int]
    )

    assert result.status == "unknown"
    assert result.reason_code == "typevar.binding_unknown"


def test_contravariant_source_typevar_handles_special_destinations() -> None:
    source_type_contra = TypeVar("source_type_contra", contravariant=True)

    class GenericConsumer(Generic[source_type_contra]):
        pass

    assert ia(GenericConsumer[source_type_contra], GenericConsumer[Any])
    assert ia(GenericConsumer[source_type_contra], GenericConsumer[Never])

    checker_result = evaluate_assignability(
        GenericConsumer[source_type_contra],
        GenericConsumer,
        profile="typescope-checker/unknown-as-any/1",
    )
    assert checker_result.status == "assignable"
    assert checker_result.rule_source == "checker"


def test_contravariant_source_typevar_checks_all_constraints() -> None:
    unknown_type_contra = TypeVar("unknown_type_contra", int, str, contravariant=True)

    class UnknownConsumer(Generic[unknown_type_contra]):
        pass

    unknown_result = evaluate_assignability(
        UnknownConsumer[unknown_type_contra], UnknownConsumer[object]
    )
    assert unknown_result.status == "unknown"
    assert unknown_result.reason_code == "typevar.binding_unknown"

    class Base:
        pass

    class Child(Base):
        pass

    all_assignable_type_contra = TypeVar(
        "all_assignable_type_contra", Base, Child, contravariant=True
    )

    class AllAssignableConsumer(Generic[all_assignable_type_contra]):
        pass

    assert ia(
        AllAssignableConsumer[all_assignable_type_contra],
        AllAssignableConsumer[Child],
    )


def test_explicit_any_can_bind_contravariant_destination_typevar() -> None:
    any_consumer_type_contra = TypeVar("any_consumer_type_contra", contravariant=True)

    class GenericConsumer(Generic[any_consumer_type_contra]):
        pass

    assert ia(GenericConsumer[Any], GenericConsumer[any_consumer_type_contra])


def test_contravariant_typevar_does_not_bind_implicit_unknown() -> None:
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

    checker_result = evaluate_assignability(
        GenericConsumer,
        GenericConsumer[destination_unknown_consumer_type_contra],
        profile="typescope-checker/unknown-as-any/1",
    )
    assert checker_result.status == "assignable"
    assert checker_result.rule_source == "checker"


def test_covariant_user_generic_follows_typevar_metadata() -> None:
    value_type_co = TypeVar("value_type_co", covariant=True)

    class Box(Generic[value_type_co]):
        pass

    assert ia(Box[int], Box[object])
    assert not ia(Box[object], Box[int])


def test_tuple_projection_handles_single_and_duplicate_element_shapes() -> None:
    assert ia(tuple[int], Sequence[int])
    assert ia(tuple[int, int], Sequence[int])


def test_generic_inheritance_projects_arguments_to_abstract_destination() -> None:
    assert ia(list[int], Sequence[object])
    assert ia(dict[str, int], Mapping[object, object])
    assert ia(tuple[int, ...], Sequence[object])


def test_abstract_generic_inheritance_projects_arguments_between_abc_origins() -> None:
    assert ia(Sequence[int], Iterable[object])
    assert ia(MutableSequence[int], Sequence[object])
    assert ia(Mapping[str, int], Iterable[str])
    assert not ia(Mapping[str, int], Iterable[int])
    assert ia(list[int], Reversible[int])
    assert ia(dict[str, int], Reversible[str])


def test_fixed_tuple_projects_its_element_union_to_sequence() -> None:
    assert ia(tuple[int, str], Sequence[object])
    assert not ia(tuple[int, str], Sequence[int])


def test_empty_tuple_is_a_fixed_shape_with_no_element_requirements() -> None:
    assert ia(tuple[()], Sequence[int])
    assert ia(tuple[()], tuple[int, ...])
    assert not ia(tuple[()], tuple[int])


def test_raw_typing_tuple_keeps_implicit_unknown_arguments() -> None:
    result = evaluate_assignability(typing.Tuple, typing.Tuple[int, ...])

    assert result.status == "not_assignable"
    assert result.reason_code == "assignability.unknown_type"
    assert ia(
        typing.Tuple,
        typing.Tuple[int, ...],
        profile="typescope-checker/unknown-as-any/1",
    )


def test_user_generic_inheritance_projects_typevar_bindings() -> None:
    inherited_value_type = TypeVar("inherited_value_type")

    class Base(Generic[inherited_value_type]):
        pass

    class Child(Base[inherited_value_type], Generic[inherited_value_type]):
        pass

    assert ia(Child[int], Base[int])
    assert not ia(Child[int], Base[str])


def test_nested_generic_inheritance_substitutes_typevar_arguments() -> None:
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


def test_custom_builtin_generic_subclasses_project_recoverable_base_arguments() -> None:
    custom_list_value_type = TypeVar("custom_list_value_type")

    class CustomList(list[custom_list_value_type], Generic[custom_list_value_type]):
        pass

    class CustomDict(dict[str, int]):
        pass

    assert ia(CustomList[int], Sequence[object])
    assert ia(CustomDict, Mapping[str, object])


def test_unresolvable_generic_inheritance_is_structured_unknown() -> None:
    value_type = TypeVar("value_type")

    class Base(Generic[value_type]):
        pass

    class Broken(Base[Literal[1]]):
        pass

    result = evaluate_assignability(Broken, Base[int])

    assert result.status == "unknown"
    assert result.reason_code == "normalization.expression_unsupported"


def test_missing_generic_inheritance_arguments_are_unknown() -> None:
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
    bounded_to_str = evaluate_assignability(bounded_type, str)
    assert bounded_to_str.status == "unknown"
    assert bounded_to_str.reason_code == "typevar.binding_unknown"
    assert ia(constrained_type, object)
    assert not ia(bool, constrained_type)
    assert ia(free_type, int, on_unknown="return_none") is None


def test_destination_constraints_choose_or_reject_explicit_bindings() -> None:
    class Base:
        pass

    class Child(Base):
        pass

    ambiguous_type = TypeVar("ambiguous_type", Base, object)
    exact_type = TypeVar("exact_type", int, object)
    any_type = TypeVar("any_type", int, str)

    ambiguous_result = evaluate_assignability(Child, ambiguous_type)
    exact_result = evaluate_assignability(int, exact_type)
    any_result = evaluate_assignability(Any, any_type)

    assert ambiguous_result.status == "unknown"
    assert ambiguous_result.reason_code == "typevar.binding_unknown"
    assert exact_result.status == "assignable"
    assert any_result.status == "assignable"


def test_source_typevar_constraints_require_every_permitted_instantiation() -> None:
    source_constrained_type = TypeVar("source_constrained_type", int, str)

    result = evaluate_assignability(source_constrained_type, int)

    assert result.status == "unknown"
    assert result.reason_code == "typevar.binding_unknown"
    assert ia(source_constrained_type, object)


def test_source_constraints_report_unknown_and_definite_mismatch() -> None:
    class ListLike(list):
        pass

    source_unknown_type = TypeVar("source_unknown_type", ListLike, int)
    source_mismatch_type = TypeVar("source_mismatch_type", int, str)

    unknown_result = evaluate_assignability(source_unknown_type, Sequence[int])
    mismatch_result = evaluate_assignability(source_mismatch_type, bool)

    assert unknown_result.status == "unknown"
    assert mismatch_result.status == "not_assignable"


@pytest.mark.parametrize(
    ("bound", "destination"),
    [(object, str), (int, bool)],
)
def test_source_bounded_typevar_requires_every_permitted_instantiation(
    bound: type[object], destination: type[object]
) -> None:
    source_bounded_type = TypeVar("source_bounded_type", bound=bound)

    result = evaluate_assignability(source_bounded_type, destination)

    assert result.status == "unknown"
    assert result.reason_code == "typevar.binding_unknown"


def test_repeated_constrained_destination_typevar_rejects_conflicting_bindings() -> (
    None
):
    constrained_first_type = TypeVar("constrained_first_type")
    constrained_second_type = TypeVar("constrained_second_type")
    repeated_constrained_type = TypeVar("repeated_constrained_type", int, str)

    class Pair(Generic[constrained_first_type, constrained_second_type]):
        pass

    assert ia(
        Pair[int, int], Pair[repeated_constrained_type, repeated_constrained_type]
    )
    assert not ia(
        Pair[int, str], Pair[repeated_constrained_type, repeated_constrained_type]
    )


def test_repeated_destination_typevar_uses_one_binding() -> None:
    first_type = TypeVar("first_type")
    second_type = TypeVar("second_type")
    shared_type = TypeVar("shared_type")

    class Pair(Generic[first_type, second_type]):
        pass

    class SharedPair(Generic[shared_type]):
        pass

    assert ia(Pair[int, int], Pair[shared_type, shared_type])
    assert not ia(Pair[int, str], Pair[shared_type, shared_type])


def test_contravariant_destination_typevar_handles_constraints_and_bounds() -> None:
    class Base:
        pass

    class Child(Base):
        pass

    constrained_type_contra = TypeVar(
        "constrained_type_contra", int, str, contravariant=True
    )

    class ConstrainedConsumer(Generic[constrained_type_contra]):
        pass

    assert ia(ConstrainedConsumer[int], ConstrainedConsumer[constrained_type_contra])

    ambiguous_type_contra = TypeVar(
        "ambiguous_type_contra", Base, Child, contravariant=True
    )

    class AmbiguousConsumer(Generic[ambiguous_type_contra]):
        pass

    ambiguous_result = evaluate_assignability(
        AmbiguousConsumer[object], AmbiguousConsumer[ambiguous_type_contra]
    )
    assert ambiguous_result.status == "unknown"
    assert ambiguous_result.reason_code == "typevar.binding_unknown"

    rejected_type_contra = TypeVar("rejected_type_contra", int, str, contravariant=True)

    class RejectedConsumer(Generic[rejected_type_contra]):
        pass

    rejected_result = evaluate_assignability(
        RejectedConsumer[bool], RejectedConsumer[rejected_type_contra]
    )
    assert rejected_result.status == "not_assignable"

    bounded_type_contra = TypeVar(
        "bounded_type_contra", bound=object, contravariant=True
    )

    class BoundedConsumer(Generic[bounded_type_contra]):
        pass

    assert ia(BoundedConsumer[int], BoundedConsumer[bounded_type_contra])

    narrow_bound_type_contra = TypeVar(
        "narrow_bound_type_contra", bound=int, contravariant=True
    )

    class NarrowBoundConsumer(Generic[narrow_bound_type_contra]):
        pass

    assert ia(
        NarrowBoundConsumer[object], NarrowBoundConsumer[narrow_bound_type_contra]
    )


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


def test_implicit_unknown_does_not_become_explicit_any() -> None:
    result = evaluate_assignability(list, list[Any])
    reverse = evaluate_assignability(list[Any], list)

    assert result.status == "not_assignable"
    assert result.reason_code == "assignability.unknown_type"
    assert result.rule_path == ("generic.argument[0]", "special.unknown")
    assert reverse.status == "not_assignable"
    assert reverse.reason_code == "assignability.unknown_type"
    assert ia(list, list[Any], profile="typescope-checker/unknown-as-any/1")
    assert ia(list[Any], list, profile="typescope-checker/unknown-as-any/1")


def test_implicit_unknown_stays_opaque_through_unions() -> None:
    result = evaluate_assignability(list | str, Any)
    reverse = evaluate_assignability(Any, list | str)

    assert result.status == "not_assignable"
    assert result.reason_code == "assignability.unknown_type"
    assert reverse.status == "not_assignable"
    assert reverse.reason_code == "assignability.unknown_type"


def test_checker_unknown_does_not_bypass_outer_generic_or_union_rules() -> None:
    profile = "typescope-checker/unknown-as-any/1"

    generic_result = evaluate_assignability(list, dict[int, int], profile=profile)
    union_result = evaluate_assignability(list | str, int, profile=profile)

    assert generic_result.status == "not_assignable"
    assert union_result.status == "not_assignable"
