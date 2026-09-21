"""Image conversions powered by Pillow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageColor, ImageOps, UnidentifiedImageError

from pyautobox.core.conversion.base import Converter, format_from_path
from pyautobox.exceptions import InvalidFileError

PIL_FORMATS = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "bmp": "BMP", "tiff": "TIFF"}


class ImageConverter(Converter):
    """Convert and resize common raster image formats."""

    category = "Images"
    allow_identity = True
    source_formats = frozenset(PIL_FORMATS)
    target_formats = frozenset(PIL_FORMATS)

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        """Convert an image, applying EXIF orientation and proportional resize."""
        options = options or {}
        target = format_from_path(output_path)
        quality = int(options.get("quality", 85))
        if not 1 <= quality <= 100:
            raise InvalidFileError("Image quality must be between 1 and 100.")
        try:
            with Image.open(input_path) as source:
                source.verify()
            with Image.open(input_path) as source:
                image = ImageOps.exif_transpose(source)
                metadata = self._metadata(source) if options.get("keep_metadata") else {}
                image = self._resize(
                    image,
                    options.get("max_width"),
                    options.get("max_height"),
                )
                if target == "jpg":
                    image = self._for_jpeg(image, str(options.get("background", "#ffffff")))
                elif image.mode == "P" and target not in {"png", "webp"}:
                    image = image.convert("RGBA" if "transparency" in image.info else "RGB")

                output_path.parent.mkdir(parents=True, exist_ok=True)
                save_options: dict[str, Any] = dict(metadata)
                if target in {"jpg", "webp"}:
                    save_options["quality"] = quality
                image.save(output_path, format=PIL_FORMATS[target], **save_options)
        except (UnidentifiedImageError, OSError, ValueError, KeyError) as exc:
            source_format = format_from_path(input_path).upper()
            raise InvalidFileError(f"Invalid {source_format} image.") from exc
        return output_path

    @staticmethod
    def _metadata(image: Image.Image) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if exif := image.info.get("exif"):
            metadata["exif"] = exif
        if profile := image.info.get("icc_profile"):
            metadata["icc_profile"] = profile
        return metadata

    @staticmethod
    def _resize(image: Image.Image, max_width: object, max_height: object) -> Image.Image:
        width = int(max_width) if max_width else image.width
        height = int(max_height) if max_height else image.height
        if width <= 0 or height <= 0:
            raise InvalidFileError("Resize dimensions must be positive integers.")
        scale = min(width / image.width, height / image.height, 1.0)
        if scale >= 1:
            return image.copy()
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        return image.resize(size, Image.Resampling.LANCZOS)

    @staticmethod
    def _for_jpeg(image: Image.Image, background: str) -> Image.Image:
        try:
            color = ImageColor.getrgb(background)
        except ValueError as exc:
            raise InvalidFileError(f"Invalid background color: {background}") from exc
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            rgba = image.convert("RGBA")
            canvas = Image.new("RGBA", rgba.size, (*color, 255))
            return Image.alpha_composite(canvas, rgba).convert("RGB")
        return image.convert("RGB")

