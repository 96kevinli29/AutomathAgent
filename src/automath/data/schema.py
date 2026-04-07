"""Pydantic data models for the data pool."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class VerificationStatus(BaseModel):
    success: bool
    errors: List[dict] = Field(default_factory=list)
    warnings: List[dict] = Field(default_factory=list)
    has_sorry: bool = False
    lean_version: str = ""
    elapsed_seconds: float = 0.0


class MathProblem(BaseModel):
    """A math problem from a benchmark dataset."""

    id: str
    source: str  # "miniF2F", "ProofNet", "LeanWorkbook"
    nl_statement: str
    formal_statement: Optional[str] = None
    formal_proof: Optional[str] = None
    difficulty: str = "unknown"
    tags: List[str] = Field(default_factory=list)


class DataPoolEntry(BaseModel):
    """A fully verified entry in the high-quality data pool."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    problem: str
    problem_source: str
    problem_id: str
    difficulty: str = "unknown"

    # First verification
    lean_proof_first: str
    first_verification: VerificationStatus

    # Resource translation
    nl_explanation: str = ""
    dsl_representation: Optional[dict] = None

    # Second verification
    lean_proof_second: str = ""
    second_verification: Optional[VerificationStatus] = None

    # Metadata
    model_source: str = ""
    secondary_model_source: str = ""
    generation_config: dict = Field(default_factory=dict)
    repair_iterations_first: int = 0
    repair_iterations_second: int = 0
    total_candidates: int = 0

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


class PoolStats(BaseModel):
    """Statistics for the data pool."""

    total_entries: int = 0
    dual_verified: int = 0
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_model: Dict[str, int] = Field(default_factory=dict)
    by_difficulty: Dict[str, int] = Field(default_factory=dict)
    avg_repair_iterations: float = 0.0
    first_pass_rate: float = 0.0
    dual_pass_rate: float = 0.0
