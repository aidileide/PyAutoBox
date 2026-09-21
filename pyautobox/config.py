"""Environment-backed configuration for PyAutoBox."""

from __future__ import annotations

import os


def _positive_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


MAX_UPLOAD_MB = _positive_int("PYAUTOBOX_MAX_UPLOAD_MB", 100)
MAX_BATCH_FILES = _positive_int("PYAUTOBOX_MAX_BATCH_FILES", 100)
DEFAULT_IMAGE_QUALITY = 80
DEFAULT_PORT = _positive_int("PYAUTOBOX_PORT", 8000)
