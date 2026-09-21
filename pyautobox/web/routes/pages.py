"""HTML page routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from pyautobox import __version__
from pyautobox.config import MAX_UPLOAD_MB

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


def _context(request: Request) -> dict[str, object]:
    return {"request": request, "version": __version__, "max_upload_mb": MAX_UPLOAD_MB}


@router.get("/", response_class=HTMLResponse, name="home")
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_context(request),
    )


@router.get("/tools/pdf-merge", response_class=HTMLResponse, name="pdf_merge_page")
async def pdf_merge_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="pdf_merge.html",
        context=_context(request),
    )


@router.get("/tools/excel-merge", response_class=HTMLResponse, name="excel_merge_page")
async def excel_merge_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="excel_merge.html",
        context=_context(request),
    )


@router.get(
    "/tools/image-compress",
    response_class=HTMLResponse,
    name="image_compress_page",
)
async def image_compress_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="image_compress.html",
        context=_context(request),
    )


@router.get("/tools/md2pdf", response_class=HTMLResponse, name="md2pdf_page")
async def md2pdf_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="md2pdf.html",
        context=_context(request),
    )


CONVERSION_TOOLS = {
    "image": (
        "图片格式转换", "在 PNG、JPEG、WebP、BMP、TIFF 之间转换并调整尺寸。",
        ".png,.jpg,.jpeg,.webp,.bmp,.tiff", "PNG、JPG、WebP、BMP、TIFF",
        "IMAGE CONVERTER", "IMG",
    ),
    "table": (
        "表格格式转换", "在 CSV、Excel 与 JSON 记录之间可靠迁移数据。",
        ".csv,.xlsx,.json", "CSV、XLSX、JSON", "TABLE CONVERTER", "XLS",
    ),
    "json-yaml": (
        "JSON ↔ YAML", "上传文件或直接粘贴内容，完整保留中文字符。",
        ".json,.yaml,.yml", "JSON、YAML、YML", "STRUCTURED DATA", "{ }",
    ),
    "markdown": (
        "Markdown 转换", "生成可独立打开的 HTML 页面，或提取纯文本。",
        ".md,.markdown", "Markdown、MD", "DOCUMENT CONVERTER", "MD",
    ),
    "text": (
        "文本内容提取", "从 HTML 或 Markdown 中移除标签与脚本，保留可读文本。",
        ".html,.htm,.md,.markdown", "HTML、Markdown", "TEXT EXTRACTOR", "TXT",
    ),
    "audio": (
        "音频信息查看", "读取标签、时长、码率与采样率，并导出 JSON。",
        ".mp3,.flac,.m4a,.ogg", "MP3、FLAC、M4A、OGG", "AUDIO METADATA", "ID3",
    ),
    "batch": (
        "批量文件转换", "一次处理多个兼容文件，结果自动打包为 ZIP。",
        "", "同类格式的多个文件", "BATCH CONVERTER", "ZIP",
    ),
}


@router.get("/tools/convert/{tool_name}", response_class=HTMLResponse, name="conversion_page")
async def conversion_page(request: Request, tool_name: str) -> HTMLResponse:
    """Render one focused conversion tool from a strict allowlist."""
    if tool_name not in CONVERSION_TOOLS:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context=_context(request),
            status_code=404,
        )
    title, description, accept, accept_label, kicker, code = CONVERSION_TOOLS[tool_name]
    context = _context(request)
    context.update(
        tool=tool_name,
        tool_title=title,
        tool_description=description,
        accept=accept,
        accept_label=accept_label,
        tool_kicker=kicker,
        tool_code=code,
    )
    return templates.TemplateResponse(request=request, name="conversion.html", context=context)
