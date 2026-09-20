from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader, PdfWriter

from pyautobox.web.app import create_app
from pyautobox.web.routes import api


def _pdf_bytes() -> bytes:
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(stream)
    return stream.getvalue()


def test_web_pages_and_openapi_are_available() -> None:
    client = TestClient(create_app())

    for route in [
        "/",
        "/tools/pdf-merge",
        "/tools/excel-merge",
        "/tools/image-compress",
        "/tools/md2pdf",
        "/api/docs",
    ]:
        response = client.get(route)
        assert response.status_code == 200


def test_pdf_api_merges_and_cleans_temp_directory(tmp_path: Path, monkeypatch) -> None:
    job = tmp_path / "job"

    def fixed_job_directory() -> Path:
        job.mkdir()
        return job

    monkeypatch.setattr(api, "_job_directory", fixed_job_directory)
    client = TestClient(create_app())
    payload = _pdf_bytes()

    response = client.post(
        "/api/pdf/merge",
        files=[
            ("files", ("a.pdf", payload, "application/pdf")),
            ("files", ("b.pdf", payload, "application/pdf")),
        ],
    )

    assert response.status_code == 200
    assert response.headers["x-pyautobox-success"] == "true"
    assert len(PdfReader(BytesIO(response.content)).pages) == 2
    assert not job.exists()


def test_api_error_uses_stable_envelope() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/pdf/merge",
        files=[("files", ("unsafe.txt", b"not a pdf", "text/plain"))],
    )

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert response.json()["error"] == "UnsupportedFormatError"


def test_excel_api_preserves_original_upload_names() -> None:
    client = TestClient(create_app())
    first = BytesIO()
    second = BytesIO()
    pd.DataFrame({"value": [1]}).to_excel(first, index=False)
    pd.DataFrame({"value": [2]}).to_excel(second, index=False)

    response = client.post(
        "/api/excel/merge",
        files=[
            ("files", ("first.xlsx", first.getvalue(), "application/octet-stream")),
            ("files", ("second.xlsx", second.getvalue(), "application/octet-stream")),
        ],
        data={"include_source": "true"},
    )

    assert response.status_code == 200
    merged = pd.read_excel(BytesIO(response.content))
    assert merged["_source_file"].tolist() == ["first.xlsx", "second.xlsx"]


def test_image_api_reports_sizes_and_limits_width() -> None:
    client = TestClient(create_app())
    source = BytesIO()
    Image.new("RGB", (640, 320), "navy").save(source, format="JPEG")

    response = client.post(
        "/api/image/compress",
        files=[("files", ("photo.jpg", source.getvalue(), "image/jpeg"))],
        data={"quality": "70", "max_width": "200"},
    )

    assert response.status_code == 200
    assert int(response.headers["x-original-size"]) > 0
    assert int(response.headers["x-compressed-size"]) > 0
    with Image.open(BytesIO(response.content)) as result:
        assert result.size == (200, 100)


def test_markdown_api_generates_pdf_from_pasted_text() -> None:
    client = TestClient(create_app())

    response = client.post("/api/md2pdf", data={"markdown_text": "# Hello\n\n你好"})

    assert response.status_code == 200
    assert len(PdfReader(BytesIO(response.content)).pages) == 1
