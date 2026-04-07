"""Top-level pipeline orchestrator: problem → data pool entry."""

from __future__ import annotations

import asyncio
import structlog
from dataclasses import dataclass, field

from automath.config import AutomathConfig
from automath.data.pool import DataPool
from automath.data.schema import DataPoolEntry, MathProblem, VerificationStatus
from automath.lean.error_parser import VerificationResult
from automath.lean.server_pool import LeanServerPool
from automath.lean.verifier import LeanVerifier
from automath.llm.base import LLMClient
from automath.llm.prompts import PROOF_GENERATION, SYSTEM_LEAN4_EXPERT, extract_lean_code
from automath.metrics.tracker import MetricsTracker
from automath.repair.feedback_loop import FeedbackLoop
from automath.translation.lean_to_dsl import LeanToDSLTranslator
from automath.translation.lean_to_nl import LeanToNLTranslator
from automath.translation.nl_to_lean import NLToLeanVerifier

logger = structlog.get_logger()


@dataclass
class PipelineResult:
    problem_id: str
    success: bool
    dual_verified: bool = False
    first_proof: str | None = None
    second_proof: str | None = None
    nl_explanation: str = ""
    candidates_tried: int = 0
    repair_iterations: int = 0
    error: str = ""


@dataclass
class BatchResult:
    total: int = 0
    first_pass: int = 0
    dual_verified: int = 0
    failed: int = 0
    results: list[PipelineResult] = field(default_factory=list)


def _verification_to_status(result: VerificationResult) -> VerificationStatus:
    return VerificationStatus(
        success=result.success,
        errors=[{"message": e.message, "type": e.error_type.value} for e in result.errors],
        warnings=[{"message": w.message} for w in result.warnings],
        has_sorry=result.has_sorry,
        elapsed_seconds=result.elapsed_seconds,
    )


