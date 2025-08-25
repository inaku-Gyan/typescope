from dataclasses import dataclass
from typing import TypedDict

__all__ = ["AssignabilityConfigDict", "make_assignability_config"]


class AssignabilityConfigDict(TypedDict, total=False):
    """Configuration options for assignability checks."""

    allow_bool_to_int: bool
    """Whether to allow `bool` to be assigned to `int`. Defaults to `False`."""


@dataclass(frozen=True)
class AssignabilityConfig:
    """Immutable configuration for assignability checks."""

    allow_bool_to_int: bool = False
    """Whether to allow `bool` to be assigned to `int`. Defaults to `False`."""


def make_assignability_config(
    overrides: AssignabilityConfigDict | None,
) -> AssignabilityConfig:
    """Create an `AssignabilityConfig` with optional overrides."""
    if overrides is None:
        return AssignabilityConfig()
    return AssignabilityConfig(**overrides)
