"""FastAPI application entry point for CivicLens."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.cookies import prevent_auth_caching
from app.auth.csrf import CSRFCookieMiddleware
from app.config import get_settings
from app.routes.auth import router as auth_router
from app.routes.pages import router as pages_router
from app.templating import (
    PROJECT_ROOT,
    create_template_context,
    templates,
)


logger = logging.getLogger("civiclens")
settings = get_settings()

PUBLIC_DIRECTORY = PROJECT_ROOT / "public"
CSS_DIRECTORY = PUBLIC_DIRECTORY / "css"
JS_DIRECTORY = PUBLIC_DIRECTORY / "js"

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# Assign a CSRF token to HTML requests and manage the secure CSRF cookie.
app.add_middleware(CSRFCookieMiddleware)

# These mounts mirror Vercel's public asset URLs during local development.
# Vercel serves public/ through its CDN in production.
if CSS_DIRECTORY.is_dir():
    app.mount(
        "/css",
        StaticFiles(directory=str(CSS_DIRECTORY)),
        name="css",
    )

if JS_DIRECTORY.is_dir():
    app.mount(
        "/js",
        StaticFiles(directory=str(JS_DIRECTORY)),
        name="js",
    )

# Authentication routes are registered before general page routes. This
# prevents a broad page route from accidentally matching an auth URL.
app.include_router(auth_router)
app.include_router(pages_router)


@app.get("/health", name="health")
async def health() -> dict[str, str]:
    """Return a small, non-sensitive application health response."""

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@app.exception_handler(StarletteHTTPException)
async def handle_http_exception(
    request: Request,
    exception: StarletteHTTPException,
) -> HTMLResponse:
    """Render safe HTML responses for expected HTTP errors."""

    error_details: dict[int, tuple[str, str]] = {
        401: (
            "Sign in required",
            "You must sign in before accessing this page.",
        ),
        403: (
            "Request rejected",
            "This form could not be verified. Refresh the page and try again.",
        ),
        404: (
            "Page not found",
            "The page you requested does not exist or may have moved.",
        ),
        405: (
            "Action not allowed",
            "This page does not support that type of request.",
        ),
        429: (
            "Too many attempts",
            "Please wait before trying again.",
        ),
    }

    heading, description = error_details.get(
        exception.status_code,
        (
            "Something went wrong",
            "CivicLens could not complete this request.",
        ),
    )

    context = create_template_context(
        request,
        page_title=heading,
        active_nav=None,
        status_code=exception.status_code,
        heading=heading,
        description=description,
    )

    response = templates.TemplateResponse(
        request=request,
        name="errors/error.html",
        context=context,
        status_code=exception.status_code,
    )

    if request.url.path.startswith("/auth/"):
        prevent_auth_caching(response)

    return response


@app.exception_handler(Exception)
async def handle_unexpected_exception(
    request: Request,
    exception: Exception,
) -> HTMLResponse:
    """Log unexpected failures and return a safe visitor-facing response."""

    logger.error(
        "Unhandled exception while processing %s %s",
        request.method,
        request.url.path,
        exc_info=(
            type(exception),
            exception,
            exception.__traceback__,
        ),
    )

    context: dict[str, Any] = create_template_context(
        request,
        page_title="Service error",
        active_nav=None,
        status_code=500,
        heading="CivicLens encountered a problem",
        description=(
            "The request could not be completed. Please try again shortly."
        ),
    )

    response = templates.TemplateResponse(
        request=request,
        name="errors/error.html",
        context=context,
        status_code=500,
    )

    if request.url.path.startswith("/auth/"):
        prevent_auth_caching(response)

    return response