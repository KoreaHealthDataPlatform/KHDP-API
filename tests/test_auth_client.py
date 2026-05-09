"""Verify ``KhdpAuthClient`` against mocked KHDP endpoints."""

import time
from pathlib import Path

import pytest

from khdp.config import Config
from khdp.oauth import AuthError, KhdpAuthClient


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        app_id="635e3da0-ec5a-442e-a416-0824fae7a9e2",
        redirect_url="https://example.org/cb",
        api_base="https://api.example/_api",
        token_dir=tmp_path,
        use_keyring=False,
    )


def test_password_login_success(config: Config, httpx_mock) -> None:
    expire_ms = (time.time() + 3600) * 1000
    httpx_mock.add_response(
        url="https://api.example/_api/oauth/login",
        method="POST",
        json={"accessToken": "AT", "refreshToken": "RT", "expireTime": expire_ms},
    )
    with KhdpAuthClient(config) as client:
        tokens = client.password_login(email="user@example.com", password="hunter22")
    assert tokens.access_token == "AT"
    assert tokens.refresh_token == "RT"
    assert tokens.app_id == config.app_id
    assert tokens.is_expired is False


def test_password_login_validation_error_surfaces_messages(
    config: Config, httpx_mock
) -> None:
    httpx_mock.add_response(
        url="https://api.example/_api/oauth/login",
        method="POST",
        status_code=400,
        json={
            "statusCode": 400,
            "message": [
                "password must be longer than or equal to 8 characters",
                "password must be a string",
            ],
            "error": "Bad Request",
        },
    )
    with KhdpAuthClient(config) as client, pytest.raises(AuthError) as exc:
        client.password_login(email="u@example.com", password="short")
    assert "longer than or equal to 8" in str(exc.value)


def test_password_login_requires_app_id(tmp_path: Path) -> None:
    cfg = Config(token_dir=tmp_path, use_keyring=False)
    with KhdpAuthClient(cfg) as client, pytest.raises(AuthError) as exc:
        client.password_login(email="u@example.com", password="hunter22")
    assert "app_id" in str(exc.value)


def test_password_login_requires_redirect_url(tmp_path: Path) -> None:
    cfg = Config(
        app_id="635e3da0-ec5a-442e-a416-0824fae7a9e2",
        token_dir=tmp_path,
        use_keyring=False,
    )
    with KhdpAuthClient(cfg) as client, pytest.raises(AuthError) as exc:
        client.password_login(email="u@example.com", password="hunter22")
    assert "redirect_url" in str(exc.value)


def test_refresh_success(config: Config, httpx_mock) -> None:
    expire_ms = (time.time() + 1200) * 1000
    httpx_mock.add_response(
        url="https://api.example/_api/member/refresh-token",
        method="POST",
        json={"accessToken": "new-AT", "refreshToken": "new-RT", "expireTime": expire_ms},
    )
    with KhdpAuthClient(config) as client:
        tokens = client.refresh("old-RT")
    assert tokens.access_token == "new-AT"
    assert tokens.refresh_token == "new-RT"


def test_refresh_invalid_token_returns_authoritative_message(
    config: Config, httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://api.example/_api/member/refresh-token",
        method="POST",
        status_code=403,
        json={"statusCode": 403, "message": "Refresh Token Is Not Validate"},
    )
    with KhdpAuthClient(config) as client, pytest.raises(AuthError) as exc:
        client.refresh("revoked")
    # KHDP's exact wording (their typo preserved) -- verify we surface it.
    assert "Refresh Token Is Not Validate" in str(exc.value)


def test_auto_login_success(config: Config, httpx_mock) -> None:
    expire_ms = (time.time() + 600) * 1000
    httpx_mock.add_response(
        url="https://api.example/_api/member/auto-login",
        method="POST",
        json={"accessToken": "AT", "refreshToken": "RT", "expireTime": expire_ms},
    )
    with KhdpAuthClient(config) as client:
        tokens = client.auto_login(access_token="prev-AT", refresh_token="prev-RT")
    assert tokens.access_token == "AT"
