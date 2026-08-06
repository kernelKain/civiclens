"""Local verification of Supabase access tokens."""

from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.config import get_settings


settings = get_settings()

ALLOWED_ALGORITHMS = ["RS256", "ES256", "EdDSA"]

jwks_client = PyJWKClient(
    settings.supabase_jwks_url,
    cache_jwk_set=True,
    lifespan=600,
    timeout=5,
)


def verify_access_token(token: str) -> dict:
    """Verify a Supabase JWT and return its trusted claims."""

    signing_key = jwks_client.get_signing_key_from_jwt(token)

    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=ALLOWED_ALGORITHMS,
        audience="authenticated",
        issuer=(
            f"{str(settings.supabase_url).rstrip('/')}/auth/v1"
        ),
        options={
            "require": ["exp", "iat", "sub", "role"],
        },
    )

    if claims.get("role") != "authenticated":
        raise jwt.InvalidTokenError("Unexpected role")

    if claims.get("is_anonymous") is True:
        raise jwt.InvalidTokenError(
            "Anonymous users are not residents"
        )

    subject = claims.get("sub")

    if not isinstance(subject, str):
        raise jwt.InvalidTokenError("Invalid token subject")

    try:
        UUID(subject)
    except (ValueError, TypeError) as exc:
        raise jwt.InvalidTokenError(
            "Invalid token subject"
        ) from exc

    return claims