"""Tests for data schemas."""

from automath.data.schema import DataPoolEntry, MathProblem, VerificationStatus


def test_math_problem_creation():
    p = MathProblem(
        id="test_1",
        source="miniF2F",
        nl_statement="Prove 1+1=2",
    )
    assert p.id == "test_1"
    assert p.difficulty == "unknown"
    assert p.formal_statement is None


def test_data_pool_entry_defaults():
    e = DataPoolEntry(
        problem="test",
        problem_source="miniF2F",
        problem_id="t1",
        lean_proof_first="proof",
        first_verification=VerificationStatus(success=True),
    )
    assert e.id  # auto-generated UUID
    assert e.version == 1
    assert e.created_at is not None
    assert e.second_verification is None


def test_verification_status_serialization():
    v = VerificationStatus(success=True, lean_version="4.16.0")
    data = v.model_dump()
    assert data["success"] is True

    v2 = VerificationStatus.model_validate(data)
    assert v2.success is True
    assert v2.lean_version == "4.16.0"


def test_data_pool_entry_roundtrip():
    e = DataPoolEntry(
        problem="Prove 1+1=2",
        problem_source="miniF2F",
        problem_id="t1",
        lean_proof_first="theorem t : 1+1=2 := by norm_num",
        first_verification=VerificationStatus(success=True),
        model_source="claude",
    )
    json_str = e.model_dump_json()
    e2 = DataPoolEntry.model_validate_json(json_str)
    assert e2.problem == e.problem
    assert e2.model_source == "claude"
