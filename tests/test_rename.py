from pathlib import Path

import pytest

from pyautobox.core.rename_tools import execute_renames, plan_renames
from pyautobox.exceptions import FileConflictError


def test_rename_dry_run_does_not_modify_files(tmp_path: Path) -> None:
    (tmp_path / "001.jpg").write_bytes(b"one")
    (tmp_path / "002.jpg").write_bytes(b"two")

    plan = plan_renames(tmp_path, prefix="vacation_")
    execute_renames(plan, dry_run=True)

    assert (tmp_path / "001.jpg").exists()
    assert (tmp_path / "002.jpg").exists()
    assert not (tmp_path / "vacation_001.jpg").exists()


def test_rename_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    (tmp_path / "IMG_1.jpg").write_bytes(b"one")
    (tmp_path / "Tokyo_1.jpg").write_bytes(b"existing")

    with pytest.raises(FileConflictError):
        plan_renames(tmp_path, replace_old="IMG_", replace_new="Tokyo_")


def test_two_phase_rename_handles_name_chain(tmp_path: Path) -> None:
    (tmp_path / "1.txt").write_text("first", encoding="utf-8")
    (tmp_path / "2.txt").write_text("second", encoding="utf-8")
    plan = plan_renames(tmp_path, prefix="", start=2, digits=1)

    execute_renames(plan)

    assert (tmp_path / "2.txt").read_text(encoding="utf-8") == "first"
    assert (tmp_path / "3.txt").read_text(encoding="utf-8") == "second"
