"""Universal OpenAI-compatible LLM client.

Works with any provider that supports the OpenAI chat completions API:
OpenAI, Claude, DeepSeek, Qwen, Kimi, MiniMax, Ollama, etc.
"""

from __future__ import annotations

import asyncio
import time

from openai import AsyncOpenAI

from automath.llm.base import LLMClient, LLMResponse, TokenUsage


class OpenAILLMClient(LLMClient):
    """Universal OpenAI-compatible adapter.

    Works with any provider by setting base_url:
        OpenAI:    base_url="https://api.openai.com/v1"
        Claude:    base_url="https://api.anthropic.com/v1"
        DeepSeek:  base_url="https://api.deepseek.com/v1"
        Qwen:      base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        Kimi:      base_url="https://api.moonshot.cn/v1"
        MiniMax:   base_url="https://api.minimax.chat/v1"
        Ollama:    base_url="http://localhost:11434/v1"
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str = "https://api.openai.com/v1",
        provider_name: str = "openai",
    ):
        self.model = model
        self.provider_name = provider_name
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def generate(
        self,
        prompt: str,
        system: str = "",
        n: int = 1,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> list[LLMResponse]:
        """Generate n completions.

        Uses native n parameter for OpenAI; falls back to parallel calls
        for providers that don't support n>1.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if n == 1 or self.provider_name == "openai":
            return await self._call(messages, n, temperature, max_tokens)
        else:
            # Non-OpenAI providers: sequential calls with small delay to avoid rate limits
            results = []
            for i in range(n):
                try:
                    batch = await self._call(messages, 1, temperature, max_tokens)
                    results.extend(batch)
                except Exception:
                    if results:  # got some results, continue
                        continue
                    raise
                if i < n - 1:
                    await asyncio.sleep(0.3)  # small delay between calls
            return results

    async def _call(
        self, messages: list, n: int, temperature: float, max_tokens: int
    ) -> list[LLMResponse]:
        start = time.monotonic()

        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        # Only add optional params if non-default (some providers reject them)
        if n > 1:
            kwargs["n"] = n
        if temperature is not None:
            kwargs["temperature"] = temperature

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            err_msg = str(e).lower()
            # Auto-retry: drop unsupported params (temperature, n, max_tokens)
            if "temperature" in err_msg:
                kwargs.pop("temperature", None)
                response = await self._client.chat.completions.create(**kwargs)
            elif "n" in err_msg or "only 1" in err_msg:
                kwargs.pop("n", None)
                response = await self._client.chat.completions.create(**kwargs)
            elif "max_tokens" in err_msg:
                kwargs.pop("max_tokens", None)
                response = await self._client.chat.completions.create(**kwargs)
            else:
                raise

        elapsed = (time.monotonic() - start) * 1000

        results = []
        choices = response.choices or []
        if not choices:
            # Some providers return content differently; try raw response
            raise RuntimeError(
                f"Empty response from {self.provider_name}/{self.model}. "
                f"Check that the model name is correct and your API key has access."
            )

        for choice in choices:
            usage = TokenUsage()
            if response.usage:
                pt = getattr(response.usage, "prompt_tokens", 0) or 0
                ct = getattr(response.usage, "completion_tokens", 0) or 0
                usage = TokenUsage(
                    prompt_tokens=pt,
                    completion_tokens=ct // max(n, 1),
                )
            content = ""
            if choice.message and choice.message.content:
                content = choice.message.content
            results.append(
                LLMResponse(
                    content=content,
                    model=response.model or self.model,
                    usage=usage,
                    finish_reason=choice.finish_reason or "",
                    latency_ms=elapsed,
                )
            )
        return results

    async def close(self) -> None:
        await self._client.close()
