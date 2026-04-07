"""Classify Lean errors and generate targeted repair prompts."""

from __future__ import annotations

from automath.lean.error_parser import ErrorType, LeanError, VerificationResult
from automath.llm.prompts import PROOF_REPAIR, REPAIR_GUIDANCE


def format_error_messages(result: VerificationResult) -> str:
    """Format verification errors into a readable string for the repair prompt."""
    if not result.errors:
        if result.has_sorry:
            return "The proof contains unresolved `sorry` placeholders."
        return "Unknown verification failure."

    parts = []
    for i, err in enumerate(result.errors, 1):
        loc = ""
        if err.position:
            loc = f" (line {err.position.line}, col {err.position.column})"
        parts.append(f"Error {i}{loc}: {err.message}")
    return "\n".join(parts)


def get_primary_error_type(result: VerificationResult) -> ErrorType:
    """Get the most relevant error type from a verification result."""
    if result.has_sorry:
        return ErrorType.SORRY_REMAINING
    if not result.errors:
        return ErrorType.OTHER

    # Prioritize: syntax > import > type_mismatch > unknown_id > tactic > other
    priority = [
        ErrorType.SYNTAX_ERROR,
        ErrorType.IMPORT_ERROR,
        ErrorType.TYPE_MISMATCH,
        ErrorType.UNKNOWN_IDENTIFIER,
        ErrorType.TACTIC_FAILED,
        ErrorType.TIMEOUT,
    ]
    error_types = {e.error_type for e in result.errors}
    for et in priority:
        if et in error_types:
            return et
    return ErrorType.OTHER


def build_repair_prompt(
    problem: str,
    failed_proof: str,
    result: VerificationResult,
) -> str:
    """Build a targeted repair prompt based on the error classification."""
    error_type = get_primary_error_type(result)
    error_messages = format_error_messages(result)
    guidance = REPAIR_GUIDANCE.get(error_type.value, REPAIR_GUIDANCE["other"])

    return PROOF_REPAIR.format(
        problem=problem,
        failed_proof=failed_proof,
        error_messages=error_messages,
        error_type=error_type.value,
        error_guidance=guidance,
    )
