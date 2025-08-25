from types import NoneType

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
    assert not ia(None, NoneType, {"none_as_nonetype": False})
    assert not ia(NoneType, None, {"none_as_nonetype": False})
