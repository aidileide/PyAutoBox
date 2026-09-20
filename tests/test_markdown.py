from pathlib import Path

from pypdf import PdfReader

from pyautobox.core.markdown_tools import markdown_to_pdf


def test_markdown_generates_pdf(tmp_path: Path) -> None:
    source = tmp_path / "README.md"
    output = tmp_path / "README.pdf"
    source.write_text(
        "# 标题\n\n普通文本 **粗体** 和 *斜体*。\n\n- 第一项\n- 第二项\n",
        encoding="utf-8",
    )

    markdown_to_pdf(source, output)

    assert output.is_file()
    assert output.stat().st_size > 0
    assert len(PdfReader(output).pages) == 1
