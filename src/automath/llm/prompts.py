"""Prompt templates for proof generation, repair, and translation."""

from __future__ import annotations

SYSTEM_LEAN4_EXPERT = """You are an expert in Lean4 theorem proving with deep knowledge of Mathlib4.
You write correct, concise Lean4 proofs. Always use `import Mathlib` at the top.
Output ONLY the Lean4 code inside a ```lean code block, with no other text."""

PROOF_GENERATION = """Prove the following mathematical statement in Lean4.
Generate a complete, compilable Lean4 proof using Mathlib4 tactics.

Statement:
{problem}

{formal_hint}

Requirements:
- Use `import Mathlib` at the top
- The proof must compile without errors or `sorry`
- Prefer automation tactics (omega, simp, norm_num, decide, aesop) when applicable
- Use structured proofs (calc, have, suffices) for complex reasoning

```lean
"""

PROOF_REPAIR = """The following Lean4 proof failed verification. Fix it.

Original problem:
{problem}

Failed proof:
```lean
{failed_proof}
```

Lean4 error messages:
{error_messages}

Error analysis:
- Error type: {error_type}
- {error_guidance}

Generate a corrected proof. Output ONLY the complete Lean4 code in a ```lean block.
"""

LEAN_TO_NL = """Translate the following Lean4 proof into a clear, step-by-step natural language explanation.

Problem statement:
{problem}

Lean4 proof:
```lean
{lean_proof}
```

Provide:
1. A concise summary of the proof strategy
2. Step-by-step explanation of each tactic/term
3. Key lemmas and theorems used from Mathlib

Format your response as a numbered list of steps.
"""

LEAN_TO_DSL = """Convert the following Lean4 proof into a structured proof representation.

Problem statement:
{problem}

Lean4 proof:
```lean
{lean_proof}
```

Output a JSON object with this structure:
```json
{{
  "goal": "<theorem statement>",
  "strategy": "<high-level proof strategy>",
  "steps": [
    {{
      "step": 1,
      "tactic": "<tactic used>",
      "arguments": ["<args>"],
      "justification": "<why this step works>",
      "subgoal_after": "<remaining goal after this step>"
    }}
  ]
}}
```
"""

NL_TO_LEAN = """Based on the following natural language proof explanation, write a NEW Lean4 proof.
Do NOT copy the original proof — reconstruct it from the explanation alone.

Problem statement:
{problem}

Proof explanation:
{nl_explanation}

{dsl_hint}

Generate a complete, compilable Lean4 proof using Mathlib4. Output ONLY the Lean4 code in a ```lean block.
"""

# Error-type-specific repair guidance
REPAIR_GUIDANCE = {
    "type_mismatch": "The types do not match. Check the expected vs actual types and fix the term or tactic.",
    "unknown_identifier": "An identifier or lemma name is incorrect. Search for the correct name in Mathlib4.",
    "tactic_failed": "The tactic could not solve the goal. Try a different tactic or break the goal into sub-goals.",
    "syntax_error": "There is a syntax error. Check for missing tokens, parentheses, or incorrect Lean4 syntax.",
    "sorry_remaining": "The proof is incomplete. Fill in all remaining `sorry` placeholders.",
    "timeout": "The proof timed out. Simplify the approach or use more direct tactics.",
    "import_error": "An import is missing or incorrect. Use `import Mathlib` for full Mathlib access.",
    "other": "Review the error message carefully and fix the proof accordingly.",
}


def strip_think_tags(text: str) -> str:
    """Strip <think>...</think> blocks from thinking models (MiniMax, DeepSeek, etc.)."""
    import re
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def extract_lean_code(response: str) -> str:
    """Extract Lean4 code from an LLM response (strips markdown fences and think tags)."""
    import re

    # Strip thinking tags first
    response = strip_think_tags(response)

    # Try to find ```lean ... ``` block
    match = re.search(r"```lean4?\s*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try generic code block
    match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Return raw response (might already be pure code)
    return response.strip()
