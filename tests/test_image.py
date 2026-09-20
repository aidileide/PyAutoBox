from pathlib import Path

from PIL import Image

from pyautobox.core.image_tools import compress_image


def test_compress_image_creates_file_and_limits_width(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    output = tmp_path / "photo_compressed.png"
    Image.new("RGBA", (1000, 500), (255, 0, 0, 128)).save(source)

    result = compress_image(source, output, quality=75, max_width=320)

    assert output.is_file()
    assert result.output_width == 320
    with Image.open(output) as image:
        assert image.size == (320, 160)
        assert image.mode == "RGBA"
