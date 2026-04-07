"""Claude (Anthropic) LLM client."""

from __future__ import annotations

import asyncio
import time

from anthropic import AsyncAnthropic

from automath.llm.base import LLMClient, LLMResponse, TokenUsage


class ClaudeLLMClient(LLMClient):
    """Anthropic Claude adapter."""

    provider_name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def generate(
        self,
        prompt: str,
        system: str = "",
        n: int = 1,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> list[LLMResponse]:
        """Generate n completions by making n parallel API calls."""
        tasks = [
            self._single_generate(prompt, system, temperature, max_tokens)
            for _ in range(n)
        ]
        return await asyncio.gather(*tasks)

    async def _single_generate(
        self, prompt: str, system: str, temperature: float, max_tokens: int
    ) -> LLMResponse:
        start = time.monotonic()
        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        elapsed = (time.monotonic() - start) * 1000

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            usage=TokenUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            ),
            finish_reason=response.stop_reason or "",
            latency_ms=elapsed,
        )

    async def close(self) -> None:
        await self._client.close()
