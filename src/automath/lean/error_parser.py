"""Parse and classify Lean4 REPL error messages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ErrorType(Enum):
    TYPE_MISMATCH = "type_mismatch"
    UNKNOWN_IDENTIFIER = "unknown_identifier"
    TACTIC_FAILED = "tactic_failed"
    TIMEOUT = "timeout"
    SYNTAX_ERROR = "syntax_error"
    SORRY_REMAINING = "sorry_remaining"
    IMPORT_ERROR = "import_error"
    OTHER = "other"


@dataclass
class Position:
    line: int
    column: int


@dataclass
class LeanError:
    severity: str
    message: str
    error_type: ErrorType
    position: Position | None = None
    end_position: Position | None = None

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


@dataclass
class VerificationResult:
    success: bool
    errors: list[LeanError] = field(default_factory=list)
    warnings: list[LeanError] = field(default_factory=list)
    has_sorry: bool = False
    raw_messages: list[dict] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    lean_code: str = ""


# Patterns for classifying errors
_ERROR_PATTERNS: list[tuple[re.Pattern, ErrorType]] = [
    (re.compile(r"type mismatch", re.IGNORECASE), ErrorType.TYPE_MISMATCH),
    (re.compile(r"unknown identifier", re.IGNORECASE), ErrorType.UNKNOWN_IDENTIFIER),
    (re.compile(r"unknown constant", re.IGNORECASE), ErrorType.UNKNOWN_IDENTIFIER),
    (re.compile(r"tactic .+ failed", re.IGNORECASE), ErrorType.TACTIC_FAILED),
    (re.compile(r"unsolved goals", re.IGNORECASE), ErrorType.TACTIC_FAILED),
    (re.compile(r"expected token", re.IGNORECASE), ErrorType.SYNTAX_ERROR),
    (re.compile(r"unexpected token", re.IGNORECASE), ErrorType.SYNTAX_ERROR),
    (re.compile(r"(deterministic )?timeout", re.IGNORECASE), ErrorType.TIMEOUT),
    (re.compile(r"import .+ not found", re.IGNORECASE), ErrorType.IMPORT_ERROR),
    (re.compile(r"unknown package", re.IGNORECASE), ErrorType.IMPORT_ERROR),
]


def classify_error(message: str) -> ErrorType:
    """Classify a Lean error message into an ErrorType."""
    for pattern, error_type in _ERROR_PATTERNS:
        if pattern.search(message):
            return error_type
    return ErrorType.OTHER


def parse_position(pos_dict: dict | None) -> Position | None:
    if pos_dict is None:
        return None
    return Position(line=pos_dict.get("line", 0), column=pos_dict.get("column", 0))


def parse_repl_response(response: dict, lean_code: str = "", elapsed: float = 0.0) -> VerificationResult:
    """Parse a Lean REPL JSON response into a VerificationResult."""
    messages = response.get("messages", [])
    sorries = response.get("sorries", [])

    errors: list[LeanError] = []
    warnings: list[LeanError] = []

    for msg in messages:
        severity = msg.get("severity", "error")
        data = msg.get("data", "")
        error_type = classify_error(data) if severity == "error" else ErrorType.OTHER

        lean_error = LeanError(
            severity=severity,
            message=data,
            error_type=error_type,
            position=parse_position(msg.get("pos")),
            end_position=parse_position(msg.get("endPos")),
        )

        if severity == "error":
            errors.append(lean_error)
        elif severity == "warning":
            warnings.append(lean_error)

    has_sorry = len(sorries) > 0
    success = len(errors) == 0 and not has_sorry

    return VerificationResult(
        success=success,
        errors=errors,
        warnings=warnings,
        has_sorry=has_sorry,
        raw_messages=messages,
        elapsed_seconds=elapsed,
        lean_code=lean_code,
    )
