"""Translate verified Lean4 proofs to natural language explanations."""

from __future__ import annotations

from dataclasses import dataclass, field

from automath.llm.base import LLMClient
from automath.llm.prompts import LEAN_TO_NL, SYSTEM_LEAN4_EXPERT


@dataclass
class NLTranslation:
    explanation: str
    step_by_step: list[str] = field(default_factory=list)
    key_lemmas: list[str] = field(default_factory=list)


class LeanToNLTranslator:
    """Translates a verified Lean4 proof to natural language explanation."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def translate(self, problem: str, lean_proof: str) -> NLTranslation:
        """Translate a Lean4 proof into natural language."""
        prompt = LEAN_TO_NL.format(problem=problem, lean_proof=lean_proof)

        responses = await self.llm.generate(
            prompt=prompt,
            system=SYSTEM_LEAN4_EXPERT,
            n=1,
            temperature=0.3,
        )

        if not responses:
            return NLTranslation(explanation="Translation failed.")

        text = responses[0].content
        steps = self._parse_steps(text)
        lemmas = self._extract_lemmas(text)

        return NLTranslation(
            explanation=text,
            step_by_step=steps,
            key_lemmas=lemmas,
        )

    def _parse_steps(self, text: str) -> list[str]:
        """Extract numbered steps from the explanation."""
        import re
        steps = re.findall(r"^\d+\.\s*(.+)$", text, re.MULTILINE)
        return steps

    def _extract_lemmas(self, text: str) -> list[str]:
        """Extract Mathlib lemma names mentioned in the explanation."""
        import re
        # Match common Lean identifier patterns (e.g., Nat.add_comm, List.map_id)
        lemmas = re.findall(r"`([A-Z][a-zA-Z0-9_.]+)`", text)
        return list(set(lemmas))
