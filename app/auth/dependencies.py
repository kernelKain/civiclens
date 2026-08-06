"""FastAPI dependencies for authenticated residents."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.auth.tokens import verify_access_token
from app.config import get_settings


settings = get_settings()


async def get_optional_resident(
    request: Request,
) -> dict | None:
    token = request.cookies.get(settings.access_cookie_name)

    if not token:
        return None

    try:
        return await run_in_threadpool(
            verify_access_token,
            token,
        )
    except (jwt.PyJWTError, ValueError):
        return None


async def require_resident(
    claims: Annotated[
        dict | None,
        Depends(get_optional_resident),
    ],
) -> dict:
    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
        )

    return claims


CurrentResident = Annotated[dict, Depends(require_resident)]