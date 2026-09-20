"""Image compression utilities."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from pyautobox.config import DEFAULT_IMAGE_QUALITY
from pyautobox.exceptions import (
    FileConflictError,
    InvalidFileError,
    ToolExecutionError,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True, slots=True)
class ImageCompressionResult:
    """Metadata describing a completed image compression."""

    output_path: Path
    original_size: int
    compressed_size: int
    original_width: int
    output_width: int

    @property
    def saved_percent(self) -> float:
        """Return the percentage of bytes saved; negative means the file grew."""
        if self.original_size == 0:
            return 0.0
        return (1 - self.compressed_size / self.original_size) * 100


def default_compressed_path(input_file: Path) -> Path:
    """Return the conventional output path for one compressed image."""
    path = Path(input_file)
    return path.with_name(f"{path.stem}_compressed{path.suffix.lower()}")


def compress_image(
    input_file: Path,
    output_file: Path | None = None,
    *,
    quality: int = DEFAULT_IMAGE_QUALITY,
    max_width: int | None = None,
    overwrite: bool = False,
) -> ImageCompressionResult:
    """Compress one image while preserving its source format and transparency."""
    started = time.perf_counter()
    source = Path(input_file).expanduser()
    if not source.is_file():
        raise InvalidFileError(f"{source} does not exist or is not a file.")
    suffix = source.suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise UnsupportedFormatError(f"{source.name} is not a supported image.")
    if not 10 <= quality <= 100:
        raise InvalidFileError("Image quality must be between 10 and 100.")
    if max_width is not None and max_width <= 0:
        raise InvalidFileError("Maximum width must be greater than zero.")

    output = Path(output_file).expanduser() if output_file else default_compressed_path(source)
    if output.suffix.lower() != suffix:
        raise UnsupportedFormatError("The output extension must match the input image format.")
    if source.resolve() == output.resolve(strict=False):
        raise FileConflictError("The output image cannot overwrite the source image.")
    if output.exists() and not overwrite:
        raise FileConflictError(f"{output} already exists.")

    output.parent.mkdir(parents=True, exist_ok=True)
    original_size = source.stat().st_size
    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened)
            image.load()
            original_width = image.width
            if max_width and image.width > max_width:
                height = max(1, round(image.height * max_width / image.width))
                image = image.resize((max_width, height), Image.Resampling.LANCZOS)

            save_options: dict[str, int | bool] = {}
            if suffix in {".jpg", ".jpeg"}:
                if image.mode not in {"RGB", "L"}:
                    background = Image.new("RGB", image.size, "white")
                    if "A" in image.getbands():
                        background.paste(image, mask=image.getchannel("A"))
                    else:
                        background.paste(image.convert("RGB"))
                    image = background
                save_options = {"quality": quality, "optimize": True, "progressive": True}
            elif suffix == ".png":
                compress_level = max(0, min(9, round((100 - quality) * 9 / 90)))
                save_options = {"optimize": True, "compress_level": compress_level}
            elif suffix == ".webp":
                save_options = {"quality": quality, "method": 6}

            image.save(output, **save_options)
            output_width = image.width
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise ToolExecutionError(f"Could not compress {source.name}: {exc}") from exc

    result = ImageCompressionResult(
        output_path=output,
        original_size=original_size,
        compressed_size=output.stat().st_size,
        original_width=original_width,
        output_width=output_width,
    )
    logger.info(
        "tool=image_compress inputs=1 result=success duration_ms=%d",
        round((time.perf_counter() - started) * 1000),
    )
    return result
