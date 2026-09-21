"""HTTP endpoints for the merged file-conversion engine."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse

from pyautobox import __version__
from pyautobox.core.conversion.audio import AUDIO_FORMATS, read_audio_metadata
from pyautobox.core.conversion.base import normalize_format
from pyautobox.core.conversion.registry import registry
from pyautobox.core.conversion.table import TableConverter
from pyautobox.exceptions import InvalidFileError
from pyautobox.web.routes.api import _download, _job_directory, _store_upload

router = APIRouter(prefix="/api")
CONVERT_FORMATS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff",
    ".csv", ".xlsx", ".json", ".yaml", ".yml",
    ".md", ".markdown", ".html", ".htm",
}
AUDIO_SUFFIXES = {f".{item}" for item in AUDIO_FORMATS}


def _options(
    quality: int,
    max_width: int | None,
    max_height: int | None,
    sheet: str | None,
) -> dict[str, Any]:
    return {
        "quality": quality,
        "max_width": max_width,
        "max_height": max_height,
        "sheet": sheet,
        "pretty": True,
        "standalone": True,
    }


@router.get("/formats")
async def formats() -> dict[str, Any]:
    """Return conversion pairs used to populate the browser UI."""
    return {"success": True, "formats": registry.list_formats(), "audio": sorted(AUDIO_FORMATS)}


@router.get("/health")
async def health() -> dict[str, str | bool]:
    """Report service health and package version."""
    return {"success": True, "version": __version__}


@router.post("/convert")
async def convert_file(
    file: Annotated[UploadFile, File()],
    target: Annotated[str, Form()],
    quality: Annotated[int, Form(ge=1, le=100)] = 85,
    max_width: Annotated[int | None, Form(ge=1)] = None,
    max_height: Annotated[int | None, Form(ge=1)] = None,
    sheet: Annotated[str | None, Form()] = None,
) -> FileResponse:
    """Convert one uploaded file and remove temporary data after download."""
    job = _job_directory()
    try:
        stored = await _store_upload(file, job, CONVERT_FORMATS)
        normalized_target = normalize_format(target)
        output = job / f"{Path(stored.original_name).stem}.{normalized_target}"
        registry.convert(stored.path, output, _options(quality, max_width, max_height, sheet))
        return _download(output, output.name, job, media_type="application/octet-stream")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


@router.post("/batch")
async def convert_batch(
    files: Annotated[list[UploadFile], File()],
    target: Annotated[str, Form()],
    quality: Annotated[int, Form(ge=1, le=100)] = 85,
) -> FileResponse:
    """Convert up to 100 uploads and return a ZIP archive."""
    if not files or len(files) > 100:
        raise InvalidFileError("请选择 1 至 100 个文件。")
    job = _job_directory()
    outputs = job / "outputs"
    outputs.mkdir()
    try:
        normalized_target = normalize_format(target)
        used: set[str] = set()
        for upload in files:
            stored = await _store_upload(upload, job, CONVERT_FORMATS)
            base = f"{Path(stored.original_name).stem}.{normalized_target}"
            name = base
            index = 1
            while name.casefold() in used:
                name = f"{Path(base).stem}_{index}.{normalized_target}"
                index += 1
            used.add(name.casefold())
            registry.convert(stored.path, outputs / name, {"quality": quality})
        archive = job / "pyautobox-results.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for output in sorted(outputs.iterdir()):
                bundle.write(output, output.name)
        return _download(archive, archive.name, job, media_type="application/zip")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


@router.post("/table/preview")
async def table_preview(
    file: Annotated[UploadFile, File()],
    sheet: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """Return table dimensions, columns and worksheet names."""
    job = _job_directory()
    try:
        stored = await _store_upload(file, job, {".csv", ".xlsx", ".json"})
        converter = TableConverter()
        frame = converter.read(stored.path, sheet)
        sheets: list[str] = []
        if stored.path.suffix == ".xlsx":
            import pandas as pd

            sheets = pd.ExcelFile(stored.path, engine="openpyxl").sheet_names
        return {
            "success": True,
            "filename": stored.original_name,
            "rows": int(frame.shape[0]),
            "columns": int(frame.shape[1]),
            "column_names": [str(column) for column in frame.columns],
            "sheets": sheets,
        }
    finally:
        shutil.rmtree(job, ignore_errors=True)


@router.post("/audio/metadata")
async def audio_metadata(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    """Read audio metadata and immediately delete the upload."""
    job = _job_directory()
    try:
        stored = await _store_upload(file, job, AUDIO_SUFFIXES)
        return {"success": True, "metadata": read_audio_metadata(stored.path)}
    finally:
        shutil.rmtree(job, ignore_errors=True)
