"""KHDP authentication client.

KHDP authenticates apps via an ``appId`` (UUID) registered with KHDP
plus an allowlisted ``redirectUrl``. KHDP issues a Bearer
``accessToken`` + ``refreshToken`` pair. This module wraps the two
endpoints used by the CLI / MCP server:

* ``POST /_api/oauth/login`` -- direct ``mail + password`` login.
* ``POST /_api/member/refresh-token`` -- rotate an expired access token.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from khdp.config import Config

log = logging.getLogger(__name__)


class AuthError(RuntimeError):
    """Raised when KHDP rejects a login or refresh request."""


# Backward-compat alias -- previous draft used the OIDC name.
OAuthError = AuthError


@dataclass
class TokenSet:
    """Bearer token pair issued by KHDP."""

    access_token: str
    refresh_token: str | None = None
    # KHDP's payload uses ``expireTime`` as an absolute unix-millis timestamp.
    # We normalise to seconds and store the absolute moment of expiry.
    expires_at: float = 0.0
    app_id: str = ""
    obtained_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        if self.expires_at == 0.0:
            return False
        # 30 second skew so the server doesn't reject a token we just refreshed.
        return time.time() >= (self.expires_at - 30)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TokenSet:
        return cls(**payload)

    @classmethod
    def from_khdp_response(cls, payload: dict[str, Any], *, app_id: str) -> TokenSet:
        """Normalise a KHDP token response.

        KHDP's documented field is ``expireTime``. The shape observed in
        the public ``khdp.net`` SPA bundle is:

        ```json
        { "accessToken": "...", "refreshToken": "...", "expireTime": 173... }
        ```

        ``expireTime`` is unix milliseconds in the SPA's localStorage
        usage, but tolerate both seconds and milliseconds because
        upstream documentation is not public.
        """
        access = payload.get("accessToken") or payload.get("access_token")
        if not access:
            raise AuthError(f"Login response missing accessToken: {payload}")
        refresh = payload.get("refreshToken") or payload.get("refresh_token")
        expire_raw = payload.get("expireTime") or payload.get("expire_time") or 0
        try:
            expire_num = float(expire_raw)
        except (TypeError, ValueError):
            expire_num = 0.0
        # If the value looks like milliseconds (>= 10^12), convert to seconds.
        if expire_num >= 1e12:
            expire_num = expire_num / 1000.0
        # If the value is < 10^9 it's almost certainly a relative duration
        # in seconds (rare but seen on some KHDP environments).
        if 0 < expire_num < 1e9:
            expire_num = time.time() + expire_num
        return cls(
            access_token=access,
            refresh_token=refresh,
            expires_at=expire_num,
            app_id=app_id,
            obtained_at=time.time(),
        )


@dataclass
class _Endpoints:
    login: str
    refresh: str
    auto_login: str
    consent: str


class KhdpAuthClient:
    """Thin client for KHDP's ``/_api/oauth/*`` and ``/_api/member/*`` routes.

    Two flows are supported:

    * :meth:`password_login` -- direct ``mail + password`` exchange
      against ``POST /_api/oauth/login``. The KHDP-registered app is
      identified by ``appId`` and ``redirectUrl`` (both required by the
      backend even though no browser redirect is involved).
    * :meth:`refresh` -- rotate an expired access token via
      ``POST /_api/member/refresh-token``.

    """

    def __init__(self, config: Config, *, http_client: httpx.Client | None = None) -> None:
        self.config = config
        self._http = http_client or httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "khdp/0.1.0"},
        )
        base = config.api_base.rstrip("/")
        self._endpoints = _Endpoints(
            login=f"{base}/oauth/login",
            refresh=f"{base}/member/refresh-token",
            auto_login=f"{base}/member/auto-login",
            consent=f"{base}/oauth/consent",
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> KhdpAuthClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- public API --------------------------------------------------------

    def password_login(self, *, email: str, password: str) -> TokenSet:
        """Log in with email + password.

        Requires ``app_id`` and ``redirect_url`` to be set on the config.
        Both fields are validated server-side: ``appId`` must be a UUID
        and ``redirectUrl`` must be a URL. ``password`` must be 8-50
        characters; KHDP returns HTTP 400 with explicit field-level
        errors for any violation.
        """
        if not self.config.app_id:
            raise AuthError(
                "config.app_id is required for KHDP login. "
                "Register a KHDP app and set it via KHDP_APP_ID or khdp.local.toml."
            )
        if not self.config.redirect_url:
            raise AuthError(
                "config.redirect_url is required for KHDP login. "
                "Set the value registered with the KHDP app (any allowlisted URL)."
            )

        body = {
            "appId": self.config.app_id,
            "redirectUrl": self.config.redirect_url,
            "mail": email,
            "password": password,
        }
        return self._post_token(self._endpoints.login, body)

    def refresh(self, refresh_token: str) -> TokenSet:
        """Rotate an expired access token.

        KHDP returns HTTP 403 with message
        ``"Refresh Token Is Not Validate"`` (their typo, preserved) when
        the token has been revoked or expired beyond the refresh window.
        """
        return self._post_token(self._endpoints.refresh, {"refreshToken": refresh_token})

    def auto_login(self, *, access_token: str, refresh_token: str) -> TokenSet:
        """Sliding-refresh login used by the KHDP web client at startup.

        Useful for re-establishing a session from a previously cached
        token pair without prompting for a password.
        """
        body = {"accessToken": access_token, "refreshToken": refresh_token}
        return self._post_token(self._endpoints.auto_login, body)

    # -- internals --------------------------------------------------------

    def _post_token(self, url: str, body: dict[str, Any]) -> TokenSet:
        try:
            resp = self._http.post(url, json=body)
        except httpx.HTTPError as exc:
            raise AuthError(f"KHDP endpoint unreachable ({url}): {exc}") from exc

        if resp.status_code == 200:
            try:
                payload = resp.json()
            except ValueError as exc:
                raise AuthError(f"KHDP returned non-JSON success: {resp.text[:200]}") from exc
            return TokenSet.from_khdp_response(payload, app_id=self.config.app_id)

        # Surface the most useful piece of the JSON error body.
        detail: str = resp.text[:400]
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                msg = payload.get("message")
                if isinstance(msg, list):
                    detail = "; ".join(str(m) for m in msg)
                elif isinstance(msg, str):
                    detail = msg
        except ValueError:
            pass
        raise AuthError(f"KHDP {resp.status_code} {url}: {detail}")
