"""Authentication pages and form actions."""

from typing import Annotated

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from app.auth.client import (
    AuthenticationError,
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


@router.get("/sign-up", name="auth_sign_up_page")
async def sign_up_page(request: Request) -> Response:
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
    validate_csrf_token(request, csrf_token)

    email = email.strip().lower()
    display_name = display_name.strip()

    if not email or not display_name or len(password) < 8:
        return render_auth_template(
            request,
            "auth/sign_up.html",
            status_code=400,
            error=(
                "Enter your name, a valid email, and a password "
                "containing at least eight characters."
            ),
            email=email,
            display_name=display_name,
        )

    try:
        await sign_up(email, password, display_name)
    except AuthenticationError as exc:
        return render_auth_template(
            request,
            "auth/sign_up.html",
            status_code=400,
            error=str(exc),
            email=email,
            display_name=display_name,
        )

    response = RedirectResponse(
        url="/auth/check-email",
        status_code=303,
    )
    prevent_auth_caching(response)
    return response


@router.get("/check-email", name="auth_check_email")
async def check_email_page(request: Request) -> Response:
    return render_auth_template(
        request,
        "auth/check_email.html",
    )


@router.get("/sign-in", name="auth_sign_in_page")
async def sign_in_page(request: Request) -> Response:
    return render_auth_template(
        request,
        "auth/sign_in.html",
        error=None,
        email="",
        confirmed=(
            request.query_params.get("confirmed") == "1"
        ),
        signed_out=(
            request.query_params.get("signed_out") == "1"
        ),
    )


@router.post("/sign-in", name="auth_sign_in")
async def sign_in_action(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    csrf_token: Annotated[str, Form()],
) -> Response:
    validate_csrf_token(request, csrf_token)

    email = email.strip().lower()

    try:
        session = await sign_in(email, password)
    except AuthenticationError as exc:
        return render_auth_template(
            request,
            "auth/sign_in.html",
            status_code=400,
            error=str(exc),
            email=email,
            confirmed=False,
            signed_out=False,
        )

    response = RedirectResponse(url="/", status_code=303)

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
            email=email,
            confirmed=False,
            signed_out=False,
        )

    return response


@router.post("/sign-out", name="auth_sign_out")
async def sign_out_action(
    request: Request,
    csrf_token: Annotated[str, Form()],
) -> Response:
    validate_csrf_token(request, csrf_token)

    access_token = request.cookies.get(
        settings.access_cookie_name
    )

    if access_token:
        try:
            await sign_out(access_token)
        except AuthenticationError:
            # Local cookies must still be deleted if Supabase is unavailable
            # or the server-side session has already expired.
            pass

    response = RedirectResponse(
        url="/auth/sign-in?signed_out=1",
        status_code=303,
    )
    delete_auth_cookies(response)
    return response