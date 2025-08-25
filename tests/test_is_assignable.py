from typescope import is_assignable as ia


def test_basic_builtin_types() -> None:
    """Tests for basic builtin types like int, str, etc."""
    assert ia(int, int)
    assert not ia(int, str)

    assert ia(str, str)
    assert not ia(str, int)

    assert ia(float, float)
    assert not ia(float, int)

    assert ia(bool, bool)
    assert not ia(bool, int), "`bool` should not be assignable to `int` by default."
    assert ia(bool, int, {"allow_bool_to_int": True})
