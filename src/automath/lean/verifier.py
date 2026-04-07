"""Core Lean4 REPL verification via subprocess."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from automath.lean.error_parser import VerificationResult, parse_repl_response


class LeanVerifier:
    """Verifies Lean4 proof code via the REPL subprocess."""

    def __init__(self, lean_project_path: str | Path, timeout: float = 60.0):
        self.lean_project_path = Path(lean_project_path).resolve()
        self.timeout = timeout
        self._process: asyncio.subprocess.Process | None = None
        self._env_counter = 0
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the Lean REPL subprocess via `lake exe repl`."""
        import shutil

        # Find lake executable
        lake_bin = shutil.which("lake")
        if not lake_bin:
            elan_lake = Path.home() / ".elan" / "bin" / "lake"
            if elan_lake.exists():
                lake_bin = str(elan_lake)
            else:
                raise FileNotFoundError(
                    "lake not found. Install elan: curl https://elan.lean-lang.org/elan-init.sh -sSf | sh"
                )

        self._process = await asyncio.create_subprocess_exec(
            lake_bin, "exe", "repl",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.lean_project_path),
        )
        self._env_counter = 0

    async def stop(self) -> None:
        """Stop the REPL subprocess."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
        self._process = None

    def _ensure_imports(self, lean_code: str) -> str:
        """Prepend 'import Mathlib' if no import statement is present."""
        if not any(line.strip().startswith("import") for line in lean_code.splitlines()):
            lean_code = "import Mathlib\n\n" + lean_code
        return lean_code

    async def verify(self, lean_code: str, timeout: float | None = None) -> VerificationResult:
        """Verify a Lean4 proof string via the REPL.

        Returns a VerificationResult with success/failure and structured errors.
        """
        if self._process is None or self._process.returncode is not None:
            await self.start()

        timeout = timeout or self.timeout
        lean_code = self._ensure_imports(lean_code)
        start_time = time.monotonic()

        async with self._lock:
            cmd = {"cmd": lean_code, "env": self._env_counter}
            cmd_json = json.dumps(cmd) + "\n\n"

            try:
                assert self._process and self._process.stdin and self._process.stdout
                self._process.stdin.write(cmd_json.encode())
                await self._process.stdin.drain()

                response_text = await asyncio.wait_for(
                    self._read_response(), timeout=timeout
                )
                elapsed = time.monotonic() - start_time

                response = json.loads(response_text)
                self._env_counter = response.get("env", self._env_counter) + 1

                return parse_repl_response(response, lean_code=lean_code, elapsed=elapsed)

            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start_time
                # Restart the REPL after a timeout
                await self.stop()
                return VerificationResult(
                    success=False,
                    errors=[],
                    lean_code=lean_code,
                    elapsed_seconds=elapsed,
                )
            except (json.JSONDecodeError, OSError) as e:
                elapsed = time.monotonic() - start_time
                await self.stop()
                return VerificationResult(
                    success=False,
                    errors=[],
                    lean_code=lean_code,
                    elapsed_seconds=elapsed,
                )

    async def _read_response(self) -> str:
        """Read a complete JSON response from the REPL stdout.

        The REPL outputs a JSON object followed by a blank line.
        """
        assert self._process and self._process.stdout
        lines: list[str] = []
        while True:
            line = await self._process.stdout.readline()
            if not line:
                break
            decoded = line.decode().rstrip("\n")
            if decoded == "" and lines:
                break
            if decoded:
                lines.append(decoded)
        return "\n".join(lines)

    async def __aenter__(self) -> LeanVerifier:
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()
