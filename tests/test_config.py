from pathlib import Path

import pytest

from khdp.config import DEFAULT_API_BASE, load_config


def _clear_khdp_env(monkeypatch: pytest.MonkeyPatch) -> None:
    import os
    for key in [k for k in os.environ if k.startswith("KHDP_")]:
        monkeypatch.delenv(key, raising=False)


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("khdp.config.user_config_dir", lambda *_a, **_kw: str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _clear_khdp_env(monkeypatch)
    cfg = load_config()
    assert cfg.api_base == DEFAULT_API_BASE
    assert cfg.app_id == ""
    assert cfg.redirect_url == ""
    assert cfg.use_keyring is True


def test_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("khdp.config.user_config_dir", lambda *_a, **_kw: str(tmp_path))
    monkeypatch.chdir(tmp_path)
    _clear_khdp_env(monkeypatch)
    monkeypatch.setenv("KHDP_APP_ID", "635e3da0-ec5a-442e-a416-0824fae7a9e2")
    monkeypatch.setenv("KHDP_REDIRECT_URL", "https://example.org/cb")
    monkeypatch.setenv("KHDP_API_BASE", "https://staging.khdp.net/_api")
    cfg = load_config()
    assert cfg.app_id == "635e3da0-ec5a-442e-a416-0824fae7a9e2"
    assert cfg.redirect_url == "https://example.org/cb"
    assert cfg.api_base == "https://staging.khdp.net/_api"


def test_local_file_overrides_user_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text(
        'app_id = "11111111-1111-1111-1111-111111111111"\n'
        'redirect_url = "https://from-user-file.example"\n',
        encoding="utf-8",
    )
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / "khdp.local.toml").write_text(
        'redirect_url = "https://from-local-file.example"\n', encoding="utf-8"
    )
    monkeypatch.setattr(
        "khdp.config.user_config_dir", lambda *_a, **_kw: str(user_dir)
    )
    monkeypatch.chdir(cwd)
    _clear_khdp_env(monkeypatch)
    cfg = load_config()
    # Local file overrides only the keys it sets.
    assert cfg.redirect_url == "https://from-local-file.example"
    assert cfg.app_id == "11111111-1111-1111-1111-111111111111"
