"""High-level operations shared by command and HTTP interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyautobox.core.conversion.base import format_from_path, normalize_format, unique_output_path
from pyautobox.core.conversion.registry import ConverterRegistry, registry
from pyautobox.exceptions import InvalidFileError


def output_path_for(
    input_path: Path,
    target_format: str,
    output: Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    """Resolve a requested output file without silently overwriting existing data."""
    target = normalize_format(target_format)
    if output and (output.is_dir() or not output.suffix):
        desired = output / f"{input_path.stem}.{target}"
    else:
        desired = output or input_path.with_suffix(f".{target}")
    return unique_output_path(desired, overwrite=overwrite)


def convert_one(
    input_path: Path,
    target_format: str,
    output: Path | None = None,
    *,
    overwrite: bool = False,
    options: dict[str, Any] | None = None,
    converter_registry: ConverterRegistry = registry,
) -> Path:
    """Validate paths, resolve output, and dispatch one conversion."""
    if not input_path.is_file():
        raise InvalidFileError(f"找不到输入文件：{input_path}")
    source = format_from_path(input_path)
    target = normalize_format(target_format)
    converter_registry.get_converter(source, target)
    output_path = output_path_for(input_path, target, output, overwrite=overwrite)
    return converter_registry.convert(input_path, output_path, options)


def convert_directory(
    input_dir: Path,
    target_format: str,
    category: str,
    output_dir: Path | None = None,
    *,
    overwrite: bool = False,
    options: dict[str, Any] | None = None,
    converter_registry: ConverterRegistry = registry,
) -> list[Path]:
    """Convert direct child files supported by a category to one target format."""
    if not input_dir.is_dir():
        raise InvalidFileError(f"找不到输入目录：{input_dir}")
    target = normalize_format(target_format)
    destination = output_dir or input_dir / "output"
    supported = converter_registry.list_formats().get(category, {})
    inputs = [
        path
        for path in sorted(input_dir.iterdir())
        if path.is_file()
        and format_from_path(path) in supported
        and target in supported[format_from_path(path)]
    ]
    return [
        convert_one(
            path,
            target,
            destination,
            overwrite=overwrite,
            options=options,
            converter_registry=converter_registry,
        )
        for path in inputs
    ]

