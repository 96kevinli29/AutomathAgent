"""Tests for Lean error parser."""

import json
from pathlib import Path

from automath.lean.error_parser import (
    ErrorType,
    classify_error,
    parse_repl_response,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_classify_type_mismatch():
    assert classify_error("type mismatch\n  rfl") == ErrorType.TYPE_MISMATCH


def test_classify_unknown_identifier():
    assert classify_error("unknown identifier 'foo'") == ErrorType.UNKNOWN_IDENTIFIER


def test_classify_unknown_constant():
    assert classify_error("unknown constant 'Nat.foo'") == ErrorType.UNKNOWN_IDENTIFIER


def test_classify_tactic_failed():
    assert classify_error("tactic 'simp' failed") == ErrorType.TACTIC_FAILED


def test_classify_unsolved_goals():
    assert classify_error("unsolved goals\n...") == ErrorType.TACTIC_FAILED


def test_classify_syntax_error():
    assert classify_error("expected token ')'") == ErrorType.SYNTAX_ERROR


def test_classify_timeout():
    assert classify_error("deterministic timeout") == ErrorType.TIMEOUT


def test_classify_other():
    assert classify_error("some random error") == ErrorType.OTHER


def test_parse_success_response():
    data = json.loads((FIXTURES / "repl_response_success.json").read_text())
    result = parse_repl_response(data, lean_code="test", elapsed=1.0)
    assert result.success is True
    assert result.errors == []
    assert result.has_sorry is False
    assert result.elapsed_seconds == 1.0


def test_parse_type_mismatch_response():
    data = json.loads((FIXTURES / "repl_response_type_mismatch.json").read_text())
    result = parse_repl_response(data, lean_code="test")
    assert result.success is False
    assert len(result.errors) == 1
    assert result.errors[0].error_type == ErrorType.TYPE_MISMATCH
    assert result.errors[0].position.line == 3
    assert result.errors[0].position.column == 10


def test_parse_sorry_response():
    data = {"env": 0, "messages": [], "sorries": [{"pos": {"line": 5, "column": 2}}]}
    result = parse_repl_response(data)
    assert result.success is False
    assert result.has_sorry is True
    assert result.errors == []
