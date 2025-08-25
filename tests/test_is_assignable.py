from typescope import is_assignable


def test_basic_builtin_types() -> None:
    """Tests for basic builtin types like int, str, etc."""
    assert is_assignable(int, int)
    assert not is_assignable(int, str)

    assert is_assignable(str, str)
    assert not is_assignable(str, int)

    assert is_assignable(float, float)
    assert not is_assignable(float, int)

    assert is_assignable(bool, bool)
    # assert not is_assignable(bool, int)  # bool is not a subtype of int in this context
