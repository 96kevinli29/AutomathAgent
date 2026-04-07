"""Second verification: NL/DSL → new Lean proof → verify."""

from __future__ import annotations

import json
from dataclasses import dataclass

from automath.lean.error_parser import VerificationResult
from automath.lean.verifier import LeanVerifier
from automath.llm.base import LLMClient
from automath.llm.prompts import NL_TO_LEAN, SYSTEM_LEAN4_EXPERT, extract_lean_code
from automath.repair.feedback_loop import FeedbackLoop
from automath.translation.lean_to_dsl import DSLProof
from automath.translation.lean_to_nl import NLTranslation


@dataclass
class SecondVerificationResult:
    success: bool
    new_lean_proof: str
    verification: VerificationResult
    repair_attempts: int = 0


class NLToLeanVerifier:
    """Implements second verification: NL/DSL → new Lean proof → verify."""

    def __init__(
        self,
        llm: LLMClient,
        verifier: LeanVerifier,
        max_repair_iterations: int = 3,
    ):
        self.llm = llm
        self.verifier = verifier
        self.feedback_loop = FeedbackLoop(llm, verifier, max_repair_iterations)

    async def verify_round_trip(
        self,
        problem: str,
        nl: NLTranslation,
        dsl: DSLProof | None = None,
    ) -> SecondVerificationResult:
        """Generate a new proof from NL/DSL and verify it.

        The LLM should NOT see the original proof — only the NL/DSL explanation.
        """
        # Build DSL hint if available
        dsl_hint = ""
        if dsl and dsl.steps:
            dsl_hint = f"Structured proof outline:\n```json\n{json.dumps(dsl.to_dict(), indent=2)}\n```"

        prompt = NL_TO_LEAN.format(
            problem=problem,
            nl_explanation=nl.explanation,
            dsl_hint=dsl_hint,
        )

        # Generate initial proof from NL/DSL
        responses = await self.llm.generate(
            prompt=prompt,
            system=SYSTEM_LEAN4_EXPERT,
            n=1,
            temperature=0.5,
        )

        if not responses:
            empty_result = VerificationResult(success=False, lean_code="")
            return SecondVerificationResult(
                success=False,
                new_lean_proof="",
                verification=empty_result,
            )

        new_proof = extract_lean_code(responses[0].content)

        # Run through feedback loop (verify + optional repair)
        repair_result = await self.feedback_loop.run(problem, new_proof)

        final_proof = repair_result.final_proof or new_proof
        final_verification = (
            repair_result.iterations[-1].verification
            if repair_result.iterations
            else VerificationResult(success=False, lean_code=new_proof)
        )

        return SecondVerificationResult(
            success=repair_result.success,
            new_lean_proof=final_proof,
            verification=final_verification,
            repair_attempts=repair_result.repair_rounds,
        )
