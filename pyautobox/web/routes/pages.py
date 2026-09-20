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
