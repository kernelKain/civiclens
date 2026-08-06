"""Public/protected page and privacy tests."""

from uuid import uuid4

import pytest

from tests.conftest import csrf_token_from


@pytest.mark.parametrize(
    "path",
    ["/report", "/following", "/account"],
)
def test_protected_pages_redirect_signed_out_users(client, path) -> None:
    response = client.get(path)

    assert response.status_code == 303
    assert response.headers["location"].startswith(
        "/auth/sign-in?next="
    )
    assert path.replace("/", "%2F") in response.headers["location"]


@pytest.mark.parametrize(
    "path",
    ["/", "/issues/example", "/health", "/auth/sign-up", "/auth/sign-in"],
)
def test_public_pages_remain_public(client, path) -> None:
    response = client.get(path)
    assert response.status_code == 200


def test_signed_out_navigation_shows_sign_in(client) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert ">Sign in<" in response.text


def test_email_is_rendered_only_on_own_account_page(
    client,
    monkeypatch,
) -> None:
    user_id = str(uuid4())
    email = "resident-private@example.com"

    monkeypatch.setattr(
        "app.auth.middleware.verify_access_token",
        lambda token: {
            "sub": user_id,
            "role": "authenticated",
            "email": email,
            "user_metadata": {"display_name": "Resident Private"},
        },
    )
    client.cookies.set("civiclens_access", "verified-test-token")

    explore = client.get("/")
    report = client.get("/report")
    following = client.get("/following")
    account = client.get("/account")

    assert explore.status_code == 200
    assert report.status_code == 200
    assert following.status_code == 200
    assert account.status_code == 200
    assert email not in explore.text
    assert email not in report.text
    assert email not in following.text
    assert email in account.text
    assert "Resident Private" in account.text
    assert "Authenticated" in account.text
    assert 'method="post" action="/auth/sign-out"' in account.text


def test_sign_out_posts_csrf_and_deletes_session(
    client,
    monkeypatch,
) -> None:
    user_id = str(uuid4())

    monkeypatch.setattr(
        "app.auth.middleware.verify_access_token",
        lambda token: {
            "sub": user_id,
            "role": "authenticated",
            "email": "resident@example.com",
            "user_metadata": {"display_name": "Resident"},
        },
    )

    async def fake_sign_out(access_token: str) -> None:
        assert access_token == "verified-test-token"

    monkeypatch.setattr("app.routes.auth.sign_out", fake_sign_out)
    client.cookies.set("civiclens_access", "verified-test-token")

    account = client.get("/account")
    csrf_token = csrf_token_from(account.text)
    response = client.post(
        "/auth/sign-out",
        data={"csrf_token": csrf_token},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
