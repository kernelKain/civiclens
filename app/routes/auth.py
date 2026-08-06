"""Authentication pages, session actions, and form validation."""

from typing import Annotated
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from app.auth.client import (
    AuthenticationError,
    refresh_session,
    sign_in,
    sign_out,
    sign_up,
)
from app.auth.cookies import (
    delete_auth_cookies,
    prevent_auth_caching,
    set_session_cookies,
)
from app.auth.csrf import validate_csrf_token
from app.config import get_settings
from app.templating import create_template_context, templates


router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


AUTH_PAGE_TITLES = {
    "auth/sign_up.html": "Create account",
    "auth/sign_in.html": "Sign in",
    "auth/check_email.html": "Check your email",
}


def render_auth_template(
    request: Request,
    template_name: str,
    *,
    status_code: int = 200,
    **extra: object,
) -> Response:
    """Render an authentication page that browsers must not cache."""

    context = create_template_context(
        request,
        page_title=AUTH_PAGE_TITLES.get(
            template_name,
            "Authentication",
        ),
        active_nav=None,
        **extra,
    )

    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
        status_code=status_code,
    )

    prevent_auth_caching(response)
    return response


def normalize_email(value: str) -> str | None:
    """Normalize an email and reject obviously invalid input."""

    email = value.strip().lower()

    if not email or len(email) > 254:
        return None

    if email.count("@") != 1:
        return None

    local_part, domain = email.split("@", maxsplit=1)

    if not local_part or not domain:
        return None

    if any(character.isspace() for character in email):
        return None

    return email


def validate_local_next(value: str | None) -> str | None:
    """Return a safe local redirect path or None.

    Accepted examples:
        /account
        /report
        /issues/123?tab=evidence

    Rejected examples:
        https://example.com
        //example.com
        account
        /\\example.com
    """

    if value is None:
        return None

    candidate = value.strip()

    if not candidate:
        return None

    # A local redirect must begin with exactly one forward slash.
    if not candidate.startswith("/") or candidate.startswith("//"):
        return None

    # Backslashes can be interpreted as URL separators by some clients.
    if "\\" in candidate:
        return None

    # Do not allow control characters in a Location header.
    if any(
        ord(character) < 32 or ord(character) == 127
        for character in candidate
    ):
        return None

    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
    except ValueError:
        return None

    if parsed.scheme or parsed.netloc or hostname:
        return None

    return candidate


def sign_in_url(next_path: str | None = None) -> str:
    """Build a sign-in URL containing only a validated local next path."""

    safe_next = validate_local_next(next_path)

    if safe_next is None:
        return "/auth/sign-in"

    return f"/auth/sign-in?{urlencode({'next': safe_next})}"


@router.get("/sign-up", name="auth_sign_up_page")
async def sign_up_page(request: Request) -> Response:
    """Render the account registration form."""

    return render_auth_template(
        request,
        "auth/sign_up.html",
        error=None,
        email="",
        display_name="",
    )


@router.post("/sign-up", name="auth_sign_up")
async def sign_up_action(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
) -> Response:
    """Validate registration data and create a Supabase user."""

    validate_csrf_token(request, csrf_token)

    normalized_email = normalize_email(email)
    normalized_display_name = display_name.strip()

    error: str | None = None

    if not 2 <= len(normalized_display_name) <= 80:
        error = "Display name must contain between 2 and 80 characters."
    elif normalized_email is None:
        error = "Enter a valid email address containing at most 254 characters."
    elif not 10 <= len(password) <= 72:
        error = "Password must contain between 10 and 72 characters."

    if error is not None:
        return render_auth_template(
            request,
            "auth/sign_up.html",
            status_code=400,
            error=error,
            email=(
                email.strip().lower()
                if len(email.strip()) <= 254
                else ""
            ),
            display_name=normalized_display_name,
        )

    try:
        await sign_up(
            normalized_email,
            password,
            normalized_display_name,
        )
    except AuthenticationError as exc:
        return render_auth_template(
            request,
            "auth/sign_up.html",
            status_code=400,
            error=str(exc),
            email=normalized_email,
            display_name=normalized_display_name,
        )

    response = RedirectResponse(
        url="/auth/check-email",
        status_code=303,
    )
    prevent_auth_caching(response)
    return response


@router.get("/check-email", name="auth_check_email")
async def check_email_page(request: Request) -> Response:
    """Explain that the resident must confirm their email."""

    return render_auth_template(
        request,
        "auth/check_email.html",
    )


