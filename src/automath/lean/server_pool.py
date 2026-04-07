"""Pool of Lean REPL instances for parallel verification."""

from __future__ import annotations

import asyncio
from pathlib import Path

from automath.lean.error_parser import VerificationResult
from automath.lean.verifier import LeanVerifier


class LeanServerPool:
    """Manages a pool of Lean REPL instances for parallel verification."""

    def __init__(
        self,
        lean_project_path: str | Path,
        pool_size: int = 10,
        timeout: float = 60.0,
    ):
        self.lean_project_path = Path(lean_project_path).resolve()
        self.pool_size = pool_size
        self.timeout = timeout
        self._verifiers: list[LeanVerifier] = []
        self._semaphore = asyncio.Semaphore(pool_size)
        self._index = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Initialize and start all REPL instances in the pool."""
        self._verifiers = [
            LeanVerifier(self.lean_project_path, timeout=self.timeout)
            for _ in range(self.pool_size)
        ]
        # Start all verifiers concurrently
        await asyncio.gather(*(v.start() for v in self._verifiers))

    async def stop(self) -> None:
        """Stop all REPL instances."""
        await asyncio.gather(*(v.stop() for v in self._verifiers))
        self._verifiers = []

    async def _get_verifier(self) -> LeanVerifier:
        """Get the next available verifier (round-robin)."""
        async with self._lock:
            verifier = self._verifiers[self._index % self.pool_size]
            self._index += 1
            return verifier

    async def verify(self, lean_code: str, timeout: float | None = None) -> VerificationResult:
        """Verify a single proof using an available REPL from the pool."""
        async with self._semaphore:
            verifier = await self._get_verifier()
            return await verifier.verify(lean_code, timeout=timeout)

    async def verify_batch(
        self, proofs: list[str], timeout: float | None = None
    ) -> list[VerificationResult]:
        """Verify multiple proofs in parallel using the pool."""
        tasks = [self.verify(proof, timeout=timeout) for proof in proofs]
        return await asyncio.gather(*tasks)

    async def __aenter__(self) -> LeanServerPool:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()
