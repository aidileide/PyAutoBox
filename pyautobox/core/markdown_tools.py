"""Small, dependency-light Markdown-to-PDF renderer."""

from __future__ import annotations

import html
import logging
import re
import time
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

from pyautobox.exceptions import (
    FileConflictError,
    InvalidFileError,
    ToolExecutionError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)


def _font_name() -> str:
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        logger.warning("A Chinese PDF font was unavailable; falling back to Helvetica.")
        return "Helvetica"


def _inline_markup(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<link href="\2">\1</link>', escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<i>\1</i>", escaped)
    return escaped


def _styles() -> dict[str, ParagraphStyle]:
    font = _font_name()
    sample = getSampleStyleSheet()
    return {
        "body": ParagraphStyle(
            "AutoBoxBody",
            parent=sample["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=16,
            spaceAfter=7,
            textColor=colors.HexColor("#1f2937"),
        ),
        "h1": ParagraphStyle(
            "AutoBoxH1",
            parent=sample["Heading1"],
            fontName=font,
            fontSize=22,
            leading=28,
            spaceAfter=12,
            textColor=colors.HexColor("#111827"),
        ),
        "h2": ParagraphStyle(
            "AutoBoxH2",
            parent=sample["Heading2"],
            fontName=font,
            fontSize=17,
            leading=22,
            spaceBefore=8,
            spaceAfter=8,
            textColor=colors.HexColor("#111827"),
        ),
        "h3": ParagraphStyle(
            "AutoBoxH3",
            parent=sample["Heading3"],
            fontName=font,
            fontSize=14,
            leading=19,
            spaceBefore=6,
            spaceAfter=6,
        ),
        "quote": ParagraphStyle(
            "AutoBoxQuote",
            parent=sample["BodyText"],
            fontName=font,
            fontSize=10.5,
            leading=16,
            leftIndent=12,
            borderColor=colors.HexColor("#9ca3af"),
            borderWidth=1,
            borderPadding=6,
            textColor=colors.HexColor("#4b5563"),
        ),
        "code": ParagraphStyle(
            "AutoBoxCode",
            parent=sample["Code"],
            fontName=font,
            fontSize=8.5,
            leading=12,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#d1d5db"),
            borderWidth=0.5,
            borderPadding=7,
            backColor=colors.HexColor("#f3f4f6"),
        ),
    }


def _build_story(markdown_text: str) -> list[object]:
    styles = _styles()
    story: list[object] = []
    lines = markdown_text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            story.append(Preformatted("\n".join(code_lines), styles["code"]))
            story.append(Spacer(1, 3 * mm))
        elif match := re.match(r"^(#{1,3})\s+(.+)$", stripped):
            level = len(match.group(1))
            story.append(Paragraph(_inline_markup(match.group(2)), styles[f"h{level}"]))
        elif stripped.startswith(">"):
            story.append(Paragraph(_inline_markup(stripped.lstrip("> ")), styles["quote"]))
        elif re.match(r"^[-*+]\s+", stripped):
            items: list[ListItem] = []
            while index < len(lines) and re.match(r"^\s*[-*+]\s+", lines[index]):
                item_text = re.sub(r"^\s*[-*+]\s+", "", lines[index])
                items.append(ListItem(Paragraph(_inline_markup(item_text), styles["body"])))
                index += 1
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=18))
            index -= 1
        elif re.match(r"^\d+[.)]\s+", stripped):
            numbered: list[ListItem] = []
            while index < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[index]):
                item_text = re.sub(r"^\s*\d+[.)]\s+", "", lines[index])
                numbered.append(ListItem(Paragraph(_inline_markup(item_text), styles["body"])))
                index += 1
            story.append(ListFlowable(numbered, bulletType="1", leftIndent=18))
            index -= 1
        elif stripped:
            paragraphs = [stripped]
            while index + 1 < len(lines) and lines[index + 1].strip():
                next_line = lines[index + 1].strip()
                if re.match(r"^(#{1,3})\s+|^```|^>|^[-*+]\s+|^\d+[.)]\s+", next_line):
                    break
                index += 1
                paragraphs.append(next_line)
            story.append(Paragraph(_inline_markup(" ".join(paragraphs)), styles["body"]))
        else:
            story.append(Spacer(1, 2 * mm))
        index += 1
    return story


def markdown_to_pdf(
    input_file: Path | None,
    output_file: Path,
    *,
    markdown_text: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Render a Markdown file or supplied Markdown text to a portable PDF."""
    started = time.perf_counter()
    if input_file is None and markdown_text is None:
        raise InvalidFileError("Provide a Markdown file or Markdown text.")
    if input_file is not None:
        source = Path(input_file).expanduser()
        if not source.is_file():
            raise InvalidFileError(f"{source} does not exist or is not a file.")
        if source.suffix.lower() not in {".md", ".markdown"}:
            raise UnsupportedFormatError(f"{source.name} is not a Markdown file.")
        try:
            markdown_text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidFileError("Markdown files must use UTF-8 encoding.") from exc

    output = Path(output_file).expanduser()
    if output.suffix.lower() != ".pdf":
        raise UnsupportedFormatError("The output file must use the .pdf extension.")
    if output.exists() and not overwrite:
        raise FileConflictError(f"{output} already exists.")
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        document = SimpleDocTemplate(
            str(output),
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="PyAutoBox Markdown export",
        )
        document.build(_build_story(markdown_text or ""))
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise ToolExecutionError(f"Could not render Markdown PDF: {exc}") from exc

    logger.info(
        "tool=md2pdf inputs=1 result=success duration_ms=%d",
        round((time.perf_counter() - started) * 1000),
    )
    return output
