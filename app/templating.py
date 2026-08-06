"""Shared Jinja2 template configuration and context helpers."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.auth.csrf import csrf_template_context
from app.config import get_settings


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIRECTORY = PROJECT_ROOT / "app" / "templates"

templates = Jinja2Templates(
    directory=str(TEMPLATES_DIRECTORY),
    context_processors=[csrf_template_context],
)


def create_template_context(
    request: Request,
    *,
    page_title: str,
    active_nav: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Return values shared by CivicLens templates."""

    return {
        **extra,
        "request": request,
        "settings": get_settings(),
        "page_title": page_title,
        "active_nav": active_nav,
        "csrf_token": getattr(
            request.state,
            "csrf_token",
            "",
        ),
    }