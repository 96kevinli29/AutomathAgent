"""Tests for prompt templates and code extraction."""

from automath.llm.prompts import (
    PROOF_GENERATION,
    PROOF_REPAIR,
    extract_lean_code,
)


def test_proof_generation_template():
    result = PROOF_GENERATION.format(
        problem="Prove 1+1=2",
        formal_hint="",
    )
    assert "Prove 1+1=2" in result
    assert "import Mathlib" in result


def test_proof_repair_template():
    result = PROOF_REPAIR.format(
        problem="Prove 1+1=2",
        failed_proof="theorem t : 1+1=3 := by rfl",
        error_messages="type mismatch",
        error_type="type_mismatch",
        error_guidance="Fix the type",
    )
    assert "type mismatch" in result
    assert "1+1=3" in result


def test_extract_lean_code_from_markdown():
    response = """Here's the proof:
```lean
import Mathlib
theorem t : 1+1=2 := by norm_num
```
"""
    code = extract_lean_code(response)
    assert "import Mathlib" in code
    assert "norm_num" in code
    assert "```" not in code


def test_extract_lean_code_from_lean4_block():
    response = """```lean4
theorem t : 1+1=2 := by norm_num
```"""
    code = extract_lean_code(response)
    assert "norm_num" in code


def test_extract_lean_code_raw():
    response = "theorem t : 1+1=2 := by norm_num"
    code = extract_lean_code(response)
    assert code == response
