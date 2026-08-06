"""Asynchronous client for the Supabase Auth REST API."""

from typing import Any

import httpx

from app.config import get_settings


class AuthenticationError(Exception):
    """A safe authentication error that may be displayed to visitors."""


class SupabaseAuthClient:
    """Small asynchronous wrapper around the Supabase Auth API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout = httpx.Timeout(10.0)

    def _headers(self, access_token: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": (
                self.settings.supabase_publishable_key.get_secret_value()
            ),
            "Content-Type": "application/json",
        }

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        return headers

    async def _post(
        self,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        access_token: str | None = None,
        action: str,
    ) -> dict[str, Any]:
        url = f"{self.settings.supabase_auth_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=self._headers(access_token),
                    json=payload or {},
                    params=params,
                )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AuthenticationError(
                "Authentication is temporarily unavailable. Please try again."
            ) from exc

        if response.status_code == 429:
            raise AuthenticationError(
                "Too many attempts; please wait and try again."
            )

        if response.is_error:
            if action == "sign_in":
                raise AuthenticationError(
                    "Unable to sign in. Check your details or confirm your email."
                )

            if action == "refresh":
                raise AuthenticationError(
                    "Your session has expired. Please sign in again."
                )

            if action == "sign_up":
                raise AuthenticationError(
                    "Unable to create the account. Check your details and try again."
                )

            raise AuthenticationError(
                "Authentication could not be completed. Please try again."
            )

        if not response.content:
            return {}

        try:
            data = response.json()
        except ValueError as exc:
            raise AuthenticationError(
                "Authentication returned an invalid response."
            ) from exc

        if not isinstance(data, dict):
            raise AuthenticationError(
                "Authentication returned an invalid response."
            )

        return data

    async def sign_up(
        self,
        email: str,
        password: str,
        display_name: str,
    ) -> None:
        await self._post(
            "/signup",
            payload={
                "email": email,
                "password": password,
                "data": {
                    "display_name": display_name,
                },
            },
            params={
                "redirect_to": str(
                    self.settings.auth_confirmation_redirect
                ),
            },
            action="sign_up",
        )

    async def sign_in(self, email: str, password: str) -> dict[str, Any]:
        return await self._post(
            "/token",
            params={"grant_type": "password"},
            payload={
                "email": email,
                "password": password,
            },
            action="sign_in",
        )

    async def refresh_session(
        self,
        refresh_token: str,
    ) -> dict[str, Any]:
        return await self._post(
            "/token",
            params={"grant_type": "refresh_token"},
            payload={"refresh_token": refresh_token},
            action="refresh",
        )

    async def sign_out(self, access_token: str) -> None:
        await self._post(
            "/logout",
            params={"scope": "local"},
            access_token=access_token,
            action="sign_out",
        )


auth_client = SupabaseAuthClient()


async def sign_up(
    email: str,
    password: str,
    display_name: str,
) -> None:
    await auth_client.sign_up(email, password, display_name)


async def sign_in(email: str, password: str) -> dict[str, Any]:
    return await auth_client.sign_in(email, password)


async def refresh_session(refresh_token: str) -> dict[str, Any]:
    return await auth_client.refresh_session(refresh_token)


async def sign_out(access_token: str) -> None:
    await auth_client.sign_out(access_token)