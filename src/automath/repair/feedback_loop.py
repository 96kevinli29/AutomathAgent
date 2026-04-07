"""Auto-repair feedback loop: generate → verify → repair → retry."""

from __future__ import annotations

from dataclasses import dataclass, field

from automath.lean.error_parser import VerificationResult
from automath.lean.verifier import LeanVerifier
from automath.llm.base import LLMClient
from automath.llm.prompts import SYSTEM_LEAN4_EXPERT, extract_lean_code
from automath.repair.error_classifier import build_repair_prompt


@dataclass
class RepairIteration:
    iteration: int
    proof: str
    verification: VerificationResult
    repair_prompt: str = ""


@dataclass
class RepairResult:
    success: bool
    final_proof: str | None
    iterations: list[RepairIteration] = field(default_factory=list)
    total_attempts: int = 0

    @property
    def repair_rounds(self) -> int:
        return max(0, len(self.iterations) - 1)


class FeedbackLoop:
    """Orchestrates the generate-verify-repair cycle."""

    def __init__(
        self,
        llm: LLMClient,
        verifier: LeanVerifier,
        max_iterations: int = 3,
    ):
        self.llm = llm
        self.verifier = verifier
        self.max_iterations = max_iterations

    async def run(self, problem: str, initial_proof: str) -> RepairResult:
        """Run the feedback loop starting from an initial proof.

        Attempts to verify the proof, and if it fails, generates repair
        prompts and re-generates up to max_iterations times.
        """
        iterations: list[RepairIteration] = []
        current_proof = initial_proof

        for i in range(self.max_iterations + 1):
            # Verify current proof
            result = await self.verifier.verify(current_proof)

            iteration = RepairIteration(
                iteration=i,
                proof=current_proof,
                verification=result,
            )

            if result.success:
                iterations.append(iteration)
                return RepairResult(
                    success=True,
                    final_proof=current_proof,
                    iterations=iterations,
                    total_attempts=i + 1,
                )

            # Don't repair on the last iteration
            if i >= self.max_iterations:
                iterations.append(iteration)
                break

            # Build repair prompt and re-generate
            repair_prompt = build_repair_prompt(problem, current_proof, result)
            iteration.repair_prompt = repair_prompt
            iterations.append(iteration)

            responses = await self.llm.generate(
                prompt=repair_prompt,
                system=SYSTEM_LEAN4_EXPERT,
                n=1,
                temperature=0.5,  # Lower temperature for repairs
            )

            if responses:
                current_proof = extract_lean_code(responses[0].content)
            else:
                break

        return RepairResult(
            success=False,
            final_proof=None,
            iterations=iterations,
            total_attempts=len(iterations),
        )
