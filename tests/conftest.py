"""Shared test fixtures."""

from __future__ import annotations

import pytest

from automath.lean.error_parser import VerificationResult, LeanError, ErrorType, Position
from automath.llm.base import LLMClient, LLMResponse, TokenUsage


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    provider_name = "mock"

    def __init__(self, responses: list[str] | None = None):
        self._responses = responses or ["mock response"]
        self._call_count = 0

    async def generate(self, prompt: str, system: str = "", n: int = 1,
                       temperature: float = 0.7, max_tokens: int = 4096) -> list[LLMResponse]:
        results = []
        for _ in range(n):
            idx = self._call_count % len(self._responses)
            results.append(LLMResponse(
                content=self._responses[idx],
                model="mock-model",
                usage=TokenUsage(prompt_tokens=100, completion_tokens=200),
            ))
            self._call_count += 1
        return results


class MockLeanVerifier:
    """Mock Lean verifier for testing."""

    def __init__(self, results: list[VerificationResult] | None = None):
        self._results = results or [VerificationResult(success=True)]
        self._call_count = 0

    async def verify(self, lean_code: str, timeout: float | None = None) -> VerificationResult:
        idx = self._call_count % len(self._results)
        self._call_count += 1
        result = self._results[idx]
        result.lean_code = lean_code
        return result

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass


@pytest.fixture
def mock_llm():
    return MockLLMClient()


@pytest.fixture
def mock_verifier():
    return MockLeanVerifier()


@pytest.fixture
def success_result():
    return VerificationResult(success=True, lean_code="theorem t : 1+1=2 := by norm_num")


@pytest.fixture
def failure_result():
    return VerificationResult(
        success=False,
        errors=[
            LeanError(
                severity="error",
                message="type mismatch\n  rfl\nhas type\n  ?a = ?a\nbut is expected to have type\n  1 + 1 = 3",
                error_type=ErrorType.TYPE_MISMATCH,
                position=Position(line=3, column=10),
            )
        ],
        lean_code="theorem t : 1+1=3 := by rfl",
    )
