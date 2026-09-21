from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from pyautobox.core.conversion.operations import convert_one
from pyautobox.core.conversion.registry import registry
from pyautobox.web.app import create_app


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGBA", (24, 12), (90, 70, 220, 120)).save(stream, format="PNG")
    return stream.getvalue()


def test_registry_exposes_merged_conversion_categories() -> None:
    formats = registry.list_formats()
    assert {"Images", "Tables", "Structured Data", "Documents"} <= formats.keys()
    assert registry.supports("png", "webp")
    assert registry.supports("json", "yaml")


def test_json_yaml_round_trip_preserves_chinese(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    source.write_text('{"message": "你好", "items": [1, 2]}', encoding="utf-8")
    yaml_path = convert_one(source, "yaml")
    json_path = convert_one(yaml_path, "json")
    assert json.loads(json_path.read_text(encoding="utf-8"))["message"] == "你好"


def test_image_conversion_handles_transparency(tmp_path: Path) -> None:
    source = tmp_path / "logo.png"
    source.write_bytes(_png_bytes())
    output = convert_one(source, "jpg", options={"background": "#ffffff"})
    with Image.open(output) as result:
        assert result.format == "JPEG"
        assert result.size == (24, 12)


def test_conversion_pages_and_health_render_in_chinese() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json() == {"success": True, "version": "0.2.1"}
    home = client.get("/")
    tool = client.get("/tools/convert/image")
    assert "一个工具箱" in home.text
    assert "PDF 合并" in home.text
    assert 'id="tool-search"' in home.text
    assert "批量重命名" in home.text
    assert "文件夹整理" in home.text
    assert "图片格式转换" in tool.text


def test_unknown_conversion_tool_uses_pyautobox_404_page() -> None:
    response = TestClient(create_app()).get("/tools/convert/not-here")
    assert response.status_code == 404
    assert "页面不存在 · PyAutoBox" in response.text


def test_convert_api_sanitizes_filename_and_returns_jpeg() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/convert",
        files={"file": ("../../escape.png", _png_bytes(), "image/png")},
        data={"target": "jpg"},
    )
    assert response.status_code == 200
    assert "escape.jpg" in response.headers["content-disposition"]
    assert response.content.startswith(b"\xff\xd8")


def test_table_preview_reports_shape() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/table/preview",
        files={"file": ("people.csv", b"name,age\nAlice,18\n", "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["rows"] == 1
    assert response.json()["column_names"] == ["name", "age"]
