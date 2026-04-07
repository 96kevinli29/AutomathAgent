"""Tests for the data pool."""

import pytest
from pathlib import Path

from automath.data.pool import DataPool
from automath.data.schema import DataPoolEntry, VerificationStatus


@pytest.fixture
def tmp_pool(tmp_path):
    return DataPool(tmp_path / "test_pool")


@pytest.fixture
def sample_entry():
    return DataPoolEntry(
        problem="Prove 1+1=2",
        problem_source="miniF2F",
        problem_id="test_001",
        difficulty="easy",
        lean_proof_first="theorem t : 1+1=2 := by norm_num",
        first_verification=VerificationStatus(success=True),
        nl_explanation="By norm_num, 1+1 evaluates to 2.",
        model_source="claude",
        total_candidates=16,
    )


def test_add_and_get(tmp_pool, sample_entry):
    tmp_pool.add(sample_entry)
    retrieved = tmp_pool.get(sample_entry.id)
    assert retrieved is not None
    assert retrieved.problem == "Prove 1+1=2"
    assert retrieved.problem_source == "miniF2F"


def test_pool_size(tmp_pool, sample_entry):
    assert tmp_pool.size == 0
    tmp_pool.add(sample_entry)
    assert tmp_pool.size == 1


def test_query_by_source(tmp_pool, sample_entry):
    tmp_pool.add(sample_entry)
    results = tmp_pool.query(source="miniF2F")
    assert len(results) == 1
    results = tmp_pool.query(source="ProofNet")
    assert len(results) == 0


def test_query_by_difficulty(tmp_pool, sample_entry):
    tmp_pool.add(sample_entry)
    results = tmp_pool.query(difficulty="easy")
    assert len(results) == 1
    results = tmp_pool.query(difficulty="hard")
    assert len(results) == 0


def test_stats(tmp_pool, sample_entry):
    tmp_pool.add(sample_entry)
    stats = tmp_pool.stats()
    assert stats.total_entries == 1
    assert stats.by_source["miniF2F"] == 1
    assert stats.by_model["claude"] == 1


def test_snapshot(tmp_pool, sample_entry):
    tmp_pool.add(sample_entry)
    snapshot_dir = tmp_pool.snapshot("v1")
    assert (snapshot_dir / "pool.jsonl").exists()
    assert (snapshot_dir / "metadata.json").exists()


def test_export_jsonl(tmp_pool, sample_entry, tmp_path):
    tmp_pool.add(sample_entry)
    export_path = tmp_path / "export.jsonl"
    count = tmp_pool.export_jsonl(export_path)
    assert count == 1
    assert export_path.exists()


def test_persistence(tmp_path, sample_entry):
    """Entries persist across pool instances."""
    pool1 = DataPool(tmp_path / "persist_pool")
    pool1.add(sample_entry)

    pool2 = DataPool(tmp_path / "persist_pool")
    assert pool2.size == 1
    assert pool2.get(sample_entry.id) is not None