@router.get("/sign-in", name="auth_sign_in_page")
async def sign_in_page(
    request: Request,
    next_path: Annotated[
        str | None,
        Query(alias="next"),
    ] = None,
) -> Response:
    """Render the sign-in form with an optional safe destination."""

    return render_auth_template(
        request,
        "auth/sign_in.html",
        error=None,
        email="",
        next_path=validate_local_next(next_path),
        confirmed=(
            request.query_params.get("confirmed") == "1"
        ),
    )


@router.post("/sign-in", name="auth_sign_in")
async def sign_in_action(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
    next_path: Annotated[
        str | None,
        Form(alias="next"),
    ] = None,
) -> Response:
    """Create a Supabase session and store it in secure cookies."""

    validate_csrf_token(request, csrf_token)

    normalized_email = normalize_email(email)
    safe_next = validate_local_next(next_path)

    if normalized_email is None or not 10 <= len(password) <= 72:
        return render_auth_template(
            request,
            "auth/sign_in.html",
            status_code=400,
            error=(
                "Enter a valid email and a password containing "
                "between 10 and 72 characters."
            ),
            email=(
                email.strip().lower()
                if len(email.strip()) <= 254
                else ""
            ),
            next_path=safe_next,
            confirmed=False,
        )

    try:
        session = await sign_in(normalized_email, password)
    except AuthenticationError as exc:
        return render_auth_template(
            request,
            "auth/sign_in.html",
            status_code=400,
            error=str(exc),
            email=normalized_email,
            next_path=safe_next,
            confirmed=False,
        )

    response = RedirectResponse(
        url=safe_next or "/account",
        status_code=303,
    )

    try:
        set_session_cookies(response, session)
    except ValueError:
        delete_auth_cookies(response)

        return render_auth_template(
            request,
            "auth/sign_in.html",
            status_code=502,
            error=(
                "Authentication returned an invalid session. "
                "Please try again."
            ),
            email=normalized_email,
            next_path=safe_next,
            confirmed=False,
        )

    return response


@router.get("/refresh", name="auth_refresh")
async def refresh_action(
    request: Request,
    next_path: Annotated[
        str | None,
        Query(alias="next"),
    ] = None,
) -> Response:
    """Rotate the refresh token and replace both session cookies."""

    safe_next = validate_local_next(next_path)
    destination = safe_next or "/account"

    refresh_token = request.cookies.get(
        settings.refresh_cookie_name
    )

    return await _refresh_session_response(
        refresh_token=refresh_token,
        destination=destination,
    )


async def _refresh_session_response(
    *,
    refresh_token: str | None,
    destination: str,
) -> Response:
    """Build the refresh response.

    This helper is separated only to keep refresh error handling readable.
    """

    if refresh_token is None:
        response = RedirectResponse(
            url=sign_in_url(destination),
            status_code=303,
        )
        delete_auth_cookies(response)
        return response

    try:
        session = await refresh_session(refresh_token)
    except AuthenticationError:
        response = RedirectResponse(
            url=sign_in_url(destination),
            status_code=303,
        )
        delete_auth_cookies(response)
        return response

    response = RedirectResponse(
        url=destination,
        status_code=303,
    )

    try:
        set_session_cookies(response, session)
    except ValueError:
        response = RedirectResponse(
            url=sign_in_url(destination),
            status_code=303,
        )
        delete_auth_cookies(response)

    return response


@router.post("/sign-out", name="auth_sign_out")
async def sign_out_action(
    request: Request,
    csrf_token: Annotated[str, Form()],
) -> Response:
    """Revoke the current Supabase session and remove local cookies."""

    validate_csrf_token(request, csrf_token)

    access_token = request.cookies.get(
        settings.access_cookie_name
    )
    refresh_token = request.cookies.get(
        settings.refresh_cookie_name
    )

    try:
        # If the access token cookie is missing, use the refresh token to
        # obtain an access token before asking Supabase to revoke the session.
        if access_token is None and refresh_token:
            session = await refresh_session(refresh_token)
            refreshed_access_token = session.get("access_token")

            if isinstance(refreshed_access_token, str):
                access_token = refreshed_access_token

        if access_token:
            await sign_out(access_token)
    except AuthenticationError:
        # Local logout must still complete if Supabase is temporarily
        # unavailable or the remote session has already expired.
        pass

    response = RedirectResponse(
        url="/",
        status_code=303,
    )
    delete_auth_cookies(response)
    return response