#!/usr/bin/env python3
"""Generate visualizations from benchmark metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_metrics(metrics_dir: str = "data/metrics") -> list[dict]:
    """Load all run metrics from the metrics directory."""
    metrics_path = Path(metrics_dir)
    runs = []
    for f in sorted(metrics_path.glob("run_*.json")):
        runs.append(json.loads(f.read_text()))
    return runs


def load_comparison(metrics_dir: str = "data/metrics") -> list[dict]:
    """Load benchmark comparison data."""
    path = Path(metrics_dir) / "benchmark_comparison.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def plot_pass_rates(comparison: list[dict], output_dir: str = "data/metrics") -> None:
    """Plot first pass and dual verification rates by model."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not comparison:
        print("No comparison data found.")
        return

    models = [f"{r['provider']}/{r['model']}" for r in comparison]
    first_pass = [r["first_pass_rate"] for r in comparison]
    dual_rate = [r["dual_rate"] for r in comparison]

    x = np.arange(len(models))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, first_pass, width, label="First Pass Rate", color="#4A90D9")
    bars2 = ax.bar(x + width / 2, dual_rate, width, label="Dual Verification Rate", color="#E8744F")

    ax.set_ylabel("Rate")
    ax.set_title("Proof Verification Rates by Model")
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()
    ax.set_ylim(0, 1.0)

    # Add value labels
    for bar in bars1 + bars2:
        height = bar.get_height()
        ax.annotate(f"{height:.1%}", xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points", ha="center", va="bottom")

    plt.tight_layout()
    out = Path(output_dir) / "pass_rates.png"
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


def plot_repair_convergence(runs: list[dict], output_dir: str = "data/metrics") -> None:
    """Plot repair convergence across runs."""
    import matplotlib.pyplot as plt

    if not runs:
        print("No run data found.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    for run in runs:
        summary = run.get("summary", {})
        problems = run.get("problems", {})
        if not problems:
            continue

        # Count repair iteration distribution
        repair_counts = {}
        for p in problems.values():
            iters = p.get("repair_iterations", 0)
            repair_counts[iters] = repair_counts.get(iters, 0) + 1

        iters = sorted(repair_counts.keys())
        counts = [repair_counts[i] for i in iters]
        label = f"Run {summary.get('run_id', 'unknown')}"
        ax.plot(iters, counts, marker="o", label=label)

    ax.set_xlabel("Repair Iterations")
    ax.set_ylabel("Number of Problems")
    ax.set_title("Repair Iteration Distribution")
    ax.legend()
    plt.tight_layout()

    out = Path(output_dir) / "repair_convergence.png"
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


def plot_difficulty_breakdown(runs: list[dict], output_dir: str = "data/metrics") -> None:
    """Plot pass rates by difficulty level."""
    import matplotlib.pyplot as plt
    import numpy as np

    if not runs:
        return

    # Use the latest run
    latest = runs[-1]
    by_diff = latest.get("summary", {}).get("by_difficulty", {})
    if not by_diff:
        print("No difficulty breakdown data.")
        return

    difficulties = list(by_diff.keys())
    totals = [by_diff[d]["total"] for d in difficulties]
    first_pass = [by_diff[d]["first_pass"] / by_diff[d]["total"] if by_diff[d]["total"] > 0 else 0 for d in difficulties]
    dual = [by_diff[d].get("dual", 0) / by_diff[d]["total"] if by_diff[d]["total"] > 0 else 0 for d in difficulties]

    x = np.arange(len(difficulties))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x - width / 2, first_pass, width, label="First Pass", color="#4A90D9")
    ax.bar(x + width / 2, dual, width, label="Dual Verified", color="#E8744F")

    ax.set_ylabel("Rate")
    ax.set_title("Pass Rates by Difficulty")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{d}\n(n={t})" for d, t in zip(difficulties, totals)])
    ax.legend()
    ax.set_ylim(0, 1.0)
    plt.tight_layout()

    out = Path(output_dir) / "difficulty_breakdown.png"
    plt.savefig(out, dpi=150)
    print(f"Saved: {out}")


def main() -> None:
    metrics_dir = "data/metrics"
    Path(metrics_dir).mkdir(parents=True, exist_ok=True)

    runs = load_metrics(metrics_dir)
    comparison = load_comparison(metrics_dir)

    print(f"Found {len(runs)} run(s) and {len(comparison)} comparison result(s)\n")

    plot_pass_rates(comparison, metrics_dir)
    plot_repair_convergence(runs, metrics_dir)
    plot_difficulty_breakdown(runs, metrics_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
