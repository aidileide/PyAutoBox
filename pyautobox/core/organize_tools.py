"""Safe folder organization with a reversible history file."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pyautobox.exceptions import FileConflictError, InvalidFileError, ToolExecutionError

logger = logging.getLogger(__name__)
HISTORY_FILE = ".pyautobox_history.json"

CATEGORY_EXTENSIONS: dict[str, set[str]] = {
    "Images": {".bmp", ".gif", ".heic", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "Documents": {
        ".csv",
        ".doc",
        ".docx",
        ".odt",
        ".ppt",
        ".pptx",
        ".rtf",
        ".txt",
        ".xls",
        ".xlsx",
    },
    "PDFs": {".pdf"},
    "Archives": {".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".zip"},
    "Videos": {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm", ".wmv"},
    "Audio": {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav", ".wma"},
    "Code": {
        ".c",
        ".cpp",
        ".css",
        ".go",
        ".html",
        ".java",
        ".js",
        ".json",
        ".md",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".sh",
        ".sql",
        ".ts",
        ".yaml",
        ".yml",
    },
}


@dataclass(frozen=True, slots=True)
class MoveOperation:
    """A planned source-to-target file move."""

    source: Path
    target: Path


def category_for(path: Path) -> str:
    """Return the category folder for a file extension."""
    suffix = path.suffix.lower()
    for category, suffixes in CATEGORY_EXTENSIONS.items():
        if suffix in suffixes:
            return category
    return "Others"


def _available_target(directory: Path, filename: str, reserved: set[Path]) -> Path:
    candidate = directory / filename
    counter = 1
    while candidate.exists() or candidate in reserved:
        source_name = Path(filename)
        candidate = directory / f"{source_name.stem}_{counter}{source_name.suffix}"
        counter += 1
    return candidate


def plan_organization(directory: Path) -> list[MoveOperation]:
    """Plan a one-level folder organization without modifying the directory."""
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise InvalidFileError(f"{root} does not exist or is not a directory.")

    reserved: set[Path] = set()
    operations: list[MoveOperation] = []
    for source in sorted(root.iterdir(), key=lambda path: path.name.casefold()):
        if not source.is_file() or source.name == HISTORY_FILE:
            continue
        category_dir = root / category_for(source)
        target = _available_target(category_dir, source.name, reserved)
        reserved.add(target)
        operations.append(MoveOperation(source=source, target=target))
    return operations


def _read_history(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"version": 1, "runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolExecutionError(f"Could not read history file: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise ToolExecutionError("The PyAutoBox history file is invalid.")
    return data


def _write_history(path: Path, history: dict[str, object]) -> None:
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def organize_folder(directory: Path, *, dry_run: bool = True) -> list[MoveOperation]:
    """Move top-level files into categories, or return a dry-run preview."""
    started = time.perf_counter()
    root = Path(directory).expanduser()
    operations = plan_organization(root)
    if dry_run or not operations:
        logger.info(
            "tool=organize inputs=%d result=success dry_run=%s duration_ms=%d",
            len(operations),
            dry_run,
            round((time.perf_counter() - started) * 1000),
        )
        return operations

    moved: list[MoveOperation] = []
    try:
        for operation in operations:
            operation.target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(operation.source), str(operation.target))
            moved.append(operation)
    except Exception as exc:
        for operation in reversed(moved):
            if operation.target.exists() and not operation.source.exists():
                shutil.move(str(operation.target), str(operation.source))
        raise ToolExecutionError(f"Organization failed and was rolled back: {exc}") from exc

    history_path = root / HISTORY_FILE
    history = _read_history(history_path)
    runs = history["runs"]
    assert isinstance(runs, list)
    runs.append(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "undone": False,
            "operations": [
                {"source": str(item.source), "target": str(item.target)} for item in operations
            ],
        }
    )
    try:
        _write_history(history_path, history)
    except OSError as exc:
        for operation in reversed(moved):
            if operation.target.exists() and not operation.source.exists():
                shutil.move(str(operation.target), str(operation.source))
        raise ToolExecutionError(
            f"Could not save undo history; changes were rolled back: {exc}"
        ) from exc

    logger.info(
        "tool=organize inputs=%d result=success dry_run=false duration_ms=%d",
        len(operations),
        round((time.perf_counter() - started) * 1000),
    )
    return operations


def undo_last_organization(directory: Path) -> list[MoveOperation]:
    """Restore files from the most recent organization run."""
    started = time.perf_counter()
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise InvalidFileError(f"{root} does not exist or is not a directory.")
    history_path = root / HISTORY_FILE
    history = _read_history(history_path)
    runs = history["runs"]
    assert isinstance(runs, list)
    run = next((item for item in reversed(runs) if not item.get("undone")), None)
    if run is None:
        raise InvalidFileError("No organization run is available to undo.")

    operations = [
        MoveOperation(source=Path(item["target"]), target=Path(item["source"]))
        for item in run["operations"]
    ]
    for operation in operations:
        if not operation.source.is_file():
            raise InvalidFileError(f"Cannot undo because {operation.source} is missing.")
        if operation.target.exists():
            raise FileConflictError(f"Cannot restore because {operation.target} already exists.")

    restored: list[MoveOperation] = []
    try:
        for operation in reversed(operations):
            shutil.move(str(operation.source), str(operation.target))
            restored.append(operation)
    except Exception as exc:
        for operation in reversed(restored):
            if operation.target.exists() and not operation.source.exists():
                shutil.move(str(operation.target), str(operation.source))
        raise ToolExecutionError(f"Undo failed and was rolled back: {exc}") from exc

    run["undone"] = True
    run["undone_at"] = datetime.now(UTC).isoformat()
    try:
        _write_history(history_path, history)
    except OSError as exc:
        for operation in restored:
            if operation.target.exists() and not operation.source.exists():
                shutil.move(str(operation.target), str(operation.source))
        raise ToolExecutionError(
            f"Could not save undo history; undo was rolled back: {exc}"
        ) from exc
    logger.info(
        "tool=organize_undo inputs=%d result=success duration_ms=%d",
        len(operations),
        round((time.perf_counter() - started) * 1000),
    )
    return operations
