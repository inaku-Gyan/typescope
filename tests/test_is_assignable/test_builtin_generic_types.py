# ruff: noqa: UP007, UP045

from typescope import is_assignable as ia


def test_basic_builtin_generic_types() -> None:
    """Tests for basic builtin generic types like list, dict, etc."""
    assert ia(list, list)
    assert not ia(list, dict)

    # assert ia(list[int], list[int])
    # assert not ia(list[int], list[str])