class AutomathPipeline:
    """Orchestrates the full dual-verification pipeline."""

    def __init__(
        self,
        config: AutomathConfig,
        llm: LLMClient,
        verifier_pool: LeanServerPool,
        data_pool: DataPool,
        metrics: MetricsTracker,
        secondary_llm: LLMClient | None = None,
    ):
        self.config = config
        self.llm = llm
        self.secondary_llm = secondary_llm
        self.pool = verifier_pool
        self.data_pool = data_pool
        self.metrics = metrics

        # Create a single verifier for repair loops (uses the pool internally)
        self._single_verifier = LeanVerifier(
            config.lean_project_path, timeout=config.lean_verification_timeout
        )

        self.feedback_loop = FeedbackLoop(
            llm, self._single_verifier, config.max_repair_iterations
        )
        self.nl_translator = LeanToNLTranslator(llm)
        self.dsl_translator = LeanToDSLTranslator(llm)
        self.second_verifier = NLToLeanVerifier(
            llm, self._single_verifier, config.max_repair_iterations
        )

    async def process_problem(self, problem: MathProblem) -> PipelineResult:
        """Full pipeline for a single problem."""
        log = logger.bind(problem_id=problem.id, source=problem.source)
        log.info("processing_problem")

        # Step 1: Generate candidate proofs
        formal_hint = ""
        if problem.formal_statement:
            formal_hint = f"Formal statement (Lean4):\n```lean\n{problem.formal_statement}\n```"

        prompt = PROOF_GENERATION.format(
            problem=problem.nl_statement, formal_hint=formal_hint
        )

        candidates = await self.llm.generate(
            prompt=prompt,
            system=SYSTEM_LEAN4_EXPERT,
            n=self.config.candidates_per_problem,
            temperature=self.config.llm_temperature,
        )

        total_tokens = sum(r.usage.total_tokens for r in candidates)
        self.metrics.record_generation(
            problem.id, len(candidates), total_tokens, self.llm.provider_name
        )
        log.info("candidates_generated", count=len(candidates))

        # Step 2: Extract and verify all candidates in parallel
        proofs = [extract_lean_code(c.content) for c in candidates]
        results = await self.pool.verify_batch(proofs)

        # Find first passing candidate
        verified_proof: str | None = None
        verified_result: VerificationResult | None = None
        repair_iters = 0

        for i, (proof, result) in enumerate(zip(proofs, results)):
            self.metrics.record_first_verification(
                problem.id, result.success, i, result.elapsed_seconds
            )
            if result.success:
                verified_proof = proof
                verified_result = result
                log.info("first_pass", candidate_index=i)
                break

        # Step 3: If no candidate passed, try repair on the best one
        if verified_proof is None:
            log.info("no_first_pass_trying_repair")
            # Pick the candidate with fewest errors
            best_idx = min(
                range(len(results)), key=lambda i: len(results[i].errors)
            )
            repair_result = await self.feedback_loop.run(problem.nl_statement, proofs[best_idx])
            self.metrics.record_repair(
                problem.id, repair_result.total_attempts, repair_result.success
            )
            repair_iters = repair_result.repair_rounds

            if repair_result.success and repair_result.final_proof:
                verified_proof = repair_result.final_proof
                verified_result = repair_result.iterations[-1].verification
                log.info("repair_success", iterations=repair_iters)
            else:
                log.warn("repair_failed")
                return PipelineResult(
                    problem_id=problem.id,
                    success=False,
                    candidates_tried=len(proofs),
                    repair_iterations=repair_iters,
                    error="All candidates and repair attempts failed.",
                )

        # Step 4: Translate to NL and DSL
        nl = await self.nl_translator.translate(problem.nl_statement, verified_proof)
        dsl = await self.dsl_translator.translate(problem.nl_statement, verified_proof)
        self.metrics.record_translation(problem.id, nl=bool(nl.explanation), dsl=bool(dsl.steps))
        log.info("translation_complete")

        # Step 5: Second verification (NL/DSL → new Lean proof)
        second_result = await self.second_verifier.verify_round_trip(
            problem.nl_statement, nl, dsl
        )
        self.metrics.record_second_verification(
            problem.id, second_result.success, second_result.repair_attempts
        )

        dual_verified = second_result.success
        log.info("second_verification", passed=dual_verified)

        # Step 6: Add to data pool
        assert verified_result is not None
        entry = DataPoolEntry(
            problem=problem.nl_statement,
            problem_source=problem.source,
            problem_id=problem.id,
            difficulty=problem.difficulty,
            lean_proof_first=verified_proof,
            first_verification=_verification_to_status(verified_result),
            nl_explanation=nl.explanation,
            dsl_representation=dsl.to_dict() if dsl.steps else None,
            lean_proof_second=second_result.new_lean_proof,
            second_verification=_verification_to_status(second_result.verification) if dual_verified else None,
            model_source=self.llm.provider_name,
            generation_config={
                "temperature": self.config.llm_temperature,
                "candidates": self.config.candidates_per_problem,
                "model": self.config.llm_model,
            },
            repair_iterations_first=repair_iters,
            repair_iterations_second=second_result.repair_attempts,
            total_candidates=len(proofs),
        )
        self.data_pool.add(entry)
        log.info("added_to_pool", entry_id=entry.id)

        return PipelineResult(
            problem_id=problem.id,
            success=True,
            dual_verified=dual_verified,
            first_proof=verified_proof,
            second_proof=second_result.new_lean_proof if dual_verified else None,
            nl_explanation=nl.explanation,
            candidates_tried=len(proofs),
            repair_iterations=repair_iters,
        )

    async def run_batch(
        self, problems: list[MathProblem], concurrency: int | None = None
    ) -> BatchResult:
        """Process multiple problems with controlled concurrency."""
        concurrency = concurrency or self.config.problem_concurrency
        semaphore = asyncio.Semaphore(concurrency)
        batch = BatchResult(total=len(problems))

        async def _process(problem: MathProblem) -> PipelineResult:
            async with semaphore:
                try:
                    return await self.process_problem(problem)
                except Exception as e:
                    logger.error("problem_failed", problem_id=problem.id, error=str(e))
                    return PipelineResult(
                        problem_id=problem.id, success=False, error=str(e)
                    )

        results = await asyncio.gather(*[_process(p) for p in problems])

        for r in results:
            batch.results.append(r)
            if r.success:
                batch.first_pass += 1
            else:
                batch.failed += 1
            if r.dual_verified:
                batch.dual_verified += 1

        return batch
