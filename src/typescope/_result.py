"""Public result and profile types for assignability evaluation."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Literal

__all__ = [
    "AssignabilityCapabilityError",
    "AssignabilityResult",
    "AssignabilityStatus",
    "NATIVE_PROFILE",
    "RuleSource",
    "UnknownPolicy",
]


NATIVE_PROFILE: Final = "typescope-native/1"
UnknownPolicy = Literal["return_none", "return_true", "return_false", "raise"]


class AssignabilityStatus(StrEnum):
    """The three possible outcomes of a structured evaluation."""

    ASSIGNABLE = "assignable"
    NOT_ASSIGNABLE = "not_assignable"
    UNKNOWN = "unknown"


class RuleSource(StrEnum):
    """The provenance of the rule that produced an evaluation result."""

    STANDARD = "standard"
    CHECKER = "checker"
    EXTENSION = "extension"


@dataclass(frozen=True, slots=True)
class AssignabilityResult:
    """Structured outcome for one type-expression comparison."""

    status: AssignabilityStatus
    profile: str = NATIVE_PROFILE
    rule_source: RuleSource | None = None
    rule_path: tuple[str, ...] = ()
    reason_code: str | None = None
    detail: str | None = None
    provenance: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()

    @property
    def is_definite(self) -> bool:
        """Whether the evaluation reached a yes/no conclusion."""

        return self.status is not AssignabilityStatus.UNKNOWN


class AssignabilityCapabilityError(TypeError):
    """Raised when the Boolean API cannot decide assignability."""

    def __init__(self, result: AssignabilityResult) -> None:
        if result.status is not AssignabilityStatus.UNKNOWN:
            raise ValueError("capability errors require an unknown result")
        self.result = result
        message = result.detail or result.reason_code or "assignability is unknown"
        super().__init__(message)
