from pathlib import Path

import pytest

from khdp.oauth import TokenSet
from khdp.token_store import TokenStore


@pytest.fixture
def store(tmp_path: Path) -> TokenStore:
    return TokenStore(tmp_path, use_keyring=False)


def _sample(app_id: str = "635e3da0-ec5a-442e-a416-0824fae7a9e2") -> TokenSet:
    return TokenSet(
        access_token="at-123",
        refresh_token="rt-456",
        expires_at=0.0,
        app_id=app_id,
    )


def test_save_and_load_round_trip(store: TokenStore) -> None:
    tokens = _sample()
    store.save(tokens)
    loaded = store.load(tokens.app_id)
    assert loaded is not None
    assert loaded.access_token == tokens.access_token
    assert loaded.refresh_token == tokens.refresh_token


def test_load_missing_returns_none(store: TokenStore) -> None:
    assert store.load("00000000-0000-0000-0000-000000000000") is None


def test_delete_removes_entry(store: TokenStore) -> None:
    tokens = _sample()
    store.save(tokens)
    assert store.delete(tokens.app_id) is True
    assert store.load(tokens.app_id) is None


def test_multiple_apps_coexist(store: TokenStore) -> None:
    a = _sample("11111111-1111-1111-1111-111111111111")
    b = _sample("22222222-2222-2222-2222-222222222222")
    store.save(a)
    store.save(b)
    assert set(store.list_apps()) == {a.app_id, b.app_id}
    assert store.load(a.app_id).access_token == a.access_token  # type: ignore[union-attr]
    assert store.load(b.app_id).access_token == b.access_token  # type: ignore[union-attr]
