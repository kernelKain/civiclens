"""Authentication route, middleware, and template tests."""

from uuid import uuid4

import pytest

from app.auth.dependencies import AuthenticationRequired, require_user
from app.auth.middleware import safe_user_claims
from app.routes.auth import validate_local_next
from tests.conftest import csrf_token_from


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("/account", "/account"),
        ("/issues/123?tab=evidence", "/issues/123?tab=evidence"),
        ("https://example.com", None),
        ("//example.com", None),
        ("account", None),
        ("/\\example.com", None),
        ("/account\r\nX-Test: unsafe", None),
    ],
)
def test_validate_local_next(candidate: str, expected: str | None) -> None:
    assert validate_local_next(candidate) == expected


def test_safe_user_claims_are_allowlisted() -> None:
    claims = {
        "sub": str(uuid4()),
        "role": "authenticated",
        "email": "resident@example.com",
        "user_metadata": {"display_name": "Resident One"},
        "access_token": "must-not-escape",
        "app_metadata": {"provider": "email"},
    }

    user = safe_user_claims(claims)

    assert user == {
        "sub": claims["sub"],
        "role": "authenticated",
        "email": "resident@example.com",
        "display_name": "Resident One",
    }
    assert "access_token" not in user
    assert "app_metadata" not in user


def test_require_user_raises_with_requested_path() -> None:
    class State:
        current_user = None

    class URL:
        path = "/report"

    class Request:
        state = State()
        url = URL()

    with pytest.raises(AuthenticationRequired) as raised:
        require_user(Request())  # type: ignore[arg-type]

    assert raised.value.next_path == "/report"


def test_sign_up_page_contains_required_controls(client) -> None:
    response = client.get("/auth/sign-up")

    assert response.status_code == 200
    assert 'name="display_name"' in response.text
    assert 'name="email"' in response.text
    assert 'name="password"' in response.text
    assert 'name="csrf_token"' in response.text
    assert "confirm your email" in response.text.lower()
    assert "Already have an account?" in response.text


def test_invalid_sign_up_never_echoes_password(client) -> None:
    page = client.get("/auth/sign-up")
    csrf_token = csrf_token_from(page.text)
    password = "NeverEchoThisPassword"

    response = client.post(
        "/auth/sign-up",
        data={
            "csrf_token": csrf_token,
            "display_name": "X",
            "email": "resident@example.com",
            "password": password,
        },
    )

    assert response.status_code == 400
    assert password not in response.text
    assert "between 2 and 80" in response.text


def test_sign_in_preserves_only_safe_next(client) -> None:
    safe = client.get("/auth/sign-in?next=/report")
    unsafe = client.get(
        "/auth/sign-in?next=https://example.com/steal"
    )

    assert safe.status_code == 200
    assert 'name="next"' in safe.text
    assert 'value="/report"' in safe.text
    assert 'name="next"' not in unsafe.text


def test_sign_out_is_not_available_over_get(client) -> None:
    response = client.get("/auth/sign-out")
    assert response.status_code == 405
