"""Translate verified Lean4 proofs to structured DSL representation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from automath.llm.base import LLMClient
from automath.llm.prompts import LEAN_TO_DSL, SYSTEM_LEAN4_EXPERT


@dataclass
class DSLStep:
    step: int
    tactic: str
    arguments: list[str] = field(default_factory=list)
    justification: str = ""
    subgoal_after: str = ""


@dataclass
class DSLProof:
    goal: str
    strategy: str
    steps: list[DSLStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "strategy": self.strategy,
            "steps": [
                {
                    "step": s.step,
                    "tactic": s.tactic,
                    "arguments": s.arguments,
                    "justification": s.justification,
                    "subgoal_after": s.subgoal_after,
                }
                for s in self.steps
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> DSLProof:
        steps = [
            DSLStep(
                step=s.get("step", i),
                tactic=s.get("tactic", ""),
                arguments=s.get("arguments", []),
                justification=s.get("justification", ""),
                subgoal_after=s.get("subgoal_after", ""),
            )
            for i, s in enumerate(data.get("steps", []), 1)
        ]
        return cls(
            goal=data.get("goal", ""),
            strategy=data.get("strategy", ""),
            steps=steps,
        )


class LeanToDSLTranslator:
    """Translates a verified Lean4 proof to a structured DSL."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def translate(self, problem: str, lean_proof: str) -> DSLProof:
        """Translate a Lean4 proof into a structured DSL representation."""
        prompt = LEAN_TO_DSL.format(problem=problem, lean_proof=lean_proof)

        responses = await self.llm.generate(
            prompt=prompt,
            system=SYSTEM_LEAN4_EXPERT,
            n=1,
            temperature=0.2,
        )

        if not responses:
            return DSLProof(goal=problem, strategy="Translation failed.")

        return self._parse_response(responses[0].content, problem)

    def _parse_response(self, text: str, problem: str) -> DSLProof:
        """Parse the LLM's JSON response into a DSLProof."""
        import re

        # Extract JSON from markdown code block
        match = re.search(r"```json\s*\n(.*?)```", text, re.DOTALL)
        json_str = match.group(1) if match else text

        try:
            data = json.loads(json_str)
            return DSLProof.from_dict(data)
        except json.JSONDecodeError:
            return DSLProof(goal=problem, strategy="Failed to parse DSL response.")
