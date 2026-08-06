"""Opt-in hosted Supabase authentication and RLS acceptance tests."""

import os
from uuid import uuid4

import httpx
import pytest


pytestmark = pytest.mark.acceptance


REQUIRED_ENVIRONMENT = (
    "CIVICLENS_ACCEPTANCE_SUPABASE_URL",
    "CIVICLENS_ACCEPTANCE_PUBLISHABLE_KEY",
    "CIVICLENS_ACCEPTANCE_RESIDENT_A_EMAIL",
    "CIVICLENS_ACCEPTANCE_RESIDENT_A_PASSWORD",
    "CIVICLENS_ACCEPTANCE_RESIDENT_B_EMAIL",
    "CIVICLENS_ACCEPTANCE_RESIDENT_B_PASSWORD",
)


def acceptance_settings() -> dict[str, str]:
    missing = [name for name in REQUIRED_ENVIRONMENT if not os.getenv(name)]
    if missing:
        pytest.skip(
            "Hosted acceptance credentials are missing: "
            + ", ".join(missing)
        )

    return {name: os.environ[name] for name in REQUIRED_ENVIRONMENT}


def auth_headers(key: str, access_token: str | None = None) -> dict[str, str]:
    headers = {"apikey": key}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def sign_in(
    client: httpx.Client,
    base_url: str,
    key: str,
    email: str,
    password: str,
) -> dict:
    response = client.post(
        f"{base_url}/auth/v1/token",
        params={"grant_type": "password"},
        headers=auth_headers(key),
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_real_accounts_profiles_and_cross_user_privacy() -> None:
    settings = acceptance_settings()
    base_url = settings["CIVICLENS_ACCEPTANCE_SUPABASE_URL"].rstrip("/")
    key = settings["CIVICLENS_ACCEPTANCE_PUBLISHABLE_KEY"]

    with httpx.Client(timeout=20.0) as client:
        resident_a = sign_in(
            client,
            base_url,
            key,
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_A_EMAIL"],
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_A_PASSWORD"],
        )
        resident_b = sign_in(
            client,
            base_url,
            key,
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_B_EMAIL"],
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_B_PASSWORD"],
        )

        user_a = resident_a["user"]["id"]
        user_b = resident_b["user"]["id"]
        assert user_a != user_b

        own_profile = client.get(
            f"{base_url}/rest/v1/profiles",
            params={"id": f"eq.{user_a}", "select": "id,display_name,role"},
            headers=auth_headers(key, resident_a["access_token"]),
        )
        assert own_profile.status_code == 200
        assert own_profile.json()[0]["id"] == user_a

        other_profile = client.get(
            f"{base_url}/rest/v1/profiles",
            params={"id": f"eq.{user_b}", "select": "id,display_name,role"},
            headers=auth_headers(key, resident_a["access_token"]),
        )
        assert other_profile.status_code == 200
        assert other_profile.json() == []


def test_anonymous_writes_and_storage_uploads_fail() -> None:
    settings = acceptance_settings()
    base_url = settings["CIVICLENS_ACCEPTANCE_SUPABASE_URL"].rstrip("/")
    key = settings["CIVICLENS_ACCEPTANCE_PUBLISHABLE_KEY"]

    with httpx.Client(timeout=20.0) as client:
        database_write = client.post(
            f"{base_url}/rest/v1/profiles",
            headers={
                **auth_headers(key),
                "Content-Type": "application/json",
            },
            json={
                "id": str(uuid4()),
                "display_name": "Anonymous",
            },
        )
        assert database_write.status_code in {401, 403}

        storage_write = client.post(
            f"{base_url}/storage/v1/object/evidence/anonymous/{uuid4()}.jpg",
            headers={
                **auth_headers(key),
                "Content-Type": "image/jpeg",
            },
            content=b"not-a-real-image",
        )
        assert storage_write.status_code in {400, 401, 403}


def test_resident_upload_folder_and_file_privacy() -> None:
    settings = acceptance_settings()
    base_url = settings["CIVICLENS_ACCEPTANCE_SUPABASE_URL"].rstrip("/")
    key = settings["CIVICLENS_ACCEPTANCE_PUBLISHABLE_KEY"]

    with httpx.Client(timeout=20.0) as client:
        resident_a = sign_in(
            client,
            base_url,
            key,
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_A_EMAIL"],
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_A_PASSWORD"],
        )
        resident_b = sign_in(
            client,
            base_url,
            key,
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_B_EMAIL"],
            settings["CIVICLENS_ACCEPTANCE_RESIDENT_B_PASSWORD"],
        )

        user_a = resident_a["user"]["id"]
        wrong_path = f"{resident_b['user']['id']}/{uuid4()}.jpg"
        own_path = f"{user_a}/{uuid4()}.jpg"
        image = b"\xff\xd8\xff\xd9"

        wrong_folder = client.post(
            f"{base_url}/storage/v1/object/evidence/{wrong_path}",
            headers={
                **auth_headers(key, resident_a["access_token"]),
                "Content-Type": "image/jpeg",
            },
            content=image,
        )
        assert wrong_folder.status_code in {400, 401, 403}

        own_upload = client.post(
            f"{base_url}/storage/v1/object/evidence/{own_path}",
            headers={
                **auth_headers(key, resident_a["access_token"]),
                "Content-Type": "image/jpeg",
            },
            content=image,
        )
        assert own_upload.status_code == 200, own_upload.text

        resident_b_read = client.get(
            f"{base_url}/storage/v1/object/evidence/{own_path}",
            headers=auth_headers(key, resident_b["access_token"]),
        )
        assert resident_b_read.status_code in {400, 401, 403, 404}
