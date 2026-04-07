"""Configuration for AutomathAgent using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AutomathConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTOMATH_")

    # LLM settings
    llm_provider: str = "claude"
    claude_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-20250514"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Second model for comparison experiments
    secondary_llm_provider: str = "openai"
    secondary_llm_model: str = "gpt-4o"

    # Generation settings
    candidates_per_problem: int = 16
    max_repair_iterations: int = 3

    # Lean settings
    lean_project_path: str = "lean_project"
    lean_repl_pool_size: int = 10
    lean_verification_timeout: float = 60.0
    lean_backend: str = "subprocess"  # "lean_interact" | "subprocess"

    # Data settings
    data_pool_dir: str = "data/pool"
    log_dir: str = "data/logs"
    metrics_dir: str = "data/metrics"

    # Pipeline settings
    problem_concurrency: int = 4
    batch_size: int = 50

    def get_lean_project_abs_path(self) -> Path:
        return Path(self.lean_project_path).resolve()

    def get_data_pool_abs_path(self) -> Path:
        return Path(self.data_pool_dir).resolve()
