"""Shared converter abstractions and path helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pyautobox.exceptions import FileConflictError

FORMAT_ALIASES = {"jpeg": "jpg", "yml": "yaml", "markdown": "md", "htm": "html"}


def normalize_format(value: str) -> str:
    """Normalize an extension or format name for registry lookups."""
    cleaned = value.lower().strip().lstrip(".")
    return FORMAT_ALIASES.get(cleaned, cleaned)


def format_from_path(path: Path) -> str:
    """Return normalized format inferred from a path suffix."""
    return normalize_format(path.suffix)


def unique_output_path(path: Path, overwrite: bool = False) -> Path:
    """Return a non-conflicting output path, or the original path when allowed."""
    if overwrite or not path.exists():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise FileConflictError(f"无法为 {path} 找到可用的输出文件名。")


class Converter(ABC):
    """Interface implemented by all file converters."""

    category: str
    source_formats: frozenset[str]
    target_formats: frozenset[str]
    allow_identity = False

    def pairs(self) -> set[tuple[str, str]]:
        """Return every supported source/target pair."""
        return {
            (source, target)
            for source in self.source_formats
            for target in self.target_formats
            if self.allow_identity or source != target
        }

    @abstractmethod
    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Convert one file and return the resulting path."""

