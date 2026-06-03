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


def _resolve_pat(
    store: TokenStore, config: Config,
) -> tuple[str | None, str | None]:
    """Return ``(token, source)`` for the best available PAT.

    ``source`` is ``"config"`` (env or TOML; populated through
    :mod:`khdp.config`) or ``"store"`` (a token persisted via
    ``khdp pat set`` / ``khdp pat new``); ``None`` if neither is set.

    Precedence: ``config.api_key`` first, then the runtime store. Env
    vars ``KHDP_PAT`` (canonical) and ``KHDP_TOKEN`` (legacy alias) feed
    into ``config.api_key`` through :func:`khdp.config._env_overrides`.
    """
    if config.api_key:
        return config.api_key, "config"
    stored = store.load_pat()
    if stored:
        return stored, "store"
    return None, None


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
        """Delete locally cached PKCE tokens.

        KHDP's public ``/_api`` surface does not expose a refresh-token
        revocation endpoint at the time of writing. The web SPA logs
        out by clearing local state and letting the access token expire
        naturally; we follow the same approach. Returns ``True`` if a
        token was deleted, ``False`` if there was nothing to delete.
        """
        return self.store.delete(self.config.app_id or None)

    def status(self) -> dict[str, Any]:
        pat, pat_source = _resolve_pat(self.store, self.config)
        pat_info: dict[str, Any] | None = None
        if pat:
            pat_info = {"source": pat_source, "prefix": pat[:14]}

        tokens = self.store.load(self.config.app_id or None)
        if not tokens:
            return {
                "authenticated": pat is not None,
                "auth_mode": "pat" if pat else None,
                "app_id": self.config.app_id or None,
                "pat": pat_info,
            }
        return {
            "authenticated": True,
            "auth_mode": "pat" if pat else "oauth",
            "app_id": tokens.app_id or self.config.app_id,
            "expires_at": tokens.expires_at,
            "is_expired": tokens.is_expired,
            "has_refresh_token": tokens.refresh_token is not None,
            "pat": pat_info,
        }

    def access_token(self) -> str:
        """Return a Bearer-class token to use for an authenticated call.

        Prefers an API key / PAT (``config.api_key`` from
        ``KHDP_PAT`` / ``KHDP_TOKEN`` env or TOML, or a PAT persisted
        via ``khdp pat set`` / ``khdp pat new``) over the cached
        OAuth/PKCE token. Raises :class:`AuthError` if no credential is
        available.
        """
        pat, _ = _resolve_pat(self.store, self.config)
        if pat:
            return pat
        return self.oauth_access_token()

    def oauth_access_token(self) -> str:
        """Return only the OAuth (PKCE) access token, ignoring any PAT.

        Used by ``khdp pat new`` where we explicitly need the user's
        OAuth identity to call ``POST /oauth/api-tokens``.
        """
        tokens = self.store.load(self.config.app_id or None)
        if tokens is None:
            raise AuthError(
                "Not authenticated. Run `khdp login` or set a PAT "
                "(`KHDP_PAT` env or `khdp pat set <token>`)."
            )
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

        Three modes are user-visible:

        * ``app_key`` -- ``X-App-Id`` / ``X-App-Secret``; authenticates the
          *app*, not a user. Manual issuance.
        * ``api_key`` -- ``Authorization: Bearer <pat>``; the token is
          a ``khdp_pat_*`` PAT from any source (``KHDP_PAT`` env,
          ``KHDP_TOKEN`` legacy alias, ``khdp pat set`` store, or
          ``api_key`` in TOML). Long-lived; no PKCE refresh.
        * ``oauth``  -- ``Authorization: Bearer <pkce_token>`` from
          ``khdp login``. Short-lived; PKCE refresh on the fly.

        ``auto`` picks: api_key (PAT) → oauth (cached) → app_key.
        """
        if auth in ("app_key", "api_key", "oauth"):
            return auth
        if auth != "auto":
            raise ValueError(f"unknown auth mode: {auth!r}")
        pat, _ = _resolve_pat(self.store, self.config)
        if pat:
            return "api_key"
        if self.store.load(self.config.app_id or None) is not None:
            return "oauth"
        if self.config.app_id and self.config.app_secret:
            return "app_key"
        return "oauth"  # will raise an informative AuthError downstream

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
            pat, _ = _resolve_pat(self.store, self.config)
            if not pat:
                raise AuthError(
                    "api_key auth requires a PAT "
                    "(set KHDP_PAT or run `khdp pat set <token>`)."
                )
            return {"Authorization": f"Bearer {pat}"}
        # oauth
        if require_auth:
            return {"Authorization": f"Bearer {self.oauth_access_token()}"}
        # Anonymous fall-through: attach a Bearer if one is cached.
        try:
            return {"Authorization": f"Bearer {self.oauth_access_token()}"}
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

        ``auth`` selects the credential: ``auto`` (default; picks
        ``api_key`` → ``oauth`` → ``app_key``), ``app_key``
        (``X-App-Id`` / ``X-App-Secret``), ``api_key`` (``Authorization:
        Bearer <PAT>``, long-lived), or ``oauth`` (cached PKCE
        token from ``khdp login``). Raises :class:`AuthError` if the
        selected credential is unavailable.
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
            "User-Agent": "khdp/0.6.0",
            **self._auth_headers(mode, require_auth=require_auth),
        }
        with httpx.Client(timeout=30.0) as http:
            return http.request(
                method.upper(), url, params=params, json=json, headers=headers,
            )
