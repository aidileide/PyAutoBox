"""Music conversion with optional local decryption for supported containers."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from pyautobox.core.conversion.base import Converter, format_from_path
from pyautobox.core.conversion.proprietary_audio import (
    ENCRYPTED_AUDIO_FORMATS,
    decrypt_audio,
)
from pyautobox.exceptions import ConversionFailedError, ToolExecutionError

STANDARD_AUDIO_FORMATS = frozenset({"mp3", "flac", "ogg", "m4a", "wav", "aac", "wma"})
MUSIC_SOURCE_FORMATS = ENCRYPTED_AUDIO_FORMATS | STANDARD_AUDIO_FORMATS
MUSIC_TARGET_FORMATS = frozenset({"mp3", "flac", "wav"})
INPUT_FORMATS = {"m4a": "mp4", "wma": "asf"}


def find_ffmpeg(explicit: str | Path | None = None) -> str | None:
    """Return a usable FFmpeg executable from options, environment, or PATH."""
    configured = str(explicit or os.getenv("PYAUTOBOX_FFMPEG") or "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        found = shutil.which(configured)
        if found:
            return found
    return shutil.which("ffmpeg")


class MusicConverter(Converter):
    """Convert standard and locally authorized encrypted music files."""

    category = "Music"
    source_formats = MUSIC_SOURCE_FORMATS
    target_formats = MUSIC_TARGET_FORMATS

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        options = options or {}
        source = format_from_path(input_path)
        target = format_from_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        decoded: bytes | None = None
        decoded_format = source
        if source in ENCRYPTED_AUDIO_FORMATS:
            decoded, decoded_format = decrypt_audio(
                input_path,
                database=options.get("kugou_db"),
            )
            if decoded_format == target:
                output_path.write_bytes(decoded)
                return output_path

        ffmpeg = find_ffmpeg(options.get("ffmpeg"))
        if ffmpeg is None:
            raise ToolExecutionError(
                "音乐转码需要 FFmpeg。请安装 FFmpeg，或设置 PYAUTOBOX_FFMPEG。"
            )
        command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-nostdin"]
        input_bytes = None
        if decoded is None:
            command.extend(["-i", str(input_path)])
        else:
            input_format = INPUT_FORMATS.get(decoded_format, decoded_format)
            command.extend(["-f", input_format, "-i", "pipe:0"])
            input_bytes = decoded
        command.extend(["-map_metadata", "0", "-vn"])
        command.extend(self._codec_arguments(target, int(options.get("quality", 85))))
        command.append(str(output_path))
        try:
            result = subprocess.run(
                command,
                input=input_bytes,
                capture_output=True,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            raise ToolExecutionError("无法启动 FFmpeg，请检查安装路径。") from exc
        if result.returncode or not output_path.is_file() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            if len(detail) > 400:
                detail = detail[-400:]
            message = "音乐转换失败。"
            if detail:
                message = f"{message} FFmpeg：{detail}"
            raise ConversionFailedError(message)
        return output_path

    @staticmethod
    def _codec_arguments(target: str, quality: int) -> list[str]:
        if target == "flac":
            return ["-c:a", "flac"]
        if target == "wav":
            return ["-c:a", "pcm_s16le"]
        quality = max(1, min(100, quality))
        lame_quality = round((100 - quality) * 9 / 99)
        return ["-c:a", "libmp3lame", "-q:a", str(lame_quality)]
