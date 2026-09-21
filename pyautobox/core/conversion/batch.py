"""Batch conversion orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyautobox.core.conversion.base import format_from_path, normalize_format, unique_output_path
from pyautobox.core.conversion.registry import ConverterRegistry, registry
from pyautobox.exceptions import InvalidFileError


def batch_convert(
    input_dir: Path,
    source_format: str,
    target_format: str,
    output_dir: Path | None = None,
    *,
    recursive: bool = False,
    overwrite: bool = False,
    options: dict[str, Any] | None = None,
    converter_registry: ConverterRegistry = registry,
) -> list[Path]:
    """Convert matching files under a directory and return output paths."""
    if not input_dir.is_dir():
        raise InvalidFileError(f"找不到输入目录：{input_dir}")
    source = normalize_format(source_format)
    target = normalize_format(target_format)
    converter_registry.get_converter(source, target)
    destination = output_dir or input_dir / "output"
    pattern = "**/*" if recursive else "*"
    inputs = sorted(
        path
        for path in input_dir.glob(pattern)
        if path.is_file() and format_from_path(path) == source
    )
    outputs: list[Path] = []
    for input_path in inputs:
        relative_parent = input_path.parent.relative_to(input_dir) if recursive else Path()
        desired = destination / relative_parent / f"{input_path.stem}.{target}"
        output_path = unique_output_path(desired, overwrite=overwrite)
        outputs.append(converter_registry.convert(input_path, output_path, options))
    return outputs

