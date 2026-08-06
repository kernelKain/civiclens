"""Dependencies for routes that require an authenticated user."""

from typing import Annotated

from fastapi import Depends, Request


class AuthenticationRequired(Exception):
    """Raised when a visitor attempts to access a protected route."""

    def __init__(self, next_path: str) -> None:
        super().__init__("Authentication is required.")
        self.next_path = next_path


def require_user(request: Request) -> dict:
    """Return the verified user or request an authentication redirect."""

    user = getattr(
        request.state,
        "current_user",
        None,
    )

    if user is None:
        raise AuthenticationRequired(request.url.path)

    return user


CurrentUser = Annotated[
    dict,
    Depends(require_user),
]