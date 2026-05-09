import time

from khdp.oauth import AuthError, TokenSet


def test_from_khdp_response_milliseconds():
    payload = {
        "accessToken": "at",
        "refreshToken": "rt",
        # KHDP SPA stores expireTime as unix milliseconds
        "expireTime": (time.time() + 3600) * 1000,
    }
    tokens = TokenSet.from_khdp_response(payload, app_id="test-app")
    assert tokens.access_token == "at"
    assert tokens.refresh_token == "rt"
    assert tokens.app_id == "test-app"
    assert time.time() + 3500 < tokens.expires_at < time.time() + 3700
    assert tokens.is_expired is False


def test_from_khdp_response_seconds():
    payload = {
        "accessToken": "at",
        "expireTime": time.time() + 600,  # already in seconds
    }
    tokens = TokenSet.from_khdp_response(payload, app_id="x")
    assert time.time() + 500 < tokens.expires_at < time.time() + 700


def test_from_khdp_response_relative_seconds():
    # If KHDP ever returns a relative duration (< 1e9), we treat it as
    # seconds-from-now.
    payload = {"accessToken": "at", "expireTime": 60}
    tokens = TokenSet.from_khdp_response(payload, app_id="x")
    assert tokens.expires_at >= time.time() + 30


def test_from_khdp_response_missing_access_token():
    import pytest

    with pytest.raises(AuthError):
        TokenSet.from_khdp_response({"refreshToken": "rt"}, app_id="x")


def test_is_expired_true_when_past():
    tokens = TokenSet(access_token="x", expires_at=time.time() - 1)
    assert tokens.is_expired is True


def test_is_expired_false_when_no_expiry_advertised():
    tokens = TokenSet(access_token="x", expires_at=0.0)
    assert tokens.is_expired is False


def test_round_trip_dict():
    tokens = TokenSet(
        access_token="at", refresh_token="rt", expires_at=123.0, app_id="snuh-ai-app",
    )
    again = TokenSet.from_dict(tokens.to_dict())
    assert again == tokens
