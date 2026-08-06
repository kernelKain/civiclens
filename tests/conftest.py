"""Shared test configuration for CivicLens."""

import os
import re

import pytest
from fastapi.testclient import TestClient


os.environ.setdefault("CIVICLENS_APP_NAME", "CivicLens Test")
os.environ.setdefault("CIVICLENS_ENVIRONMENT", "development")
os.environ.setdefault("CIVICLENS_DEBUG", "false")
os.environ.setdefault("CIVICLENS_PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault(
    "CIVICLENS_SUPABASE_URL",
    "https://example.supabase.co",
)
os.environ.setdefault(
    "CIVICLENS_SUPABASE_PUBLISHABLE_KEY",
    "sb_publishable_test",
)
os.environ.setdefault(
    "CIVICLENS_AUTH_CONFIRMATION_REDIRECT",
    "http://testserver/auth/sign-in?confirmed=1",
)

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Return an isolated browser-like client."""

    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def csrf_token_from(response_text: str) -> str:
    """Extract the CSRF token from an HTML form."""

    match = re.search(
        r'name="csrf_token"\s+value="([^"]+)"',
        response_text,
    )
    assert match is not None, "CSRF token was not rendered"
    return match.group(1)
