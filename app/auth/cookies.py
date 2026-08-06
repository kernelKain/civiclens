"""Secure authentication-cookie helpers."""

from typing import Any

from starlette.responses import Response

from app.config import get_settings


settings = get_settings()

REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def prevent_auth_caching(response: Response) -> None:
    """Prevent caching of user-specific authentication responses."""

    response.headers["Cache-Control"] = "private, no-store"


def set_access_cookie(
    response: Response,
    access_token: str,
    expires_in: int,
) -> None:
    response.set_cookie(
        key=settings.access_cookie_name,
        value=access_token,
        max_age=expires_in,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )

    prevent_auth_caching(response)


def set_refresh_cookie(
    response: Response,
    refresh_token: str,
) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )

    prevent_auth_caching(response)


def set_session_cookies(
    response: Response,
    session: dict[str, Any],
) -> None:
    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    expires_in = session.get("expires_in", 3600)

    if not isinstance(access_token, str):
        raise ValueError("Supabase did not return an access token")

    if not isinstance(refresh_token, str):
        raise ValueError("Supabase did not return a refresh token")

    if not isinstance(expires_in, int):
        expires_in = 3600

    set_access_cookie(response, access_token, expires_in)
    set_refresh_cookie(response, refresh_token)


def delete_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        settings.access_cookie_name,
        path="/",
    )
    response.delete_cookie(
        settings.refresh_cookie_name,
        path="/",
    )

    prevent_auth_caching(response)