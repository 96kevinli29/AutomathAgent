"""Abstract LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = ""
    latency_ms: float = 0.0


class LLMClient(ABC):
    """Abstract interface for LLM providers."""

    provider_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str = "",
        n: int = 1,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> list[LLMResponse]:
        """Generate n completions for the given prompt."""

    async def close(self) -> None:
        """Clean up resources."""
