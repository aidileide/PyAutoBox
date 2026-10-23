from pathlib import Path

import pytest

from pyautobox.core.organize_tools import organize_folder, undo_last_organization
from pyautobox.exceptions import ToolExecutionError


def test_organize_dry_run_does_not_move_files(tmp_path: Path) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"image")

    plan = organize_folder(tmp_path, dry_run=True)

    assert len(plan) == 1
    assert image.exists()
    assert not (tmp_path / "Images" / "photo.jpg").exists()


def test_organize_and_undo(tmp_path: Path) -> None:
    image = tmp_path / "photo.jpg"
    document = tmp_path / "notes.txt"
    image.write_bytes(b"image")
    document.write_text("notes", encoding="utf-8")

    organize_folder(tmp_path, dry_run=False)

    assert (tmp_path / "Images" / "photo.jpg").exists()
    assert (tmp_path / "Documents" / "notes.txt").exists()
    assert not image.exists()

    undo_last_organization(tmp_path)

    assert image.exists()
    assert document.exists()
    assert not (tmp_path / "Images" / "photo.jpg").exists()


def test_organize_uses_non_conflicting_name(tmp_path: Path) -> None:
    (tmp_path / "photo.jpg").write_bytes(b"new")
    images = tmp_path / "Images"
    images.mkdir()
    (images / "photo.jpg").write_bytes(b"old")

    organize_folder(tmp_path, dry_run=False)

    assert (images / "photo.jpg").read_bytes() == b"old"
    assert (images / "photo_1.jpg").read_bytes() == b"new"


@pytest.mark.parametrize("history_contents", [b"{broken", b"\xff"])
def test_invalid_history_stops_organization_before_moving_files(
    tmp_path: Path, history_contents: bytes
) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"image")
    history = tmp_path / ".pyautobox_history.json"
    history.write_bytes(history_contents)

    with pytest.raises(ToolExecutionError, match="Could not read history"):
        organize_folder(tmp_path, dry_run=False)

    assert image.read_bytes() == b"image"
    assert not (tmp_path / "Images").exists()
    assert history.read_bytes() == history_contents
