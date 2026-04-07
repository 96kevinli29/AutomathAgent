"""High-quality data pool CRUD operations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from automath.data.schema import DataPoolEntry, PoolStats


class DataPool:
    """CRUD operations on the high-quality data pool.

    Stores entries as JSONL files with versioned snapshots.
    """

    def __init__(self, pool_dir: str | Path):
        self.pool_dir = Path(pool_dir).resolve()
        self.pool_dir.mkdir(parents=True, exist_ok=True)
        self._pool_file = self.pool_dir / "pool.jsonl"
        self._entries: dict[str, DataPoolEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load entries from the JSONL file."""
        if not self._pool_file.exists():
            return
        for line in self._pool_file.read_text().strip().splitlines():
            if line.strip():
                entry = DataPoolEntry.model_validate_json(line)
                self._entries[entry.id] = entry

    def _save(self) -> None:
        """Persist all entries to the JSONL file."""
        with open(self._pool_file, "w") as f:
            for entry in self._entries.values():
                f.write(entry.model_dump_json() + "\n")

    def add(self, entry: DataPoolEntry) -> None:
        """Add an entry to the pool."""
        entry.updated_at = datetime.now(timezone.utc)
        self._entries[entry.id] = entry
        # Append to file
        with open(self._pool_file, "a") as f:
            f.write(entry.model_dump_json() + "\n")

    def get(self, entry_id: str) -> DataPoolEntry | None:
        return self._entries.get(entry_id)

    def query(
        self,
        source: str | None = None,
        difficulty: str | None = None,
        model: str | None = None,
        dual_verified_only: bool = False,
    ) -> list[DataPoolEntry]:
        """Query entries with optional filters."""
        results = list(self._entries.values())
        if source:
            results = [e for e in results if e.problem_source == source]
        if difficulty:
            results = [e for e in results if e.difficulty == difficulty]
        if model:
            results = [e for e in results if e.model_source == model]
        if dual_verified_only:
            results = [
                e for e in results
                if e.second_verification and e.second_verification.success
            ]
        return results

    def stats(self) -> PoolStats:
        """Compute pool statistics."""
        entries = list(self._entries.values())
        if not entries:
            return PoolStats()

        dual_verified = [
            e for e in entries
            if e.second_verification and e.second_verification.success
        ]

        by_source: dict[str, int] = {}
        by_model: dict[str, int] = {}
        by_difficulty: dict[str, int] = {}
        total_repairs = 0

        for e in entries:
            by_source[e.problem_source] = by_source.get(e.problem_source, 0) + 1
            by_model[e.model_source] = by_model.get(e.model_source, 0) + 1
            by_difficulty[e.difficulty] = by_difficulty.get(e.difficulty, 0) + 1
            total_repairs += e.repair_iterations_first

        return PoolStats(
            total_entries=len(entries),
            dual_verified=len(dual_verified),
            by_source=by_source,
            by_model=by_model,
            by_difficulty=by_difficulty,
            avg_repair_iterations=total_repairs / len(entries) if entries else 0,
            dual_pass_rate=len(dual_verified) / len(entries) if entries else 0,
        )

    def snapshot(self, version_tag: str) -> Path:
        """Create a versioned snapshot of the current pool."""
        snapshot_dir = self.pool_dir / version_tag
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._pool_file, snapshot_dir / "pool.jsonl")

        metadata = {
            "version": version_tag,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "entry_count": len(self._entries),
            "stats": self.stats().model_dump(),
        }
        (snapshot_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
        return snapshot_dir

    def export_jsonl(self, path: Path, filter_fn: Callable | None = None) -> int:
        """Export entries to a JSONL file."""
        entries = list(self._entries.values())
        if filter_fn:
            entries = [e for e in entries if filter_fn(e)]
        with open(path, "w") as f:
            for e in entries:
                f.write(e.model_dump_json() + "\n")
        return len(entries)

    @property
    def size(self) -> int:
        return len(self._entries)
