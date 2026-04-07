#!/usr/bin/env python3
"""Batch benchmark runner: compare models across datasets."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from automath.config import AutomathConfig
from automath.data.loader import get_loader
from automath.data.pool import DataPool
from automath.lean.server_pool import LeanServerPool
from automath.llm.claude import ClaudeLLMClient
from automath.llm.openai_client import OpenAILLMClient
from automath.metrics.tracker import MetricsTracker
from automath.pipeline import AutomathPipeline
from automath.utils.logging import setup_logging


async def run_single_benchmark(
    config: AutomathConfig,
    provider: str,
    model: str,
    dataset: str,
    data_path: str,
    limit: int | None,
) -> dict:
    """Run benchmark for a single model on a single dataset."""
    # Load dataset
    loader = get_loader(dataset, data_path)
    problems = loader.load()
    if limit:
        problems = problems[:limit]

    # Create LLM client
    if provider == "claude":
        llm = ClaudeLLMClient(api_key=config.claude_api_key, model=model)
    elif provider == "openai":
        llm = OpenAILLMClient(api_key=config.openai_api_key, model=model)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    pool = LeanServerPool(
        config.lean_project_path,
        pool_size=config.lean_repl_pool_size,
        timeout=config.lean_verification_timeout,
    )
    data_pool = DataPool(f"data/pool/benchmark_{provider}_{dataset}")
    metrics = MetricsTracker(config.metrics_dir)

    pipeline = AutomathPipeline(
        config=config, llm=llm, verifier_pool=pool,
        data_pool=data_pool, metrics=metrics,
    )

    async with pool:
        batch = await pipeline.run_batch(problems, concurrency=config.problem_concurrency)

    summary = metrics.summary()
    metrics.save()
    await llm.close()

    return {
        "provider": provider,
        "model": model,
        "dataset": dataset,
        "total": batch.total,
        "first_pass": batch.first_pass,
        "first_pass_rate": summary.first_pass_rate,
        "dual_verified": batch.dual_verified,
        "dual_rate": summary.dual_verification_rate,
        "avg_repair": summary.avg_repair_iterations,
        "tokens": summary.total_tokens,
    }


async def main(args: argparse.Namespace) -> None:
    config = AutomathConfig()
    setup_logging(config.log_dir, json_output=False)

    models = [
        ("claude", config.llm_model),
        ("openai", config.secondary_llm_model),
    ]
    if args.model:
        models = [(args.provider, args.model)]

    all_results = []
    for provider, model in models:
        print(f"\n{'='*60}")
        print(f"Benchmarking {provider}/{model} on {args.dataset}")
        print(f"{'='*60}")

        result = await run_single_benchmark(
            config, provider, model, args.dataset, args.data_path, args.limit
        )
        all_results.append(result)

        print(f"  First pass rate:  {result['first_pass_rate']:.1%}")
        print(f"  Dual verify rate: {result['dual_rate']:.1%}")
        print(f"  Avg repair iter:  {result['avg_repair']:.2f}")
        print(f"  Tokens used:      {result['tokens']}")

    # Save comparison
    output_path = Path(config.metrics_dir) / "benchmark_comparison.json"
    output_path.write_text(json.dumps(all_results, indent=2))
    print(f"\nComparison saved to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutomathAgent Benchmark")
    parser.add_argument("--dataset", required=True, choices=["miniF2F", "ProofNet", "LeanWorkbook"])
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.parse_args()
    args = parser.parse_args()
    asyncio.run(main(args))
