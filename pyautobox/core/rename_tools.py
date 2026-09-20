"""Safe two-phase batch renaming."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from pyautobox.exceptions import FileConflictError, InvalidFileError, ToolExecutionError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RenameOperation:
    """A planned source-to-target rename."""

    source: Path
    target: Path


def plan_renames(
    directory: Path,
    *,
    prefix: str = "",
    suffix: str = "",
    start: int = 1,
    digits: int = 3,
    replace_old: str | None = None,
    replace_new: str = "",
) -> list[RenameOperation]:
    """Build and validate a deterministic rename plan without changing files."""
    root = Path(directory).expanduser()
    if not root.is_dir():
        raise InvalidFileError(f"{root} does not exist or is not a directory.")
    if start < 0:
        raise InvalidFileError("Start must be zero or greater.")
    if digits < 1:
        raise InvalidFileError("Digits must be at least one.")
    if not any((prefix, suffix, replace_old is not None, start != 1, digits != 3)):
        raise InvalidFileError("Provide --prefix, --suffix, or --replace-old.")

    files = sorted(
        (path for path in root.iterdir() if path.is_file() and not path.name.startswith(".")),
        key=lambda path: path.name.casefold(),
    )
    operations: list[RenameOperation] = []
    for index, source in enumerate(files, start=start):
        if replace_old is not None:
            stem = source.stem.replace(replace_old, replace_new)
            new_stem = f"{prefix}{stem}{suffix}"
        else:
            new_stem = f"{prefix}{index:0{digits}d}{suffix}"
        target = source.with_name(f"{new_stem}{source.suffix}")
        if target != source:
            operations.append(RenameOperation(source=source, target=target))

    _validate_plan(operations)
    return operations


def _validate_plan(operations: list[RenameOperation]) -> None:
    targets = [operation.target for operation in operations]
    if len(set(targets)) != len(targets):
        raise FileConflictError("Two or more files would receive the same target name.")

    sources = {operation.source for operation in operations}
    for operation in operations:
        if operation.target.exists() and operation.target not in sources:
            raise FileConflictError(f"Target already exists: {operation.target.name}")


def execute_renames(
    operations: list[RenameOperation],
    *,
    dry_run: bool = False,
) -> list[RenameOperation]:
    """Execute a validated rename plan using collision-safe temporary names."""
    started = time.perf_counter()
    _validate_plan(operations)
    if dry_run or not operations:
        logger.info(
            "tool=rename inputs=%d result=success dry_run=%s duration_ms=%d",
            len(operations),
            dry_run,
            round((time.perf_counter() - started) * 1000),
        )
        return operations

    temporary: list[tuple[Path, Path, Path]] = []
    completed: list[tuple[Path, Path]] = []
    try:
        for operation in operations:
            temp = operation.source.with_name(f".pyautobox-{uuid.uuid4().hex}.tmp")
            operation.source.rename(temp)
            temporary.append((temp, operation.source, operation.target))

        for temp, source, target in temporary:
            temp.rename(target)
            completed.append((target, source))
    except Exception as exc:
        for target, source in reversed(completed):
            if target.exists() and not source.exists():
                target.rename(source)
        for temp, source, _target in reversed(temporary):
            if temp.exists() and not source.exists():
                temp.rename(source)
        raise ToolExecutionError(f"Rename failed and was rolled back: {exc}") from exc

    logger.info(
        "tool=rename inputs=%d result=success dry_run=false duration_ms=%d",
        len(operations),
        round((time.perf_counter() - started) * 1000),
    )
    return operations


def rename_files(
    directory: Path,
    *,
    dry_run: bool = False,
    **options: object,
) -> list[RenameOperation]:
    """Plan and optionally execute a batch rename."""
    plan = plan_renames(directory, **options)
    return execute_renames(plan, dry_run=dry_run)
