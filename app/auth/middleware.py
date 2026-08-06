"""Authentication middleware for verified Supabase sessions."""

from collections.abc import Awaitable, Callable
from typing import Any

import jwt
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.auth.tokens import verify_access_token
from app.config import get_settings


settings = get_settings()


def safe_user_claims(
    claims: dict[str, Any],
) -> dict[str, str]:
    """Return only claims that application routes are allowed to use.

    The raw access token and the complete JWT payload are deliberately
    excluded from request.state.current_user.
    """

    user: dict[str, str] = {
        "sub": claims["sub"],
        "role": claims["role"],
    }

    email = claims.get("email")

    if isinstance(email, str):
        user["email"] = email

    user_metadata = claims.get("user_metadata")

    if isinstance(user_metadata, dict):
        display_name = user_metadata.get("display_name")

        if (
            isinstance(display_name, str)
            and 2 <= len(display_name) <= 80
        ):
            user["display_name"] = display_name

    return user


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Verify the access-token cookie once for every request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[
            [Request],
            Awaitable[Response],
        ],
    ) -> Response:
        # Every request begins signed out. A verified token changes this.
        request.state.current_user = None
        request.state.auth_session_expired = False

        access_token = request.cookies.get(
            settings.access_cookie_name
        )
        refresh_token = request.cookies.get(
            settings.refresh_cookie_name
        )

        if not access_token:
            # The access cookie may disappear when its Max-Age expires.
            # A remaining refresh cookie means the session can be renewed.
            if refresh_token:
                request.state.auth_session_expired = True

            return await call_next(request)

        try:
            claims = await run_in_threadpool(
                verify_access_token,
                access_token,
            )
        except jwt.ExpiredSignatureError:
            # The exception handler will use this flag to send protected
            # requests through /auth/refresh when a refresh cookie exists.
            request.state.auth_session_expired = True
        except (jwt.PyJWTError, ValueError):
            # Invalid signatures, claims, issuers, audiences, or subjects
            # fail closed. The visitor remains unauthenticated.
            request.state.current_user = None
        else:
            request.state.current_user = safe_user_claims(
                claims
            )

        return await call_next(request)