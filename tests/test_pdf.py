from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pyautobox.core.pdf_tools import merge_pdfs


def _blank_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with path.open("wb") as handle:
        writer.write(handle)


def test_merge_pdfs_preserves_page_count(tmp_path: Path) -> None:
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    output = tmp_path / "merged.pdf"
    _blank_pdf(first, 1)
    _blank_pdf(second, 2)

    result = merge_pdfs([first, second], output)

    assert result == output
    assert len(PdfReader(output).pages) == 3
