"""PDF utilities."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pyautobox.exceptions import (
    FileConflictError,
    InvalidFileError,
    PyAutoBoxError,
    ToolExecutionError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)


def merge_pdfs(
    input_files: list[Path],
    output_file: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Merge PDF files in order and return the created output path."""
    started = time.perf_counter()
    files = [Path(path).expanduser() for path in input_files]
    output = Path(output_file).expanduser()
    if not files:
        raise InvalidFileError("At least one PDF file is required.")

    resolved_output = output.resolve(strict=False)
    for path in files:
        if not path.is_file():
            raise InvalidFileError(f"{path} does not exist or is not a file.")
        if path.suffix.lower() != ".pdf":
            raise UnsupportedFormatError(f"{path.name} is not a PDF file.")
        if path.resolve() == resolved_output:
            raise FileConflictError("The output file cannot also be an input file.")

    if output.exists() and not overwrite:
        raise FileConflictError(f"{output} already exists.")

    output.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    try:
        for path in files:
            reader = PdfReader(path)
            for page in reader.pages:
                writer.add_page(page)
        with output.open("wb") as handle:
            writer.write(handle)
    except PyAutoBoxError:
        raise
    except Exception as exc:
        if output.exists():
            output.unlink(missing_ok=True)
        raise ToolExecutionError(f"Could not merge PDF files: {exc}") from exc

    logger.info(
        "tool=pdf_merge inputs=%d result=success duration_ms=%d",
        len(files),
        round((time.perf_counter() - started) * 1000),
    )
    return output
