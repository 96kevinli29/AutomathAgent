"""Tests for the auto-repair feedback loop."""

import pytest

from automath.lean.error_parser import ErrorType, LeanError, Position, VerificationResult
from automath.repair.feedback_loop import FeedbackLoop
from tests.conftest import MockLLMClient, MockLeanVerifier


@pytest.mark.asyncio
async def test_feedback_loop_immediate_success():
    """Proof passes on first try, no repair needed."""
    verifier = MockLeanVerifier([VerificationResult(success=True)])
    llm = MockLLMClient()
    loop = FeedbackLoop(llm, verifier, max_iterations=3)

    result = await loop.run("prove 1+1=2", "theorem t : 1+1=2 := by norm_num")

    assert result.success is True
    assert result.total_attempts == 1
    assert result.repair_rounds == 0
    assert result.final_proof is not None


@pytest.mark.asyncio
async def test_feedback_loop_repair_after_one_failure():
    """Proof fails once, then passes after repair."""
    fail_result = VerificationResult(
        success=False,
        errors=[LeanError("error", "type mismatch", ErrorType.TYPE_MISMATCH)],
    )
    success_result = VerificationResult(success=True)

    verifier = MockLeanVerifier([fail_result, success_result])
    llm = MockLLMClient(["```lean\ntheorem t : 1+1=2 := by norm_num\n```"])
    loop = FeedbackLoop(llm, verifier, max_iterations=3)

    result = await loop.run("prove 1+1=2", "theorem t : 1+1=3 := by rfl")

    assert result.success is True
    assert result.total_attempts == 2
    assert result.repair_rounds == 1


@pytest.mark.asyncio
async def test_feedback_loop_max_iterations_exceeded():
    """All repair attempts fail."""
    fail_result = VerificationResult(
        success=False,
        errors=[LeanError("error", "tactic 'simp' failed", ErrorType.TACTIC_FAILED)],
    )

    verifier = MockLeanVerifier([fail_result, fail_result, fail_result, fail_result])
    llm = MockLLMClient(["```lean\nbad proof\n```"])
    loop = FeedbackLoop(llm, verifier, max_iterations=3)

    result = await loop.run("prove something", "bad proof")

    assert result.success is False
    assert result.final_proof is None
    assert result.total_attempts == 4  # 1 initial + 3 repairs
