"""Double-submit CSRF protection."""

import secrets
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import get_settings


settings = get_settings()

CSRF_MAX_AGE = 60 * 60


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def csrf_template_context(request: Request) -> dict[str, str]:
    """Expose only the CSRF value assigned to this request."""

    token = getattr(request.state, "csrf_token", "")
    return {"csrf_token": token}


def validate_csrf_token(
    request: Request,
    submitted_token: str,
) -> None:
    cookie_token = request.cookies.get(
        settings.csrf_cookie_name
    )

    if not cookie_token or not submitted_token:
        raise HTTPException(
            status_code=403,
            detail="Invalid form submission.",
        )

    if not secrets.compare_digest(
        cookie_token,
        submitted_token,
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid form submission.",
        )


class CSRFCookieMiddleware(BaseHTTPMiddleware):
    """Assign a CSRF token and place it in an HttpOnly cookie."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cookie_token = request.cookies.get(
            settings.csrf_cookie_name
        )

        token = cookie_token or generate_csrf_token()
        request.state.csrf_token = token

        response = await call_next(request)

        content_type = response.headers.get("content-type", "")

        if not cookie_token and "text/html" in content_type:
            response.set_cookie(
                key=settings.csrf_cookie_name,
                value=token,
                max_age=CSRF_MAX_AGE,
                httponly=True,
                secure=settings.secure_cookies,
                samesite="strict",
                path="/",
            )

        return response