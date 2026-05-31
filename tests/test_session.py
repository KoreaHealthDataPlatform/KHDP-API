"""Session-level behavior -- auto refresh and authed_request header injection."""

import time
from pathlib import Path

import pytest

from khdp.config import Config
from khdp.oauth import AuthError, KhdpAuthClient, TokenSet
from khdp.session import Session
from khdp.token_store import TokenStore


@pytest.fixture
def session(tmp_path: Path) -> Session:
    cfg = Config(
        app_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        redirect_url="https://example.org/cb",
        api_base="https://api.example/_api",
        token_dir=tmp_path,
        use_keyring=False,
    )
    return Session(
        config=cfg,
        auth=KhdpAuthClient(cfg),
        store=TokenStore(tmp_path, use_keyring=False),
    )


def test_status_unauthenticated(session: Session) -> None:
    assert session.status() == {
        "authenticated": False,
        "auth_mode": None,
        "app_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "pat": None,
    }


def test_access_token_returns_cached_when_fresh(session: Session) -> None:
    session.store.save(TokenSet(
        access_token="AT", refresh_token="RT",
        expires_at=time.time() + 600, app_id=session.config.app_id,
    ))
    assert session.access_token() == "AT"


def test_access_token_auto_refresh_when_expired(
    session: Session, httpx_mock,
) -> None:
    session.store.save(TokenSet(
        access_token="OLD", refresh_token="RT",
        expires_at=time.time() - 1, app_id=session.config.app_id,
    ))
    httpx_mock.add_response(
        url="https://api.example/_api/oauth/refresh-token",
        method="POST",
        json={
            "accessToken": "NEW",
            "refreshToken": "RT2",
            "tokenType": "Bearer",
            "expires_in": 1200,
        },
    )
    assert session.access_token() == "NEW"
    again = session.store.load(session.config.app_id)
    assert again is not None
    assert again.access_token == "NEW"
    assert again.refresh_token == "RT2"


def test_authed_request_attaches_bearer(session: Session, httpx_mock) -> None:
    session.store.save(TokenSet(
        access_token="AT", refresh_token="RT",
        expires_at=time.time() + 600, app_id=session.config.app_id,
    ))

    def _check(request):
        import httpx
        assert request.headers["authorization"] == "Bearer AT"
        return httpx.Response(200, json={"ok": True})

    httpx_mock.add_callback(_check, url="https://api.example/_api/member/me")
    resp = session.authed_request("GET", "/member/me")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def _app_key_session(tmp_path: Path, **overrides: object) -> Session:
    cfg = Config(
        app_id="APP", api_base="https://api.example/_api",
        token_dir=tmp_path, use_keyring=False, **overrides,
    )
    return Session(
        config=cfg, auth=KhdpAuthClient(cfg),
        store=TokenStore(tmp_path, use_keyring=False),
    )


def test_authed_request_app_key_headers(tmp_path: Path, httpx_mock) -> None:
    s = _app_key_session(tmp_path, app_secret="SEC")

    def _check(request):
        import httpx
        assert request.headers["x-app-id"] == "APP"
        assert request.headers["x-app-secret"] == "SEC"
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    httpx_mock.add_callback(_check, url="https://api.example/_api/datasets")
    assert s.authed_request("GET", "/datasets", auth="app_key").status_code == 200


def test_authed_request_auto_falls_back_to_app_key(tmp_path: Path, httpx_mock) -> None:
    s = _app_key_session(tmp_path, app_secret="SEC")  # no cached token

    def _check(request):
        import httpx
        assert request.headers["x-app-id"] == "APP"
        return httpx.Response(200, json={"ok": True})

    httpx_mock.add_callback(_check, url="https://api.example/_api/datasets")
    assert s.authed_request("GET", "/datasets").status_code == 200


def test_authed_request_api_key_sends_x_api_key(
    tmp_path: Path, httpx_mock,
) -> None:
    """KHDP API key (a `khdp_pat_*` PAT) is sent as `X-API-Key` — the
    gateway folds it into `Authorization: Bearer` before forwarding."""
    s = _app_key_session(tmp_path, api_key="khdp_pat_FAKE")

    def _check(request):
        import httpx
        assert request.headers["x-api-key"] == "khdp_pat_FAKE"
        # The SDK does not also send Authorization for PAT mode.
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    httpx_mock.add_callback(_check, url="https://api.example/_api/datasets")
    assert s.authed_request("GET", "/datasets").status_code == 200


def test_status_reflects_api_key(tmp_path: Path) -> None:
    s = _app_key_session(tmp_path, api_key="khdp_pat_FAKE")
    assert s.status() == {
        "authenticated": True,
        "auth_mode": "pat",
        "app_id": "APP",
        "pat": {"source": "config", "prefix": "khdp_pat_FAKE"},
    }


def test_resolve_auth_explicit_oauth_ignores_api_key(
    tmp_path: Path,
) -> None:
    """`auth='oauth'` must NOT use the api_key fallback."""
    s = _app_key_session(tmp_path, api_key="khdp_pat_FAKE")
    # api_key is set, but explicit `oauth` should require the PKCE cache.
    with pytest.raises(AuthError):
        s.authed_request("GET", "/datasets", auth="oauth")
