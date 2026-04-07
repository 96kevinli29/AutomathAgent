#!/usr/bin/env python3
"""
AutomathAgent Demo — Universal dual-model proof verification.

Supports any LLM with OpenAI-compatible API:
  OpenAI, Claude, DeepSeek, Qwen, Kimi, MiniMax, Ollama, or any custom endpoint.

Usage:
    python demo.py
    python demo.py --problem "Prove that 1+1=2"
    python demo.py --model1 deepseek --model2 openai --problem "..."
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from automath.data.schema import DataPoolEntry, VerificationStatus
from automath.lean.error_parser import VerificationResult
from automath.lean.verifier import LeanVerifier
from automath.llm.openai_client import OpenAILLMClient
from automath.llm.prompts import (
    PROOF_GENERATION,
    SYSTEM_LEAN4_EXPERT,
    extract_lean_code,
    strip_think_tags,
)
from automath.repair.feedback_loop import FeedbackLoop
from automath.translation.lean_to_dsl import LeanToDSLTranslator
from automath.translation.lean_to_nl import LeanToNLTranslator
from automath.translation.nl_to_lean import NLToLeanVerifier


# ── Provider registry ────────────────────────────────────────────────────────

PROVIDERS = [
    {"key": "openai",   "name": "OpenAI (GPT-4o)",      "base_url": "https://api.openai.com/v1",                          "model": "gpt-4o",                "env": "OPENAI_API_KEY"},
    {"key": "claude",   "name": "Claude (Anthropic)",    "base_url": "https://api.anthropic.com/v1",                       "model": "claude-sonnet-4-20250514", "env": "ANTHROPIC_API_KEY"},
    {"key": "deepseek", "name": "DeepSeek",              "base_url": "https://api.deepseek.com/v1",                        "model": "deepseek-chat",          "env": "DEEPSEEK_API_KEY"},
    {"key": "qwen",     "name": "Qwen (Alibaba)",        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  "model": "qwen-plus",              "env": "QWEN_API_KEY"},
    {"key": "kimi",     "name": "Kimi (Moonshot)",       "base_url": "https://api.moonshot.cn/v1",                         "model": "moonshot-v1-128k",       "env": "KIMI_API_KEY"},
    {"key": "minimax",  "name": "MiniMax",               "base_url": "https://api.minimax.chat/v1",                        "model": "MiniMax-Text-01",        "env": "MINIMAX_API_KEY"},
    {"key": "ollama",   "name": "Ollama (local)",        "base_url": "http://localhost:11434/v1",                           "model": "llama3",                 "env": ""},
    {"key": "custom",   "name": "Custom (enter URL)",    "base_url": "",                                                    "model": "",                       "env": ""},
]


def find_provider(key: str) -> dict:
    for p in PROVIDERS:
        if p["key"] == key:
            return p
    return PROVIDERS[-1]  # fallback to custom


# ── Pretty printing ─────────────────────────────────────────────────────────

B = "\033[1m"; G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"
BL = "\033[94m"; CY = "\033[96m"; DM = "\033[2m"; E = "\033[0m"

def banner():
    print(f"""
{B}{CY}╔══════════════════════════════════════════════════════════╗
║              AutomathAgent Demo                          ║
║   Dual-Lean Verified Proof Generation & Translation      ║
╚══════════════════════════════════════════════════════════╝{E}
""")

def step(n, t, msg):  print(f"\n{B}[{n}/{t}]{E} {BL}{msg}{E}")
def ok(msg):           print(f"  {G}✓{E} {msg}")
def fail(msg):         print(f"  {R}✗{E} {msg}")
def dim(msg):          print(f"  {DM}{msg}{E}")

def box(label, content):
    print(f"\n{B}{Y}── {label} ──{E}")
    print(content)
    print(f"{Y}{'─' * (len(label) + 6)}{E}")


# ── Interactive setup ────────────────────────────────────────────────────────

def pick_provider_interactive(label: str) -> dict:
    """Show numbered menu, return provider dict."""
    print(f"\n{B}{label}:{E}")
    for i, p in enumerate(PROVIDERS, 1):
        print(f"  {i}. {p['name']}")
    while True:
        c = input(f"{B}Enter number (1-{len(PROVIDERS)}): {E}").strip()
        if c.isdigit() and 1 <= int(c) <= len(PROVIDERS):
            return PROVIDERS[int(c) - 1]
        print(f"  {R}Invalid, try again.{E}")


def configure_provider(provider: dict, label: str) -> dict:
    """Fill in base_url, model, api_key for a provider."""
    result = dict(provider)

    # Custom: ask for everything
    if provider["key"] == "custom":
        result["base_url"] = input(f"{B}Enter API base URL: {E}").strip()
        result["model"] = input(f"{B}Enter model name: {E}").strip()
        result["name"] = f"Custom ({result['model']})"

    # Ollama: no key needed, but let user override model
    if provider["key"] == "ollama":
        override = input(f"{DM}Model [{result['model']}]: {E}").strip()
        if override:
            result["model"] = override
        result["api_key"] = "ollama"
        ok(f"{label}: {result['name']} / {result['model']}")
        return result

    # Let user override model
    override = input(f"{DM}Model [{result['model']}]: {E}").strip()
    if override:
        result["model"] = override

    # Get API key: from env or input
    api_key = ""
    if result["env"]:
        api_key = os.environ.get(result["env"], "")
        if api_key:
            ok(f"Using key from ${result['env']}")

    if not api_key:
        api_key = input(f"{B}Enter API key for {result['name']}: {E}").strip()

    result["api_key"] = api_key
    ok(f"{label}: {result['name']} / {result['model']}")
    return result


def create_client(cfg: dict) -> OpenAILLMClient:
    """Create a universal OpenAI-compatible client from config."""
    return OpenAILLMClient(
        api_key=cfg["api_key"],
        model=cfg["model"],
        base_url=cfg["base_url"],
        provider_name=cfg["key"],
    )


# ── Pipeline ─────────────────────────────────────────────────────────────────

def _to_status(r: VerificationResult) -> VerificationStatus:
    return VerificationStatus(
        success=r.success,
        errors=[{"message": e.message, "type": e.error_type.value} for e in r.errors],
        has_sorry=r.has_sorry,
        elapsed_seconds=r.elapsed_seconds,
    )


async def run_demo(
    problem: str,
    llm1: OpenAILLMClient,
    llm2: OpenAILLMClient,
    cfg1: dict,
    cfg2: dict,
    lean_project: str = "lean_project",
    candidates: int = 8,
    max_repair: int = 3,
) -> Optional[DataPoolEntry]:

    N = 6
    m1 = f"{cfg1['name']} / {cfg1['model']}"
    m2 = f"{cfg2['name']} / {cfg2['model']}"

    # ── 1. Generate proof candidates (LLM 1) ────────────────────────────
    step(1, N, f"Generating Lean4 proof candidates ({m1})...")

    prompt = PROOF_GENERATION.format(problem=problem, formal_hint="")
    responses = await llm1.generate(
        prompt=prompt, system=SYSTEM_LEAN4_EXPERT, n=candidates, temperature=0.7,
    )
    proofs = [extract_lean_code(r.content) for r in responses]
    ok(f"Generated {len(proofs)} candidates")

    # ── 2. Lean4 first verification ─────────────────────────────────────
    step(2, N, "Verifying proofs with Lean4...")

    verifier = LeanVerifier(lean_project, timeout=120.0)
    verified_proof: Optional[str] = None
    verified_result: Optional[VerificationResult] = None
    repair_iters = 0

    for i, proof in enumerate(proofs):
        dim(f"Checking candidate {i+1}/{len(proofs)}...")
        result = await verifier.verify(proof)
        if result.success:
            verified_proof = proof
            verified_result = result
            ok(f"Candidate {i+1} passed! ({result.elapsed_seconds:.1f}s)")
            break
        else:
            errs = "; ".join(e.message[:60] for e in result.errors[:2])
            dim(f"  Failed: {errs}")

    # ── 3. Auto-repair if needed (LLM 1) ────────────────────────────────
    if verified_proof is None:
        step(3, N, f"Auto-repair with {m1} (max {max_repair} rounds)...")
        feedback = FeedbackLoop(llm1, verifier, max_iterations=max_repair)
        repair_result = await feedback.run(problem, proofs[0])
        repair_iters = repair_result.repair_rounds

        if repair_result.success and repair_result.final_proof:
            verified_proof = repair_result.final_proof
            verified_result = repair_result.iterations[-1].verification
            ok(f"Repaired after {repair_iters} iteration(s)")
        else:
            fail(f"Repair failed after {repair_iters} attempts.")
            await verifier.stop()
            return None
    else:
        step(3, N, "Auto-repair not needed")
        ok("Skipped")

    # ── 4. Translate to NL and DSL (LLM 1) ──────────────────────────────
    step(4, N, f"Translating proof to natural language ({m1})...")

    nl = await LeanToNLTranslator(llm1).translate(problem, verified_proof)
    dsl = await LeanToDSLTranslator(llm1).translate(problem, verified_proof)
    ok("NL and DSL translations complete")

    # ── 5. Second verification: NL → new proof (LLM 2) ──────────────────
    step(5, N, f"Second verification: NL → new Lean4 proof ({m2})...")

    second_result = await NLToLeanVerifier(
        llm2, verifier, max_repair_iterations=max_repair
    ).verify_round_trip(problem, nl, dsl)

    dual_verified = second_result.success
    if dual_verified:
        ok("Second proof verified! Dual verification complete.")
    else:
        fail("Second proof failed verification.")

    # ── 6. Output ───────────────────────────────────────────────────────
    step(6, N, "Results")

    assert verified_result is not None
    entry = DataPoolEntry(
        problem=problem,
        problem_source="user_input",
        problem_id="demo",
        difficulty="unknown",
        lean_proof_first=verified_proof,
        first_verification=_to_status(verified_result),
        nl_explanation=strip_think_tags(nl.explanation),
        dsl_representation=dsl.to_dict() if dsl.steps else None,
        lean_proof_second=second_result.new_lean_proof,
        second_verification=_to_status(second_result.verification) if dual_verified else None,
        model_source=f"{cfg1['key']}:{cfg1['model']}",
        secondary_model_source=f"{cfg2['key']}:{cfg2['model']}",
        generation_config={
            "candidates": candidates,
            "max_repair": max_repair,
            "model1": {"provider": cfg1["key"], "model": cfg1["model"], "base_url": cfg1["base_url"]},
            "model2": {"provider": cfg2["key"], "model": cfg2["model"], "base_url": cfg2["base_url"]},
        },
        repair_iterations_first=repair_iters,
        repair_iterations_second=second_result.repair_attempts,
        total_candidates=len(proofs),
    )

    box(f"Lean4 Proof (First, by {m1})", verified_proof)
    box("Natural Language Explanation", strip_think_tags(nl.explanation))
    if dual_verified and second_result.new_lean_proof.strip():
        box(f"Lean4 Proof (Second, by {m2})", second_result.new_lean_proof)

    print(f"\n{B}── Summary ──{E}")
    print(f"  Model 1 (generate):  {m1}")
    print(f"  Model 2 (verify NL): {m2}")
    print(f"  First verification:  {G}PASS{E}")
    print(f"  Repair iterations:   {repair_iters}")
    d = f"{G}PASS{E}" if dual_verified else f"{R}FAIL{E}"
    print(f"  Dual verification:   {d}")
    print(f"  Candidates tried:    {len(proofs)}")

    out_dir = Path("data/demo_output")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"result_{ts}.json"
    out_file.write_text(entry.model_dump_json(indent=2))
    print(f"\n  {G}Data saved to:{E} {out_file}")

    await verifier.stop()
    return entry


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="AutomathAgent Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Supported providers: {', '.join(p['key'] for p in PROVIDERS)}

Examples:
  python demo.py
  python demo.py --model1 deepseek --model2 openai --problem "Prove 1+1=2"
  python demo.py --model1 claude --key1 sk-ant-xxx --model2 kimi --key2 sk-xxx
  python demo.py --model1 ollama --model2 ollama --problem "..."
        """,
    )
    parser.add_argument("--problem", type=str)
    parser.add_argument("--model1", type=str, help="Provider for LLM 1")
    parser.add_argument("--model2", type=str, help="Provider for LLM 2")
    parser.add_argument("--key1", type=str, help="API key for LLM 1")
    parser.add_argument("--key2", type=str, help="API key for LLM 2")
    parser.add_argument("--candidates", type=int, default=8)
    parser.add_argument("--max-repair", type=int, default=3)
    parser.add_argument("--lean-project", type=str, default="lean_project")
    args = parser.parse_args()

    banner()

    # ── Try loading from .env first ──────────────────────────────────────
    from dotenv import dotenv_values
    env = dotenv_values(".env")

    env_m1 = env.get("MODEL1_PROVIDER", "")
    env_m2 = env.get("MODEL2_PROVIDER", "")
    env_configured = bool(env_m1 and env_m2 and env.get("MODEL1_API_KEY") and env.get("MODEL2_API_KEY"))

    if env_configured and not args.model1 and not args.model2:
        # Auto-configure from .env
        p1 = find_provider(env_m1)
        cfg1 = dict(p1)
        cfg1["api_key"] = env.get("MODEL1_API_KEY", "")
        cfg1["model"] = env.get("MODEL1_MODEL", p1["model"])
        ok(f"Model 1 (from .env): {cfg1['name']} / {cfg1['model']}")

        p2 = find_provider(env_m2)
        cfg2 = dict(p2)
        cfg2["api_key"] = env.get("MODEL2_API_KEY", "")
        cfg2["model"] = env.get("MODEL2_MODEL", p2["model"])
        ok(f"Model 2 (from .env): {cfg2['name']} / {cfg2['model']}")

        if env.get("CANDIDATES"):
            args.candidates = int(env["CANDIDATES"])
        if env.get("MAX_REPAIR"):
            args.max_repair = int(env["MAX_REPAIR"])
    else:
        # Interactive or CLI mode
        if args.model1:
            p1 = find_provider(args.model1)
        else:
            p1 = pick_provider_interactive("Select Model 1 (proof generation + translation)")

        cfg1 = configure_provider(p1, "Model 1")
        if args.key1:
            cfg1["api_key"] = args.key1

        if args.model2:
            p2 = find_provider(args.model2)
        else:
            p2 = pick_provider_interactive("Select Model 2 (second verification from NL)")

        # Reuse key if same provider
        if p2["key"] == p1["key"] and p2["key"] != "custom":
            cfg2 = dict(cfg1)
            cfg2.update({"name": p2["name"]})
            ok("Same provider — reusing API key")
        else:
            cfg2 = configure_provider(p2, "Model 2")
        if args.key2:
            cfg2["api_key"] = args.key2

    if not cfg1.get("api_key") or not cfg2.get("api_key"):
        print(f"\n{R}Error: API keys are required. Edit .env or pass --key1/--key2.{E}")
        print(f"{DM}Run: cp .env.example .env  then edit .env{E}")
        sys.exit(1)

    # ── Get problem ──────────────────────────────────────────────────────
    problem = args.problem
    if not problem:
        print(f"\n{B}Enter a math problem to prove:{E}")
        print(f"{DM}(e.g., 'Prove that if n is even, then n^2 is even'){E}")
        problem = input(f"\n{B}> {E}").strip()

    if not problem:
        print(f"\n{R}Error: A problem statement is required.{E}")
        sys.exit(1)

    box("Problem", problem)

    # ── Run ──────────────────────────────────────────────────────────────
    llm1 = create_client(cfg1)
    llm2 = create_client(cfg2)

    start = time.monotonic()
    try:
        entry = asyncio.run(run_demo(
            problem=problem, llm1=llm1, llm2=llm2, cfg1=cfg1, cfg2=cfg2,
            lean_project=args.lean_project,
            candidates=args.candidates, max_repair=args.max_repair,
        ))
    except Exception as e:
        err = str(e).lower()
        if "401" in err or "authentication" in err or "unauthorized" in err:
            print(f"\n{R}Authentication failed. Please check your API key.{E}")
            print(f"{DM}{e}{E}")
        elif "rate" in err or "429" in err or "quota" in err:
            print(f"\n{R}Rate limit or quota exceeded. Wait a moment and try again.{E}")
        elif "connect" in err or "timeout" in err:
            print(f"\n{R}Connection error. Check your network or API base URL.{E}")
            print(f"{DM}{e}{E}")
        else:
            print(f"\n{R}Error: {e}{E}")
        sys.exit(1)
    elapsed = time.monotonic() - start
    print(f"\n{DM}Total time: {elapsed:.1f}s{E}")
    if entry:
        print(f"\n{G}{B}Done!{E}")
    else:
        print(f"\n{R}Pipeline failed. Try a simpler problem or increase --candidates.{E}")
        sys.exit(1)


if __name__ == "__main__":
    main()
