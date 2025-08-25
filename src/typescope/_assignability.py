from typing import Any

from ._assignability_config import AssignabilityConfig as _Config
from ._assignability_config import AssignabilityConfigDict as _ConfigDict
from ._assignability_config import make_assignability_config as _make_config
from .typing import get_union_items, is_none_type, is_union

__all__ = ["is_assignable"]


def is_assignable(
    source_type: Any, dest_type: Any, config: _ConfigDict | None = None
) -> bool:
    """Determines if a value of `source_type` can be assigned to a variable of `dest_type`.

    Args:
        source_type (type[Any]): The type of the source value.
        dest_type (type[Any]): The type of the destination variable.
        config (_ConfigDict | None, optional): Optional configuration for assignability rules.

    Returns:
        bool: True if `source_type` is assignable to `dest_type`, False otherwise.
    """
    _config = _make_config(config)
    return _is_assignable_core(source_type, dest_type, _config)


def _special_judge_for_basic_types(
    src_tp: Any, dst_tp: Any, config: _Config
) -> bool | None:
    """Special judge for basic types like int, str, float, bool."""

    if src_tp is bool and dst_tp is int:
        return config.allow_bool_to_int

    if is_none_type(dst_tp):
        return is_none_type(src_tp)
    elif is_none_type(src_tp):
        return False


def _is_assignable_core(src_tp: Any, dst_tp: Any, config: _Config) -> bool:
    """Core logic for assignability check.

    Performs recursive checks and handles special cases.
    """
    if src_tp == dst_tp:
        return True

    ##### Handle Union types #####
    if is_union(src_tp):
        return all(
            _is_assignable_core(s, dst_tp, config) for s in get_union_items(src_tp)
        )
    if is_union(dst_tp):
        return any(
            _is_assignable_core(src_tp, d, config) for d in get_union_items(dst_tp)
        )

    ##### No any Union types here #####
    ret = _special_judge_for_basic_types(src_tp, dst_tp, config)
    if ret is not None:
        return ret

    ##### Fallback to issubclass check #####
    return issubclass(src_tp, dst_tp)
