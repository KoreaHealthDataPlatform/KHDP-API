"""Session helpers -- combine ``KhdpAuthClient`` and ``TokenStore`` to give
callers a single ``access_token()`` style API that handles refresh
transparently."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from khdp.config import Config, load_config
from khdp.oauth import AuthError, KhdpAuthClient, TokenSet
from khdp.token_store import TokenStore

log = logging.getLogger(__name__)


@dataclass
class Session:
    config: Config
    auth: KhdpAuthClient
    store: TokenStore

    @classmethod
    def open(cls, *, config: Config | None = None) -> Session:
        cfg = config or load_config()
        return cls(
            config=cfg,
            auth=KhdpAuthClient(cfg),
            store=TokenStore(cfg.token_dir, use_keyring=cfg.use_keyring),
        )

    def close(self) -> None:
        self.auth.close()

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------

    def login(self, **pkce_options: Any) -> TokenSet:
        """Run the PKCE Authorization Code login.

        Keyword arguments are forwarded to
        :meth:`KhdpAuthClient.pkce_login` so callers (CLI / tests) can
        override callback host/port, browser opener, and timeout.
        """
        tokens = self.auth.pkce_login(**pkce_options)
        self.store.save(tokens)
        return tokens

    def logout(self) -> bool:
        """Delete locally cached tokens.

        KHDP's public ``/_api`` surface does not expose a refresh-token
        revocation endpoint at the time of writing. The web SPA logs
        out by clearing local state and letting the access token expire
        naturally; we follow the same approach. Returns ``True`` if a
        token was deleted, ``False`` if there was nothing to delete.
        """
        return self.store.delete(self.config.app_id or None)

    def status(self) -> dict[str, Any]:
        tokens = self.store.load(self.config.app_id or None)
        if not tokens:
            return {
                "authenticated": False,
                "app_id": self.config.app_id or None,
            }
        return {
            "authenticated": True,
            "app_id": tokens.app_id or self.config.app_id,
            "expires_at": tokens.expires_at,
            "is_expired": tokens.is_expired,
            "has_refresh_token": tokens.refresh_token is not None,
        }

    def access_token(self) -> str:
        """Return a valid access token, refreshing if necessary.

        Raises :class:`AuthError` if the user has never logged in or the
        refresh token has been revoked.
        """
        tokens = self.store.load(self.config.app_id or None)
        if tokens is None:
            raise AuthError("Not logged in. Run `khdp login` first.")
        if not tokens.is_expired:
            return tokens.access_token
        if not tokens.refresh_token:
            raise AuthError("Access token expired and no refresh token is available.")
        log.debug("Refreshing expired access token for app %s", self.config.app_id)
        refreshed = self.auth.refresh(tokens.refresh_token)
        if not refreshed.refresh_token:
            # Some KHDP environments may omit refresh_token on refresh
            # -- keep the previous one.
            refreshed.refresh_token = tokens.refresh_token
        if not refreshed.app_id:
            refreshed.app_id = tokens.app_id or self.config.app_id
        self.store.save(refreshed)
        return refreshed.access_token

    def _resolve_auth(self, auth: str) -> str:
        """Decide which credential to use for an outgoing request.

        ``auto`` prefers a cached user token (Bearer); with none available
        it falls back to App Key, then to a personal API key.
        """
        if auth in ("bearer", "app_key", "api_key"):
            return auth
        if auth != "auto":
            raise ValueError(f"unknown auth mode: {auth!r}")
        if self.store.load(self.config.app_id or None) is not None:
            return "bearer"
        if self.config.app_id and self.config.app_secret:
            return "app_key"
        if self.config.api_key:
            return "api_key"
        return "bearer"

    def _auth_headers(self, mode: str, *, require_auth: bool) -> dict[str, str]:
        if mode == "app_key":
            if not (self.config.app_id and self.config.app_secret):
                raise AuthError(
                    "App Key auth requires app_id + app_secret "
                    "(set KHDP_APP_ID and KHDP_APP_SECRET)."
                )
            return {
                "X-App-Id": self.config.app_id,
                "X-App-Secret": self.config.app_secret,
            }
        if mode == "api_key":
            if not self.config.api_key:
                raise AuthError(
                    "API key auth requires api_key (set KHDP_API_KEY)."
                )
            return {"X-API-Key": self.config.api_key}
        # bearer
        if require_auth:
            return {"Authorization": f"Bearer {self.access_token()}"}
        # Anonymous fall-through: attach a token if one is cached.
        try:
            return {"Authorization": f"Bearer {self.access_token()}"}
        except AuthError:
            return {}

    def authed_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        auth: str = "auto",
    ) -> httpx.Response:
        """Issue an authenticated request against the KHDP API base.

        ``auth`` selects the credential: ``auto`` (default), ``bearer``
        (the logged-in user token), ``app_key`` (``X-App-Id`` /
        ``X-App-Secret``), or ``api_key`` (``X-API-Key``). Raises
        :class:`AuthError` if the selected credential is unavailable.
        """
        return self._request(method, path, params=params, json=json,
                             require_auth=True, auth=auth)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        auth: str = "auto",
    ) -> httpx.Response:
        """Issue a request, falling back to anonymous when no credential is set.

        Useful for endpoints that allow anonymous access (e.g. dataset
        search/detail). ``auth`` mirrors :meth:`authed_request`.
        """
        return self._request(method, path, params=params, json=json,
                             require_auth=False, auth=auth)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None,
        json: Any,
        require_auth: bool,
        auth: str = "auto",
    ) -> httpx.Response:
        url = path if path.startswith(("http://", "https://")) else (
            self.config.api_base.rstrip("/") + "/" + path.lstrip("/")
        )
        mode = self._resolve_auth(auth)
        headers: dict[str, str] = {
            "User-Agent": "khdp/0.3.0",
            **self._auth_headers(mode, require_auth=require_auth),
        }
        with httpx.Client(timeout=30.0) as http:
            return http.request(
                method.upper(), url, params=params, json=json, headers=headers,
            )
