"""Metrics tracking for pipeline runs."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ProblemMetrics:
    problem_id: str
    source: str = ""
    difficulty: str = ""
    candidates_generated: int = 0
    first_pass: bool = False
    first_pass_candidate_index: int = -1
    repair_iterations: int = 0
    repair_success: bool = False
    nl_generated: bool = False
    dsl_generated: bool = False
    second_pass: bool = False
    second_repair_iterations: int = 0
    dual_verified: bool = False
    tokens_used: int = 0
    llm_time_ms: float = 0.0
    lean_time_s: float = 0.0
    model_source: str = ""


@dataclass
class RunSummary:
    run_id: str
    started_at: str
    total_problems: int = 0
    first_pass_rate: float = 0.0
    repair_success_rate: float = 0.0
    dual_verification_rate: float = 0.0
    avg_candidates: float = 0.0
    avg_repair_iterations: float = 0.0
    total_tokens: int = 0
    total_lean_time_s: float = 0.0
    total_llm_time_ms: float = 0.0
    by_difficulty: dict[str, dict] = field(default_factory=dict)
    by_model: dict[str, dict] = field(default_factory=dict)


class MetricsTracker:
    """Tracks per-problem and per-run metrics."""

    def __init__(self, metrics_dir: str | Path):
        self.metrics_dir = Path(metrics_dir).resolve()
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._problems: dict[str, ProblemMetrics] = {}
        self._start_time = time.monotonic()

    def get_or_create(self, problem_id: str) -> ProblemMetrics:
        if problem_id not in self._problems:
            self._problems[problem_id] = ProblemMetrics(problem_id=problem_id)
        return self._problems[problem_id]

    def record_generation(self, problem_id: str, candidates: int, tokens: int, model: str) -> None:
        m = self.get_or_create(problem_id)
        m.candidates_generated = candidates
        m.tokens_used += tokens
        m.model_source = model

    def record_first_verification(
        self, problem_id: str, passed: bool, candidate_index: int, lean_time: float
    ) -> None:
        m = self.get_or_create(problem_id)
        if passed and not m.first_pass:
            m.first_pass = True
            m.first_pass_candidate_index = candidate_index
        m.lean_time_s += lean_time

    def record_repair(self, problem_id: str, iterations: int, success: bool) -> None:
        m = self.get_or_create(problem_id)
        m.repair_iterations = iterations
        m.repair_success = success

    def record_translation(self, problem_id: str, nl: bool, dsl: bool) -> None:
        m = self.get_or_create(problem_id)
        m.nl_generated = nl
        m.dsl_generated = dsl

    def record_second_verification(
        self, problem_id: str, passed: bool, repair_iterations: int
    ) -> None:
        m = self.get_or_create(problem_id)
        m.second_pass = passed
        m.second_repair_iterations = repair_iterations
        m.dual_verified = m.first_pass and passed

    def summary(self) -> RunSummary:
        """Compute aggregate metrics for this run."""
        problems = list(self._problems.values())
        n = len(problems)
        if n == 0:
            return RunSummary(run_id=self.run_id, started_at="", total_problems=0)

        first_passed = sum(1 for p in problems if p.first_pass)
        repair_passed = sum(1 for p in problems if p.repair_success)
        dual_passed = sum(1 for p in problems if p.dual_verified)

        # By difficulty
        by_diff: dict[str, dict] = {}
        for p in problems:
            d = p.difficulty or "unknown"
            if d not in by_diff:
                by_diff[d] = {"total": 0, "first_pass": 0, "dual": 0}
            by_diff[d]["total"] += 1
            if p.first_pass:
                by_diff[d]["first_pass"] += 1
            if p.dual_verified:
                by_diff[d]["dual"] += 1

        # By model
        by_model: dict[str, dict] = {}
        for p in problems:
            m = p.model_source or "unknown"
            if m not in by_model:
                by_model[m] = {"total": 0, "first_pass": 0, "dual": 0}
            by_model[m]["total"] += 1
            if p.first_pass:
                by_model[m]["first_pass"] += 1
            if p.dual_verified:
                by_model[m]["dual"] += 1

        return RunSummary(
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            total_problems=n,
            first_pass_rate=first_passed / n,
            repair_success_rate=repair_passed / n,
            dual_verification_rate=dual_passed / n,
            avg_candidates=sum(p.candidates_generated for p in problems) / n,
            avg_repair_iterations=sum(p.repair_iterations for p in problems) / n,
            total_tokens=sum(p.tokens_used for p in problems),
            total_lean_time_s=sum(p.lean_time_s for p in problems),
            total_llm_time_ms=sum(p.llm_time_ms for p in problems),
            by_difficulty=by_diff,
            by_model=by_model,
        )

    def save(self) -> Path:
        """Save metrics to a JSON file."""
        summary = self.summary()
        output = {
            "summary": {
                "run_id": summary.run_id,
                "total_problems": summary.total_problems,
                "first_pass_rate": summary.first_pass_rate,
                "repair_success_rate": summary.repair_success_rate,
                "dual_verification_rate": summary.dual_verification_rate,
                "avg_candidates": summary.avg_candidates,
                "avg_repair_iterations": summary.avg_repair_iterations,
                "total_tokens": summary.total_tokens,
                "by_difficulty": summary.by_difficulty,
                "by_model": summary.by_model,
            },
            "problems": {
                pid: {
                    "source": pm.source,
                    "difficulty": pm.difficulty,
                    "candidates": pm.candidates_generated,
                    "first_pass": pm.first_pass,
                    "repair_iterations": pm.repair_iterations,
                    "dual_verified": pm.dual_verified,
                    "tokens_used": pm.tokens_used,
                    "model": pm.model_source,
                }
                for pid, pm in self._problems.items()
            },
        }
        path = self.metrics_dir / f"run_{self.run_id}.json"
        path.write_text(json.dumps(output, indent=2))
        return path
