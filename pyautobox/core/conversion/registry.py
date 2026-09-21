"""Extensible converter registry shared by CLI and Web."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from pyautobox.core.conversion.base import Converter, format_from_path, normalize_format
from pyautobox.exceptions import ConversionNotSupportedError, UnsupportedFormatError


class ConverterRegistry:
    """Map normalized source/target pairs to converter instances."""

    def __init__(self) -> None:
        self._pairs: dict[tuple[str, str], Converter] = {}

    def register(self, converter: Converter) -> None:
        """Register every pair declared by a converter."""
        for pair in converter.pairs():
            if pair in self._pairs:
                raise ValueError(f"Converter pair already registered: {pair[0]} -> {pair[1]}")
            self._pairs[pair] = converter

    def supports(self, source: str, target: str) -> bool:
        """Return whether one conversion pair is available."""
        return (normalize_format(source), normalize_format(target)) in self._pairs

    def get_converter(self, source: str, target: str) -> Converter:
        """Return converter for a pair or raise a user-facing error."""
        pair = (normalize_format(source), normalize_format(target))
        try:
            return self._pairs[pair]
        except KeyError as exc:
            raise ConversionNotSupportedError(
                f"Conversion not supported: .{pair[0]} → {pair[1]}. Run 'autobox convert formats'."
            ) from exc

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Dispatch a file conversion using path suffixes."""
        source = format_from_path(input_path)
        target = format_from_path(output_path)
        if not source:
            raise UnsupportedFormatError(f"Cannot detect format for {input_path.name}.")
        return self.get_converter(source, target).convert(input_path, output_path, options)

    def list_formats(self) -> dict[str, dict[str, list[str]]]:
        """Return category/source/targets derived only from registrations."""
        grouped: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for (source, target), converter in self._pairs.items():
            grouped[converter.category][source].add(target)
        return {
            category: {
                source: sorted(targets) for source, targets in sorted(sources.items())
            }
            for category, sources in sorted(grouped.items())
        }


def create_default_registry() -> ConverterRegistry:
    """Create a registry containing all stable 0.1 converters."""
    from pyautobox.core.conversion.image import ImageConverter
    from pyautobox.core.conversion.markdown import MarkdownConverter
    from pyautobox.core.conversion.structured_data import StructuredDataConverter
    from pyautobox.core.conversion.table import TableConverter
    from pyautobox.core.conversion.text import TextConverter

    result = ConverterRegistry()
    for converter in (
        ImageConverter(),
        TableConverter(),
        StructuredDataConverter(),
        MarkdownConverter(),
        TextConverter(),
    ):
        result.register(converter)
    return result


registry = create_default_registry()

