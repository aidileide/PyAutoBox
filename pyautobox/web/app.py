"""FastAPI application factory."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from pyautobox import __version__
from pyautobox.exceptions import PyAutoBoxError
from pyautobox.web.routes import api, conversion, pages

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the local PyAutoBox Web application."""
    web_root = Path(__file__).resolve().parent
    application = FastAPI(
        title="PyAutoBox",
        description="Simple tools. Less repetitive work.",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
    )
    application.mount("/static", StaticFiles(directory=web_root / "static"), name="static")
    application.include_router(pages.router)
    application.include_router(api.router)
    application.include_router(conversion.router)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'"
        )
        return response

    @application.exception_handler(PyAutoBoxError)
    async def pyautobox_error_handler(_request: Request, exc: PyAutoBoxError) -> JSONResponse:
        logger.warning("tool=web result=error error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=400,
            content=api.json_error(type(exc).__name__, str(exc)),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=api.json_error("ValidationError", str(exc)),
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("tool=web result=error error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content=api.json_error(
                "ToolExecutionError",
                "The tool could not complete the request. Check the file and try again.",
            ),
        )

    return application


app = create_app()
