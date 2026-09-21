"""HTML and Markdown plain-text extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import markdown
from bs4 import BeautifulSoup

from pyautobox.core.conversion.base import Converter, format_from_path
from pyautobox.exceptions import InvalidFileError


class TextConverter(Converter):
    """Extract readable text while removing active HTML content."""

    category = "Documents"
    source_formats = frozenset({"html", "md"})
    target_formats = frozenset({"txt"})

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Convert HTML or Markdown to paragraph-oriented plain text."""
        del options
        try:
            source = input_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidFileError(f"无法以 UTF-8 文本读取 {input_path.name}。") from exc
        html = (
            markdown.markdown(source, extensions=["extra"])
            if format_from_path(input_path) == "md"
            else source
        )
        soup = BeautifulSoup(html, "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", text).strip() + "\n"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return output_path

