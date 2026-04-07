#!/usr/bin/env python3
"""CLI entry point for running the AutomathAgent pipeline."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
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


def create_llm_client(config: AutomathConfig, provider: str | None = None, model: str | None = None):
    """Create an LLM client based on config."""
    provider = provider or config.llm_provider
    if provider == "claude":
        return ClaudeLLMClient(api_key=config.claude_api_key, model=model or config.llm_model)
    elif provider == "openai":
        return OpenAILLMClient(api_key=config.openai_api_key, model=model or config.secondary_llm_model)
    else:
        raise ValueError(f"Unknown provider: {provider}")


async def main(args: argparse.Namespace) -> None:
    config = AutomathConfig()
    setup_logging(config.log_dir, json_output=not args.verbose)

    # Load dataset
    loader = get_loader(args.dataset, args.data_path)
    problems = loader.load()

    if args.limit:
        problems = problems[: args.limit]

    print(f"Loaded {len(problems)} problems from {args.dataset}")

    # Create components
    primary_llm = create_llm_client(config)
    secondary_llm = None
    if args.dual_model:
        secondary_llm = create_llm_client(
            config, config.secondary_llm_provider, config.secondary_llm_model
        )

    pool = LeanServerPool(
        config.lean_project_path,
        pool_size=config.lean_repl_pool_size,
        timeout=config.lean_verification_timeout,
    )
    data_pool = DataPool(config.data_pool_dir)
    metrics = MetricsTracker(config.metrics_dir)

    pipeline = AutomathPipeline(
        config=config,
        llm=primary_llm,
        verifier_pool=pool,
        data_pool=data_pool,
        metrics=metrics,
        secondary_llm=secondary_llm,
    )

    # Run
    async with pool:
        batch_result = await pipeline.run_batch(
            problems, concurrency=args.concurrency or config.problem_concurrency
        )

    # Report
    summary = metrics.summary()
    metrics_path = metrics.save()

    print("\n=== Pipeline Results ===")
    print(f"Total problems:        {batch_result.total}")
    print(f"First pass:            {batch_result.first_pass} ({summary.first_pass_rate:.1%})")
    print(f"Dual verified:         {batch_result.dual_verified} ({summary.dual_verification_rate:.1%})")
    print(f"Failed:                {batch_result.failed}")
    print(f"Avg repair iterations: {summary.avg_repair_iterations:.2f}")
    print(f"Total tokens used:     {summary.total_tokens}")
    print(f"Data pool size:        {data_pool.size}")
    print(f"Metrics saved to:      {metrics_path}")

    # Snapshot data pool
    if args.snapshot:
        snapshot_path = data_pool.snapshot(args.snapshot)
        print(f"Pool snapshot:         {snapshot_path}")

    # Cleanup
    await primary_llm.close()
    if secondary_llm:
        await secondary_llm.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AutomathAgent Pipeline")
    parser.add_argument("--dataset", required=True, choices=["miniF2F", "ProofNet", "LeanWorkbook"])
    parser.add_argument("--data-path", required=True, help="Path to dataset file")
    parser.add_argument("--limit", type=int, help="Limit number of problems")
    parser.add_argument("--concurrency", type=int, help="Problem-level concurrency")
    parser.add_argument("--dual-model", action="store_true", help="Use secondary LLM for comparison")
    parser.add_argument("--snapshot", type=str, help="Create pool snapshot with this version tag")
    parser.add_argument("--verbose", action="store_true", help="Human-readable log output")
    args = parser.parse_args()

    asyncio.run(main(args))
