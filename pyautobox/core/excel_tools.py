"""Excel utilities."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from pyautobox.exceptions import (
    FileConflictError,
    InvalidFileError,
    ToolExecutionError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)
EXCEL_SUFFIXES = {".xlsx", ".xls"}


def merge_excel_files(
    input_files: list[Path],
    output_file: Path,
    *,
    sheet_name: str | int = 0,
    include_source: bool = True,
    source_names: list[str] | None = None,
    overwrite: bool = False,
) -> Path:
    """Vertically merge Excel worksheets using the union of their columns."""
    started = time.perf_counter()
    files = [Path(path).expanduser() for path in input_files]
    output = Path(output_file).expanduser()
    if not files:
        raise InvalidFileError("At least one Excel file is required.")
    if source_names is not None and len(source_names) != len(files):
        raise InvalidFileError("Source name count must match the number of Excel files.")

    resolved_output = output.resolve(strict=False)
    for path in files:
        if not path.is_file():
            raise InvalidFileError(f"{path} does not exist or is not a file.")
        if path.suffix.lower() not in EXCEL_SUFFIXES:
            raise UnsupportedFormatError(f"{path.name} is not an .xlsx or .xls file.")
        if path.resolve() == resolved_output:
            raise FileConflictError("The output file cannot also be an input file.")

    if output.suffix.lower() != ".xlsx":
        raise UnsupportedFormatError("The merged output must use the .xlsx extension.")
    if output.exists() and not overwrite:
        raise FileConflictError(f"{output} already exists.")

    frames: list[pd.DataFrame] = []
    try:
        for index, path in enumerate(files):
            frame = pd.read_excel(path, sheet_name=sheet_name)
            if include_source:
                frame["_source_file"] = source_names[index] if source_names else path.name
            frames.append(frame)
        merged = pd.concat(frames, ignore_index=True, sort=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        merged.to_excel(output, index=False, engine="openpyxl")
    except ValueError as exc:
        output.unlink(missing_ok=True)
        raise InvalidFileError(f"Could not read the requested worksheet: {exc}") from exc
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise ToolExecutionError(f"Could not merge Excel files: {exc}") from exc

    logger.info(
        "tool=excel_merge inputs=%d result=success duration_ms=%d",
        len(files),
        round((time.perf_counter() - started) * 1000),
    )
    return output
