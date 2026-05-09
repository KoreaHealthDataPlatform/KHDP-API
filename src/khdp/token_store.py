"""Persistent storage for KHDP access + refresh tokens.

Two backends:

* OS keyring (macOS Keychain, Windows Credential Manager, Secret Service
  on Linux) -- used when the optional ``keyring`` extra is installed and
  the user has not opted out via config.
* JSON file under the user config dir, written with ``0o600`` so other
  local users cannot read it.

Each token set is keyed by ``app_id`` so multiple KHDP-registered apps
can coexist on one machine.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from khdp.oauth import TokenSet

log = logging.getLogger(__name__)

_KEYRING_SERVICE = "khdp"


def _restrict_permissions(path: Path) -> None:
    """Best-effort 0o600 on POSIX. On Windows, file ACLs default to user-only
    in the per-user config dir, which is acceptable for a public client."""
    if sys.platform == "win32":
        return
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover
        log.warning("Could not chmod %s -- token file permissions may be permissive.", path)


class TokenStore:
    """Stores and retrieves :class:`TokenSet` objects keyed by ``app_id``."""

    def __init__(self, token_dir: Path, *, use_keyring: bool = True) -> None:
        self.token_dir = token_dir
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self._file = token_dir / "tokens.json"
        self._keyring = self._maybe_load_keyring() if use_keyring else None

    @staticmethod
    def _maybe_load_keyring() -> Any:
        try:
            import keyring  # type: ignore[import-not-found]
        except ImportError:
            return None
        try:
            keyring.get_keyring()
        except Exception:  # pragma: no cover
            return None
        return keyring

    # -- public API -------------------------------------------------------

    def save(self, tokens: TokenSet) -> None:
        key = tokens.app_id or "default"
        if self._keyring is not None:
            try:
                self._keyring.set_password(
                    _KEYRING_SERVICE, key, json.dumps(tokens.to_dict())
                )
                self._write_index(key)
                return
            except Exception as exc:  # pragma: no cover
                log.warning("Keyring write failed (%s); falling back to file.", exc)
        self._write_file(key, tokens.to_dict())

    def load(self, app_id: str | None = None) -> TokenSet | None:
        key = app_id or "default"
        if self._keyring is not None:
            try:
                raw = self._keyring.get_password(_KEYRING_SERVICE, key)
            except Exception:  # pragma: no cover
                raw = None
            if raw:
                return TokenSet.from_dict(json.loads(raw))
        data = self._read_file()
        entry = data.get(key)
        if not entry or not isinstance(entry, dict) or "access_token" not in entry:
            return None
        return TokenSet.from_dict(entry)

    def delete(self, app_id: str | None = None) -> bool:
        key = app_id or "default"
        deleted = False
        if self._keyring is not None:
            try:
                self._keyring.delete_password(_KEYRING_SERVICE, key)
                deleted = True
            except Exception:  # pragma: no cover
                pass
        data = self._read_file()
        if key in data:
            del data[key]
            self._write_file_raw(data)
            deleted = True
        return deleted

    def list_apps(self) -> list[str]:
        return sorted(self._read_file().keys())

    # -- internals --------------------------------------------------------

    def _read_file(self) -> dict[str, Any]:
        if not self._file.is_file():
            return {}
        try:
            with self._file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_file(self, key: str, payload: dict[str, Any]) -> None:
        data = self._read_file()
        data[key] = payload
        self._write_file_raw(data)

    def _write_index(self, key: str) -> None:
        data = self._read_file()
        # Don't store the secret in the index -- just record presence.
        data[key] = {"_in_keyring": True}
        self._write_file_raw(data)

    def _write_file_raw(self, data: dict[str, Any]) -> None:
        tmp = self._file.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
        tmp.replace(self._file)
        _restrict_permissions(self._file)
