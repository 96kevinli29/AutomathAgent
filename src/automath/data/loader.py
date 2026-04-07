"""Dataset loaders for miniF2F, ProofNet, and LeanWorkbook."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from automath.data.schema import MathProblem


class DatasetLoader(ABC):
    @abstractmethod
    def load(self) -> list[MathProblem]:
        """Load problems from the dataset."""


class MiniF2FLoader(DatasetLoader):
    """Load miniF2F-lean4 problems from a local JSONL file.

    Expected format per line:
    {"id": "...", "statement": "...", "lean_statement": "...", "difficulty": "..."}
    """

    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)

    def load(self) -> list[MathProblem]:
        problems = []
        for line in self.data_path.read_text().strip().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            problems.append(
                MathProblem(
                    id=data.get("id", ""),
                    source="miniF2F",
                    nl_statement=data.get("statement", data.get("nl_statement", "")),
                    formal_statement=data.get("lean_statement", data.get("formal_statement")),
                    formal_proof=data.get("lean_proof", data.get("formal_proof")),
                    difficulty=data.get("difficulty", "unknown"),
                    tags=data.get("tags", []),
                )
            )
        return problems


class ProofNetLoader(DatasetLoader):
    """Load ProofNet problems from a JSON file."""

    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)

    def load(self) -> list[MathProblem]:
        data = json.loads(self.data_path.read_text())
        problems = []
        items = data if isinstance(data, list) else data.get("problems", [])
        for item in items:
            problems.append(
                MathProblem(
                    id=item.get("id", ""),
                    source="ProofNet",
                    nl_statement=item.get("nl_statement", ""),
                    formal_statement=item.get("formal_statement"),
                    formal_proof=item.get("formal_proof"),
                    difficulty=item.get("difficulty", "unknown"),
                    tags=item.get("tags", []),
                )
            )
        return problems


class LeanWorkbookLoader(DatasetLoader):
    """Load LeanWorkbook problems from a JSONL file."""

    def __init__(self, data_path: str | Path):
        self.data_path = Path(data_path)

    def load(self) -> list[MathProblem]:
        problems = []
        for line in self.data_path.read_text().strip().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            problems.append(
                MathProblem(
                    id=data.get("id", ""),
                    source="LeanWorkbook",
                    nl_statement=data.get("nl_statement", data.get("statement", "")),
                    formal_statement=data.get("formal_statement"),
                    formal_proof=data.get("formal_proof"),
                    difficulty=data.get("difficulty", "unknown"),
                    tags=data.get("tags", []),
                )
            )
        return problems


def get_loader(source: str, data_path: str | Path) -> DatasetLoader:
    """Factory function to get the appropriate loader."""
    loaders = {
        "miniF2F": MiniF2FLoader,
        "ProofNet": ProofNetLoader,
        "LeanWorkbook": LeanWorkbookLoader,
    }
    loader_cls = loaders.get(source)
    if loader_cls is None:
        raise ValueError(f"Unknown dataset source: {source}. Choose from {list(loaders.keys())}")
    return loader_cls(data_path)
