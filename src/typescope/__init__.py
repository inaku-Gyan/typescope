"""typescope - Runtime type-level assignability check"""

__version__ = "0.0.2"

from ._assignability import is_assignable
from ._assignability_config import AssignabilityConfigDict

__all__ = [
    "is_assignable",
    "AssignabilityConfigDict",
]
