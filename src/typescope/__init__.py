"""typescope - Runtime type-level assignability check"""

__version__ = "0.0.2"

from ._assignability_api import evaluate_assignability, is_assignable
from ._assignability_config import AssignabilityConfigDict
from ._result import (
    NATIVE_PROFILE,
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
]
