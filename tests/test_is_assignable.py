# ruff: noqa: UP007, UP045

from types import NoneType
from typing import Optional, Union

from typescope import is_assignable as ia


def test_basic_builtin_types() -> None:
    """Tests for basic builtin types like int, str, etc."""
    assert ia(int, int)
    assert not ia(int, str)

    assert ia(str, str)
    assert not ia(str, int)

    assert ia(float, float)
    assert not ia(float, int)
    assert not ia(int, float)

    assert ia(bool, bool)
    assert not ia(int, bool)
    assert not ia(bool, int), "`bool` should not be assignable to `int` by default."
    assert ia(bool, int, {"allow_bool_to_int": True})

    assert ia(bytes, bytes)
    assert not ia(bytes, str)
    assert not ia(bytes, int)

    assert ia(type(None), NoneType)
    assert ia(NoneType, type(None))

    assert ia(None, NoneType)
    assert ia(NoneType, None)


def test_basic_builtin_types_with_union() -> None:
    """Tests for basic builtin types with Union."""

    #### With typing.Union ####
    assert ia(int, Union[int, str])
    assert not ia(int, Union[str, float])

    assert ia(str, Union[int, str])
    assert not ia(str, Union[int, float])

    assert ia(float, Union[int, float])
    assert not ia(float, Union[int, str])
    assert not ia(int, Union[float, str])

    assert ia(bool, Union[bool, int])
    assert not ia(int, Union[bool, str])
    assert not ia(bool, Union[int, str])
    assert ia(bool, Union[int, str], {"allow_bool_to_int": True})

    assert ia(bytes, Union[bytes, str])
    assert not ia(bytes, Union[str, int])
    assert not ia(bytes, Union[int, float])

    assert ia(type(None), Union[None, int])
    assert ia(NoneType, Union[NoneType, int])

    assert ia(None, Union[NoneType, int])
    assert ia(NoneType, Union[None, int])

    #### With PEP 604 Union ####
    assert ia(int, int | str)
    assert not ia(int, str | float)
    assert ia(str, int | str)
    assert not ia(str, int | float)
    assert ia(float, int | float)
    assert not ia(float, int | str)
    assert not ia(int, float | str)
    assert ia(bool, bool | int)
    assert not ia(int, bool | str)
    assert not ia(bool, int | str)
    assert ia(bool, int | str, {"allow_bool_to_int": True})
    assert ia(bytes, bytes | str)
    assert not ia(bytes, str | int)
    assert not ia(bytes, int | float)
    assert ia(type(None), None | int)
    assert ia(NoneType, NoneType | int)
    assert ia(None, NoneType | int)
    assert ia(NoneType, None | int)

    #### With typing.Optional ####
    assert ia(int, Optional[int])
    assert not ia(int, Optional[str])
    assert ia(None, Optional[str])
    assert ia(NoneType, Optional[str])


# def test_basic_builtin_generic_types() -> None:
#     """Tests for basic builtin generic types like list, dict, etc."""
#     assert ia(list, list)
#     assert not ia(list, dict)

#     assert ia(list[int], list[int])
#     assert not ia(list[int], list[str])
