"""Read-only audio metadata inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile

from pyautobox.core.conversion.base import format_from_path
from pyautobox.exceptions import InvalidFileError, UnsupportedFormatError

AUDIO_FORMATS = frozenset({"mp3", "flac", "m4a", "ogg"})


def read_audio_metadata(path: Path) -> dict[str, Any]:
    """Return normalized tags and technical metadata for an audio file."""
    if format_from_path(path) not in AUDIO_FORMATS:
        raise UnsupportedFormatError(f"不支持的音频格式：{path.suffix or '无扩展名'}")
    try:
        audio = MutagenFile(path, easy=True)
    except (OSError, ValueError) as exc:
        raise InvalidFileError(f"{path.name} 不是有效的音频文件。") from exc
    if audio is None:
        raise InvalidFileError(f"{path.name} 不是有效的音频文件。")
    tags = audio.tags or {}
    info = getattr(audio, "info", None)

    def first(*keys: str) -> str | None:
        for key in keys:
            value = tags.get(key)
            if isinstance(value, list) and value:
                return str(value[0])
            if value is not None:
                return str(value)
        return None

    return {
        "file": path.name,
        "title": first("title"),
        "artist": first("artist"),
        "album": first("album"),
        "year": first("date", "year"),
        "track": first("tracknumber", "track"),
        "duration_seconds": round(float(getattr(info, "length", 0.0)), 2),
        "bitrate": getattr(info, "bitrate", None),
        "sample_rate": getattr(info, "sample_rate", None),
    }

