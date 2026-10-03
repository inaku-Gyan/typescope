"""typescope - Runtime type-level assignability check"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("typescope")
except PackageNotFoundError:
    __version__ = "0+unknown"

from ._assignability_api import evaluate_assignability, is_assignable
from ._assignability_config import AssignabilityConfigDict
from ._result import (
    NATIVE_PROFILE,
    UNKNOWN_AS_ANY_PROFILE,
    AssignabilityCapabilityError,
    AssignabilityResult,
    AssignabilityStatus,
    RuleSource,
)

__all__ = [
    "is_assignable",
    "evaluate_assignability",
    "AssignabilityConfigDict",
    "AssignabilityCapabilityError",
    "AssignabilityResult",
    "AssignabilityStatus",
    "NATIVE_PROFILE",
    "RuleSource",
    "UNKNOWN_AS_ANY_PROFILE",
]
