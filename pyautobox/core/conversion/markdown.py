"""Markdown document conversion."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import markdown
from bs4 import BeautifulSoup

from pyautobox.core.conversion.base import Converter
from pyautobox.exceptions import InvalidFileError

DOCUMENT_CSS = """
body{max-width:860px;margin:3rem auto;padding:0 1.25rem;color:#20242b;
font:17px/1.65 system-ui,sans-serif}
pre{overflow:auto;padding:1rem;border-radius:.75rem;background:#f4f5f7}
code{font-family:ui-monospace,monospace}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #d8dce2;padding:.55rem;text-align:left}
blockquote{margin-left:0;padding-left:1rem;border-left:4px solid #6d5dfc;color:#5c6370}
img{max-width:100%}
""".strip()


class MarkdownConverter(Converter):
    """Render Markdown as a complete or fragment HTML document."""

    category = "Documents"
    source_formats = frozenset({"md"})
    target_formats = frozenset({"html"})

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Render Markdown with tables and fenced code support."""
        options = options or {}
        try:
            source = input_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidFileError(f"无法以 UTF-8 Markdown 读取 {input_path.name}。") from exc
        body = markdown.markdown(escape(source), extensions=["extra", "sane_lists"])
        body = self._safe_links(body)
        if options.get("standalone", True):
            title = escape(input_path.stem)
            body = (
                "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
                f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{title}</title><style>{DOCUMENT_CSS}</style></head>"
                f"<body>{body}</body></html>\n"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(body, encoding="utf-8")
        return output_path

    @staticmethod
    def _safe_links(body: str) -> str:
        """Remove active URL schemes from Markdown-generated links and images."""
        soup = BeautifulSoup(body, "html.parser")
        for element, attribute, schemes in (
            ("a", "href", {"", "http", "https", "mailto"}),
            ("img", "src", {"", "http", "https"}),
        ):
            for node in soup.find_all(element):
                value = node.get(attribute)
                if value and urlparse(str(value)).scheme.lower() not in schemes:
                    del node[attribute]
        return str(soup)

