"""MCP server exposing KHDP authentication state + thin API access.

This is the Tier 1 surface from PLAN.md. It runs over stdio so it can be
spawned by any MCP-aware client (Claude Code, Codex, Gemini CLI, custom
agents). The same tool set is reused across all wrappers, which is the
whole point of MCP-as-foundation.

The MCP server **never** accepts a password through tool arguments --
passwords would otherwise flow through the LLM context window. Login
is initiated out-of-band by the user via ``khdp login`` in their
terminal; the MCP server reads the resulting token cache.

Tools exposed:
  - khdp_auth_status     : is the user logged in? when does the token expire?
  - khdp_auth_refresh    : rotate the refresh token to extend the session.
  - khdp_auth_logout     : delete the locally cached tokens.
  - khdp_api_request     : authenticated passthrough to the KHDP API.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from khdp.oauth import AuthError
from khdp.session import Session

log = logging.getLogger(__name__)


_TOOLS: list[dict[str, Any]] = [
    {
        "name": "khdp_auth_status",
        "description": (
            "Return whether the user is logged in to KHDP and, if so, when "
            "the access token expires. Safe to call at any time; never "
            "performs a network request."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "khdp_auth_refresh",
        "description": (
            "Rotate the refresh token to extend the session. Use when "
            "khdp_auth_status reports is_expired=true. Fails with an "
            "AuthError if there is no cached refresh token (the user "
            "must run `khdp login` in a terminal first)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "khdp_auth_logout",
        "description": (
            "Delete the locally cached KHDP tokens. KHDP does not expose "
            "a refresh-token revocation endpoint, so this only clears "
            "client-side state."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "khdp_api_request",
        "description": (
            "Make an authenticated HTTP request against the KHDP API. The "
            "Authorization: Bearer header is added automatically. Use "
            "this as the transport for any KHDP backend endpoint that "
            "does not yet have a dedicated MCP tool."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["method", "path"],
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    "description": "HTTP method.",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "API path (e.g. '/oauth/redirect-url') or "
                        "absolute URL. Relative paths are resolved "
                        "against KHDP_API_BASE (default https://khdp.io/v1)."
                    ),
                },
                "query": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Query string parameters.",
                },
                "json": {
                    "description": "JSON body for POST/PUT/PATCH.",
                },
                "auth": {
                    "type": "string",
                    "enum": ["auto", "app_key", "api_key", "oauth"],
                    "description": (
                        "Credential to use. 'auto' (default) picks: "
                        "api_key (KHDP_TOKEN env) → oauth (cached PKCE) "
                        "→ app_key. 'app_key' sends X-App-Id/X-App-Secret; "
                        "'api_key' sends the configured KHDP API token as "
                        "Bearer; 'oauth' uses the cached PKCE token."
                    ),
                },
            },
            "additionalProperties": False,
        },
    },
]

def _result_text(payload: object) -> dict[str, Any]:
    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, indent=2, default=str, sort_keys=True)}
        ]
    }


def _error_text(message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": f"Error: {message}"}],
        "isError": True,
    }


def _dispatch(session: Session, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "khdp_auth_status":
            return _result_text(session.status())
        if name == "khdp_auth_refresh":
            tokens = session.store.load(session.config.app_id or None)
            if not tokens or not tokens.refresh_token:
                raise AuthError(
                    "No refresh token cached. Run `khdp login` in a terminal first."
                )
            refreshed = session.auth.refresh(tokens.refresh_token)
            if not refreshed.refresh_token:
                refreshed.refresh_token = tokens.refresh_token
            if not refreshed.app_id:
                refreshed.app_id = tokens.app_id or session.config.app_id
            session.store.save(refreshed)
            return _result_text({"ok": True, "expires_at": refreshed.expires_at})
        if name == "khdp_auth_logout":
            deleted = session.logout()
            return _result_text({"ok": True, "deleted": deleted})
        if name == "khdp_api_request":
            method = arguments["method"]
            path = arguments["path"]
            query = arguments.get("query") or None
            body = arguments.get("json")
            auth = arguments.get("auth") or "auto"
            resp = session.authed_request(method, path, params=query, json=body, auth=auth)
            try:
                data: object = resp.json()
            except ValueError:
                data = resp.text
            return _result_text({
                "status": resp.status_code,
                "reason": resp.reason_phrase,
                "body": data,
            })
        return _error_text(f"Unknown tool: {name}")
    except AuthError as exc:
        return _error_text(str(exc))
    except Exception as exc:
        log.exception("Tool %s failed", name)
        return _error_text(f"{type(exc).__name__}: {exc}")


# --- Server wiring (official MCP SDK) ------------------------------------


async def _run_async() -> None:
    # Imported here so users running just the CLI don't need the MCP extra.
    import mcp.types as mt
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server

    server = Server("khdp")
    session = Session.open()

    @server.list_tools()
    async def _list_tools() -> list[mt.Tool]:
        return [
            mt.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in _TOOLS
        ]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[mt.TextContent]:
        result = _dispatch(session, name, arguments or {})
        contents = result.get("content", [])
        out: list[mt.TextContent] = []
        for c in contents:
            if c.get("type") == "text":
                out.append(mt.TextContent(type="text", text=c["text"]))
        if result.get("isError"):
            raise RuntimeError(contents[0]["text"] if contents else "tool error")
        return out

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run_stdio() -> None:
    """Entry point used by the CLI and the ``khdp-mcp`` console script."""
    logging.basicConfig(
        level=logging.INFO,
        format="[khdp-mcp] %(levelname)s %(message)s",
    )
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run_async())


def main() -> None:  # pragma: no cover
    run_stdio()


if __name__ == "__main__":  # pragma: no cover
    main()
