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

    #### Special case for `bool` and `int` ####
    assert ia(bool, bool)
    assert not ia(int, bool)
    assert not ia(bool, int), "`bool` should not be assignable to `int` by default."
    assert ia(bool, int, {"allow_bool_to_int": True})

    assert ia(bytes, bytes)
    assert not ia(bytes, str)
    assert not ia(bytes, int)

    #### `None` and `NoneType` ####
    assert ia(type(None), NoneType)
    assert ia(NoneType, type(None))

    assert ia(None, NoneType)
    assert ia(NoneType, None)

    #### `object` ####
    assert ia(object, object)

    assert ia(int, object)
    assert ia(str, object)
    assert ia(float, object)

    assert not ia(object, int)
    assert not ia(object, str)

    assert ia(NoneType, object)
    assert ia(None, object)


def test_basic_builtin_types_with_typing_union() -> None:
    """Tests for `typing.Union`"""

    #### Union type as destination ####
    assert ia(int, Union[int])
    assert ia(int, Union[int, int, int])

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

    #### Union type as source ####
    assert ia(Union[int], int)
    assert ia(Union[int, int, int], int)

    assert ia(Union[int, str], object)
    assert not ia(Union[int, str], int)

    assert not ia(Union[int, bool], int)
    assert not ia(Union[int, bool], bool)

    assert ia(Union[int, bool], int, {"allow_bool_to_int": True})
    assert not ia(Union[int, bool], bool)

    #### Union type as both ####
    assert ia(Union[int, str], Union[int, str])
    assert ia(Union[int, str], Union[str, int])
    assert ia(Union[int, str], Union[str, int, float])
    assert ia(Union[int, str, int], Union[str, int, float])

    assert not ia(Union[int, str, float], Union[str, int])

    assert not ia(Union[int, bool], Union[int])
    assert ia(Union[int, bool], Union[int], {"allow_bool_to_int": True})


def test_basic_builtin_types_with_pep604_union() -> None:
    """With PEP 604-style union types (e.g., `int | str`)"""

    #### Union type as destination ####
    assert ia(int, int | int | int)

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

    #### Union type as source ####
    assert ia(int | int | int, int)
    assert ia(int | str, object)
    assert not ia(int | str, int)
    assert not ia(int | bool, int)
    assert not ia(int | bool, bool)
    assert ia(int | bool, int, {"allow_bool_to_int": True})
    assert not ia(int | bool, bool)
    assert ia(bytes | str, object)
    assert not ia(bytes | str, bytes)
    assert not ia(bytes | str, int)
    assert not ia(bytes | str, float)

    #### Union type as both ####
    assert ia(int | str, int | str)
    assert ia(int | str, str | int)
    assert ia(int | str, str | int | float)
    assert ia(int | str | int, str | int | float)
    assert not ia(int | str | float, str | int)
    assert not ia(int | bool, int)
    assert ia(int | bool, int, {"allow_bool_to_int": True})


def test_none_uninon_and_optional() -> None:
    """Tests for union types with `None`, `NoneType`, and `typing.Optional`"""

    #### `None` and `NoneType` with `typing.Union` ###
    assert ia(type(None), Union[None, int])
    assert ia(NoneType, Union[NoneType, int])

    assert ia(None, Union[NoneType, int])
    assert ia(NoneType, Union[None, int])

    assert ia(NoneType, Union[None, NoneType])
    assert ia(None, Union[None, NoneType])

    ##
    assert ia(Union[None, NoneType], NoneType)
    assert ia(Union[None, NoneType], type(None))

    assert ia(Union[None], None)
    assert ia(Union[None], NoneType)

    #### `None` and `NoneType` with PEP 604-style union types ###
    assert ia(type(None), None | int)
    assert ia(NoneType, NoneType | int)
    assert ia(None, NoneType | int)
    assert ia(NoneType, None | int)

    assert ia(NoneType, None | NoneType)
    assert ia(None, None | NoneType)
    assert ia(None | NoneType, NoneType)
    assert ia(None | NoneType, type(None))
    assert ia(None | NoneType, None)

    #### `typing.Optional` ####
    assert ia(int, Optional[int])
    assert not ia(int, Optional[str])
    assert ia(None, Optional[str])
    assert ia(NoneType, Optional[str])

    assert not ia(Optional[int], int)
    assert not ia(Optional[str], None)
    assert ia(Optional[str], object)

    assert ia(Optional[int], Optional[int])
    assert not ia(Optional[int], Optional[str])

    assert ia(Optional[int], Union[int, None])
    assert ia(Optional[int], int | None)
    assert ia(Union[int, None], Optional[int])
    assert ia(int | None, Optional[int])

    assert ia(Optional[None], None)
    assert ia(Optional[NoneType], NoneType)
    assert ia(Optional[None], NoneType)
    assert ia(Optional[NoneType], None)
