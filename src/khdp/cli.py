"""``khdp`` command-line interface.

Subcommand groups:

* ``khdp login``       -- PKCE Authorization Code login (opens a browser).
* ``khdp logout``      -- delete the cached token.
* ``khdp status``      -- show whether a token is cached.
* ``khdp refresh``     -- force a refresh-token rotation.
* ``khdp token``       -- print the current access token (use with care).
* ``khdp pat set/status/clear`` -- manage a Personal Access Token
  (issued from the KHDP web console). PAT takes precedence over OAuth
  when both are present. Also recognised via the ``KHDP_PAT`` env var.
* ``khdp datasets ...`` -- public dataset operations (list / show / files /
  download-link / download).
* ``khdp submissions ...`` -- own dataset submission operations.
* ``khdp api METHOD PATH`` -- escape hatch: any authenticated API call.
* ``khdp config``      -- show the resolved configuration.
* ``khdp mcp``         -- start the MCP server on stdio.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from collections.abc import Sequence

from khdp import __version__, cli_datasets, cli_submissions
from khdp.config import load_config
from khdp.oauth import AuthError
from khdp.session import Session

_PAT_PREFIX = "khdp_pat_"
_PAT_ENV = "KHDP_PAT"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="khdp",
        description="KHDP connector -- login + API calls + MCP server.",
    )
    parser.add_argument("--version", action="version", version=f"khdp {__version__}")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0,
        help="increase logging verbosity (repeat for debug)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── auth + housekeeping ───────────────────────────────────────────
    p_login = sub.add_parser(
        "login", help="log in via the KHDP login page (opens a browser)",
    )
    p_login.add_argument(
        "--no-browser", action="store_true",
        help="print the login URL instead of opening a browser",
    )
    p_login.set_defaults(func=_cmd_login)

    sub.add_parser("logout", help="delete cached tokens").set_defaults(func=_cmd_logout)
    sub.add_parser("status", help="show cached token state").set_defaults(func=_cmd_status)
    sub.add_parser("refresh", help="force-refresh the access token").set_defaults(func=_cmd_refresh)

    p_token = sub.add_parser("token", help="print the current access token")
    p_token.add_argument(
        "--raw", action="store_true",
        help="print only the token value (no JSON envelope)",
    )
    p_token.set_defaults(func=_cmd_token)

    # ── PAT (Personal Access Token) ──────────────────────────────────
    p_pat = sub.add_parser(
        "pat",
        help="manage a Personal Access Token (PAT takes precedence over OAuth)",
    )
    pat_sub = p_pat.add_subparsers(dest="pat_command", required=True)

    p_pat_set = pat_sub.add_parser(
        "set", help=f"store a PAT (must start with '{_PAT_PREFIX}')",
    )
    p_pat_set.add_argument("token", help="PAT value")
    p_pat_set.set_defaults(func=_cmd_pat_set)

    pat_sub.add_parser(
        "status", help="show stored / env PAT prefix",
    ).set_defaults(func=_cmd_pat_status)

    pat_sub.add_parser(
        "clear", help="delete the stored PAT (env is left untouched)",
    ).set_defaults(func=_cmd_pat_clear)

    p_pat_new = pat_sub.add_parser(
        "new",
        help=(
            "issue a PAT via OAuth (calls POST /oauth/api-tokens); "
            "requires `khdp login` first"
        ),
    )
    p_pat_new.add_argument(
        "--name", default="khdp-cli",
        help="token name (default: khdp-cli)",
    )
    p_pat_new.add_argument(
        "--scopes", action="append", default=[],
        help="grant a scope (repeatable). Omit to issue a super-PAT.",
    )
    p_pat_new.add_argument(
        "--expires-in-days", type=int, default=None,
        help="expiry in days (default: no expiry)",
    )
    p_pat_new.add_argument(
        "--force", action="store_true",
        help="revoke any existing active PAT instead of prompting",
    )
    p_pat_new.add_argument(
        "--yes", "-y", action="store_true",
        help="auto-confirm overwrite prompt on 409 conflict",
    )
    p_pat_new.set_defaults(func=_cmd_pat_new)

    # ── domain commands ───────────────────────────────────────────────
    cli_datasets.add_subparser(sub)
    cli_submissions.add_subparser(sub)

    # ── escape hatch + meta ───────────────────────────────────────────
    p_api = sub.add_parser("api", help="make an authenticated API call (escape hatch)")
    p_api.add_argument("method", help="HTTP method, e.g. GET / POST")
    p_api.add_argument("path", help="API path or full URL")
    p_api.add_argument(
        "--query", action="append", default=[], metavar="KEY=VAL",
        help="query parameter (repeatable)",
    )
    p_api.add_argument("--data", help="JSON body string")
    p_api.add_argument(
        "--auth", choices=["auto", "app-key", "api-key", "oauth"], default="auto",
        help="credential to use (default auto: api-key → oauth (cached) → app-key)",
    )
    p_api.set_defaults(func=_cmd_api)

    sub.add_parser("mcp", help="run the KHDP MCP server on stdio").set_defaults(func=_cmd_mcp)
    sub.add_parser("config", help="show resolved configuration").set_defaults(func=_cmd_config)

    return parser


def _setup_logging(verbose: int) -> None:
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(level=level, format="[khdp] %(levelname)s %(message)s")


def _emit(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _cmd_login(session: Session, args: argparse.Namespace) -> int:
    if args.no_browser:
        def _print_url(url: str) -> bool:
            print(f"Open this URL in a browser to log in:\n  {url}", file=sys.stderr)
            return True

        tokens = session.login(open_browser=_print_url)
    else:
        tokens = session.login()
    _emit({"ok": True, "expires_at": tokens.expires_at})
    return 0


def _cmd_logout(session: Session, _args: argparse.Namespace) -> int:
    deleted = session.logout()
    _emit({"ok": True, "deleted": deleted})
    return 0


def _cmd_status(session: Session, _args: argparse.Namespace) -> int:
    _emit(session.status())
    return 0


def _cmd_refresh(session: Session, _args: argparse.Namespace) -> int:
    tokens = session.store.load(session.config.app_id or None)
    if not tokens or not tokens.refresh_token:
        print("[khdp] no refresh token cached; run `khdp login` first.", file=sys.stderr)
        return 1
    refreshed = session.auth.refresh(tokens.refresh_token)
    if not refreshed.refresh_token:
        refreshed.refresh_token = tokens.refresh_token
    if not refreshed.app_id:
        refreshed.app_id = tokens.app_id or session.config.app_id
    session.store.save(refreshed)
    _emit({"ok": True, "expires_at": refreshed.expires_at})
    return 0


def _cmd_token(session: Session, args: argparse.Namespace) -> int:
    token = session.access_token()
    if args.raw:
        print(token)
    else:
        _emit({"access_token": token})
    return 0


def _cmd_pat_set(session: Session, args: argparse.Namespace) -> int:
    token = args.token.strip()
    if not token.startswith(_PAT_PREFIX):
        print(
            f"[khdp] PAT must start with '{_PAT_PREFIX}'. Got: {token[:10]}...",
            file=sys.stderr,
        )
        return 2
    session.store.save_pat(token)
    _emit({"ok": True, "stored": True, "prefix": token[:14]})
    return 0


def _cmd_pat_status(session: Session, _args: argparse.Namespace) -> int:
    env_pat = os.environ.get(_PAT_ENV)
    env_token_alias = os.environ.get("KHDP_TOKEN")
    stored = session.store.load_pat()
    cfg_api_key = session.config.api_key
    # `config.api_key` is filled from KHDP_PAT > KHDP_TOKEN > TOML
    # `api_key`. If no env var is set but `cfg_api_key` is present, it
    # came from TOML.
    cfg_from_toml = cfg_api_key and not (env_pat or env_token_alias)
    active_source: str | None = None
    if env_pat:
        active_source = "env (KHDP_PAT)"
    elif env_token_alias:
        active_source = "env (KHDP_TOKEN, legacy alias)"
    elif cfg_from_toml:
        active_source = "config (TOML)"
    elif stored:
        active_source = "store"
    _emit({
        "env": {
            "KHDP_PAT": {
                "set": bool(env_pat),
                "prefix": env_pat[:14] if env_pat else None,
            },
            "KHDP_TOKEN": {
                "set": bool(env_token_alias),
                "prefix": env_token_alias[:14] if env_token_alias else None,
            },
        },
        "config_toml": {
            "set": bool(cfg_from_toml),
            "prefix": cfg_api_key[:14] if cfg_from_toml else None,
        },
        "store": {"set": bool(stored), "prefix": stored[:14] if stored else None},
        "active_source": active_source,
    })
    return 0


def _cmd_pat_clear(session: Session, _args: argparse.Namespace) -> int:
    deleted = session.store.delete_pat()
    _emit({"ok": True, "deleted_from_store": deleted})
    return 0


def _cmd_pat_new(session: Session, args: argparse.Namespace) -> int:
    import httpx

    oauth_token = session.oauth_access_token()  # raises if not logged in

    body: dict[str, object] = {"name": args.name}
    if args.scopes:
        body["scopes"] = args.scopes
    if args.expires_in_days is not None:
        body["expiresInDays"] = args.expires_in_days

    url = session.config.api_base.rstrip("/") + "/oauth/api-tokens"
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "User-Agent": "khdp/0.3.0",
    }

    def _post(force: bool) -> httpx.Response:
        with httpx.Client(timeout=30.0) as http:
            return http.post(
                url, params={"force": "true"} if force else None,
                json=body, headers=headers,
            )

    resp = _post(force=args.force)

    # 409 충돌 — 사용자 확인 후 재호출 (--yes 면 자동)
    if resp.status_code == 409:
        existing_prefix = None
        try:
            payload = resp.json()
            existing_prefix = (
                payload.get("existingPrefix")
                or (payload.get("message") if isinstance(payload, dict) else None)
            )
        except ValueError:
            pass

        print(
            f"[khdp] An active PAT already exists (prefix: {existing_prefix}).",
            file=sys.stderr,
        )
        if args.yes:
            print("[khdp] --yes given; revoking and re-issuing.", file=sys.stderr)
        else:
            print(
                "[khdp] Re-issuing will revoke the existing PAT immediately.",
                file=sys.stderr,
            )
            answer = input("Continue? [y/N] ").strip().lower()
            if answer != "y":
                print("[khdp] aborted.", file=sys.stderr)
                return 1
        resp = _post(force=True)

    if not resp.is_success:
        print(f"[khdp] PAT issuance failed: {resp.status_code} {resp.text}", file=sys.stderr)
        return 1

    issued = resp.json()
    plain = issued.get("plainToken")
    if not plain or not plain.startswith(_PAT_PREFIX):
        print(f"[khdp] unexpected response: {issued}", file=sys.stderr)
        return 1

    session.store.save_pat(plain)
    _emit({
        "ok": True,
        "stored": True,
        "prefix": issued.get("prefix"),
        "scopes": issued.get("scopes"),
        "expires_at": issued.get("expiresAt"),
    })
    return 0


def _cmd_api(session: Session, args: argparse.Namespace) -> int:
    params: dict[str, str] = {}
    for kv in args.query:
        if "=" not in kv:
            print(f"[khdp] invalid --query (expected KEY=VAL): {kv}", file=sys.stderr)
            return 2
        k, v = kv.split("=", 1)
        params[k] = v
    body = json.loads(args.data) if args.data else None
    resp = session.authed_request(
        args.method, args.path, params=params or None, json=body,
        auth=args.auth.replace("-", "_"),
    )
    print(f"[khdp] {resp.status_code} {resp.reason_phrase}", file=sys.stderr)
    try:
        _emit(resp.json())
    except ValueError:
        sys.stdout.write(resp.text)
    return 0 if resp.is_success else 1


def _cmd_mcp(_session: Session, _args: argparse.Namespace) -> int:
    from khdp.mcp_server import run_stdio
    run_stdio()
    return 0


def _cmd_config(session: Session, _args: argparse.Namespace) -> int:
    cfg = session.config
    _emit({
        "app_id": cfg.app_id or None,
        "api_base": cfg.api_base,
        "authorize_url": cfg.authorize_url or None,
        "has_app_secret": bool(cfg.app_secret),
        "has_api_key": bool(cfg.api_key),
        "token_dir": str(cfg.token_dir),
    })
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)

    config = load_config()
    try:
        with Session.open(config=config) as session:
            return args.func(session, args)
    except AuthError as exc:
        print(f"[khdp] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("[khdp] interrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
