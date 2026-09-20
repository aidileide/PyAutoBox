"""Upload APIs that delegate all business logic to ``pyautobox.core``."""

from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from pyautobox.config import DEFAULT_IMAGE_QUALITY, MAX_UPLOAD_MB
from pyautobox.core.excel_tools import EXCEL_SUFFIXES, merge_excel_files
from pyautobox.core.image_tools import IMAGE_SUFFIXES, compress_image
from pyautobox.core.markdown_tools import markdown_to_pdf
from pyautobox.core.pdf_tools import merge_pdfs
from pyautobox.exceptions import InvalidFileError, UnsupportedFormatError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredUpload:
    """A safely stored upload and its display name."""

    path: Path
    original_name: str


def _job_directory() -> Path:
    return Path(tempfile.mkdtemp(prefix="pyautobox-"))


def _safe_filename(raw_name: str | None) -> str:
    normalized = (raw_name or "upload").replace("\\", "/")
    name = Path(normalized).name
    if name in {"", ".", ".."}:
        raise InvalidFileError("The uploaded file name is invalid.")
    return name


async def _store_upload(
    upload: UploadFile,
    directory: Path,
    allowed_suffixes: set[str],
) -> StoredUpload:
    destination: Path | None = None
    try:
        name = _safe_filename(upload.filename)
        suffix = Path(name).suffix.lower()
        if suffix not in allowed_suffixes:
            allowed = ", ".join(sorted(allowed_suffixes))
            raise UnsupportedFormatError(
                f"{name} has an unsupported format. Allowed: {allowed}"
            )

        destination = directory / f"{uuid.uuid4().hex}{suffix}"
        max_bytes = MAX_UPLOAD_MB * 1024 * 1024
        total = 0
        with destination.open("wb") as handle:
            while chunk := await upload.read(CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise InvalidFileError(
                        f"{name} exceeds the {MAX_UPLOAD_MB} MB per-file upload limit."
                    )
                handle.write(chunk)
    except Exception:
        if destination is not None:
            destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return StoredUpload(path=destination, original_name=name)


async def _store_many(
    uploads: list[UploadFile],
    directory: Path,
    allowed_suffixes: set[str],
) -> list[StoredUpload]:
    if not uploads:
        raise InvalidFileError("Upload at least one file.")
    stored: list[StoredUpload] = []
    for upload in uploads:
        stored.append(await _store_upload(upload, directory, allowed_suffixes))
    return stored


def _download(
    path: Path,
    filename: str,
    job_directory: Path,
    *,
    media_type: str,
    headers: dict[str, str] | None = None,
) -> FileResponse:
    response_headers = {"X-PyAutoBox-Success": "true", **(headers or {})}
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type,
        headers=response_headers,
        background=BackgroundTask(shutil.rmtree, job_directory, ignore_errors=True),
    )


@router.post("/pdf/merge")
async def api_pdf_merge(files: Annotated[list[UploadFile], File()]) -> FileResponse:
    """Merge uploaded PDFs in multipart order."""
    job = _job_directory()
    try:
        stored = await _store_many(files, job, {".pdf"})
        output = job / "merged.pdf"
        merge_pdfs([item.path for item in stored], output)
        return _download(output, "merged.pdf", job, media_type="application/pdf")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


@router.post("/excel/merge")
async def api_excel_merge(
    files: Annotated[list[UploadFile], File()],
    sheet: Annotated[str, Form()] = "",
    include_source: Annotated[bool, Form()] = True,
) -> FileResponse:
    """Merge uploaded Excel files by rows."""
    job = _job_directory()
    try:
        stored = await _store_many(files, job, EXCEL_SUFFIXES)
        output = job / "merged.xlsx"
        merge_excel_files(
            [item.path for item in stored],
            output,
            sheet_name=sheet.strip() or 0,
            include_source=include_source,
            source_names=[item.original_name for item in stored],
        )
        return _download(
            output,
            "merged.xlsx",
            job,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


def _unique_output_name(name: str, used: set[str]) -> str:
    source = Path(name)
    candidate = f"{source.stem}_compressed{source.suffix.lower()}"
    counter = 1
    while candidate.casefold() in used:
        candidate = f"{source.stem}_compressed_{counter}{source.suffix.lower()}"
        counter += 1
    used.add(candidate.casefold())
    return candidate


@router.post("/image/compress")
async def api_image_compress(
    files: Annotated[list[UploadFile], File()],
    quality: Annotated[int, Form()] = DEFAULT_IMAGE_QUALITY,
    max_width: Annotated[int | None, Form()] = None,
) -> FileResponse:
    """Compress one image or return multiple compressed images as a ZIP."""
    job = _job_directory()
    try:
        stored = await _store_many(files, job, IMAGE_SUFFIXES)
        output_dir = job / "output"
        output_dir.mkdir()
        used_names: set[str] = set()
        results = []
        for item in stored:
            output_name = _unique_output_name(item.original_name, used_names)
            results.append(
                compress_image(
                    item.path,
                    output_dir / output_name,
                    quality=quality,
                    max_width=max_width,
                )
            )

        original_size = sum(result.original_size for result in results)
        compressed_size = sum(result.compressed_size for result in results)
        saved_percent = 0 if not original_size else (1 - compressed_size / original_size) * 100
        headers = {
            "X-Original-Size": str(original_size),
            "X-Compressed-Size": str(compressed_size),
            "X-Saved-Percent": f"{saved_percent:.1f}",
        }
        if len(results) == 1:
            result = results[0]
            return _download(
                result.output_path,
                result.output_path.name,
                job,
                media_type="application/octet-stream",
                headers=headers,
            )

        archive = job / "compressed_images.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for result in results:
                bundle.write(result.output_path, arcname=result.output_path.name)
        return _download(
            archive,
            "compressed_images.zip",
            job,
            media_type="application/zip",
            headers=headers,
        )
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


@router.post("/md2pdf")
async def api_md2pdf(
    markdown_file: Annotated[UploadFile | None, File()] = None,
    markdown_text: Annotated[str, Form()] = "",
) -> FileResponse:
    """Convert an uploaded Markdown file or pasted text to PDF."""
    job = _job_directory()
    try:
        source: Path | None = None
        if markdown_file is not None and markdown_file.filename:
            stored = await _store_upload(markdown_file, job, {".md", ".markdown"})
            source = stored.path
        if source is None and not markdown_text.strip():
            raise InvalidFileError("Upload a Markdown file or paste Markdown text.")
        output = job / "converted.pdf"
        markdown_to_pdf(
            source,
            output,
            markdown_text=None if source else markdown_text,
        )
        return _download(output, "converted.pdf", job, media_type="application/pdf")
    except Exception:
        shutil.rmtree(job, ignore_errors=True)
        raise


def json_error(error: str, detail: str) -> dict[str, str | bool]:
    """Return the stable error envelope used by every API failure."""
    return {"success": False, "error": error, "detail": detail}
