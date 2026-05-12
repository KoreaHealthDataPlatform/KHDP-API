"""MCP tools for SNUH SuperTable, exposed alongside KHDP auth tools.

The same MCP server (``python -m khdp.mcp_server``) speaks both KHDP
authentication and SuperTable queries, so an LLM client only opens one
connection to access both surfaces.

Tools exposed:
  - supertable_info  : catalog manifest (datasets, tables, columns, policy)
  - supertable_stat  : zone-map stats (row count + min/max/null per column)
  - supertable_head  : first N rows of a table for shape preview
  - supertable_query : run a SELECT and return rows inline

The SuperTable gateway URL and bearer token are read from the env vars
``SUPERTABLE_BASE_URL`` and ``SUPERTABLE_TOKEN`` exactly as the Python
client does. We don't accept either through tool arguments — credentials
should not flow through the LLM context.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from .client import Client
from .exceptions import (
    AuthenticationError,
    NotFound,
    PolicyRejected,
    QueryFailed,
    QueryTimeout,
    SupertableError,
)


# ── tool catalog ────────────────────────────────────────────────────────

TOOLS: list[dict[str, Any]] = [
    {
        "name": "supertable_info",
        "description": (
            "Return the SuperTable catalog manifest (datasets, tables, "
            "columns, policy summary). Call once at session start, then "
            "cache locally. ``dataset`` and ``table`` narrow the result "
            "to a single dataset or single table."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": "Optional. 'fhir' or 'cdm'.",
                },
                "table": {
                    "type": "string",
                    "description": "Optional. Requires ``dataset`` for unambiguous narrowing.",
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "supertable_stat",
        "description": (
            "Return zone-map-derived statistics: per-table row count and "
            "per-column min/max/null counts (no full scan). Use to find "
            "out the actual date range and null-rich columns before "
            "writing SQL. Cached server-side with 1h TTL — pass "
            "``refresh=true`` to recompute."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"},
                "table": {"type": "string"},
                "refresh": {
                    "type": "boolean",
                    "description": "Bypass the server cache and recompute.",
                    "default": False,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "supertable_head",
        "description": (
            "Return the first N rows of a table (max 100) for shape "
            "preview. Equivalent to ``SELECT * FROM <ds>.<t> LIMIT N`` "
            "but the server crafts the SQL, so this works on tables that "
            "would otherwise require a date filter."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["dataset", "table"],
            "properties": {
                "dataset": {"type": "string"},
                "table": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "supertable_query",
        "description": (
            "Run one SELECT / WITH / EXPLAIN against SuperTable. Returns "
            "rows as a list of objects keyed by column name (no separate "
            "``columns`` array; column names are the dict keys). The SQL "
            "is checked by the gateway's policy gate first — see "
            "``policy_summary`` in ``supertable_info`` for what's "
            "rejected. Huge tables (cdm.measurement, cdm.condition_"
            "occurrence, cdm.drug_exposure, fhir.observation) **require** "
            "a date filter on one of their date_filter_columns; queries "
            "without one are rejected."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["sql"],
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Single statement. SELECT / WITH / EXPLAIN only.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 50_000,
                    "description": "LIMIT injected. Default 100. Hard cap 50000.",
                },
                "timeout_ms": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 600_000,
                    "description": "Override per-request statement timeout (ms).",
                },
            },
            "additionalProperties": False,
        },
    },
]


# ── singleton client (created on first call) ────────────────────────────

_client: Client | None = None
_client_lock = threading.Lock()


def _get_client() -> Client:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not os.environ.get("SUPERTABLE_BASE_URL"):
                    raise SupertableError(
                        "SUPERTABLE_BASE_URL is not set. Set it (and "
                        "SUPERTABLE_TOKEN if the gateway requires auth) "
                        "before invoking SuperTable MCP tools."
                    )
                _client = Client()
    return _client


def reset_client() -> None:
    """Drop the cached client (e.g. after env-var changes). Test hook."""
    global _client
    with _client_lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                pass
            _client = None


# ── dispatcher ──────────────────────────────────────────────────────────


def dispatch(name: str, arguments: dict[str, Any]) -> Any:
    """Execute one MCP tool call. Returns a JSON-serializable result.

    Raises an exception (which the calling MCP server should convert to
    isError) on any failure.
    """
    c = _get_client()
    if name == "supertable_info":
        return c.info(
            dataset=arguments.get("dataset"),
            table=arguments.get("table"),
        )
    if name == "supertable_stat":
        return c.stat(
            dataset=arguments.get("dataset"),
            table=arguments.get("table"),
            refresh=bool(arguments.get("refresh", False)),
        )
    if name == "supertable_head":
        return {
            "dataset": arguments["dataset"],
            "table": arguments["table"],
            "data": c.head(
                arguments["dataset"],
                arguments["table"],
                limit=int(arguments.get("limit", 10)),
            ),
        }
    if name == "supertable_query":
        sql = arguments["sql"]
        kwargs: dict[str, Any] = {}
        if "limit" in arguments:
            kwargs["limit"] = int(arguments["limit"])
        if "timeout_ms" in arguments:
            kwargs["timeout_ms"] = int(arguments["timeout_ms"])
        rows = c.query(sql, **kwargs)
        return {"row_count": len(rows), "data": rows}
    raise SupertableError(f"unknown SuperTable tool: {name}")


def is_supertable_tool(name: str) -> bool:
    return any(t["name"] == name for t in TOOLS)


__all__ = [
    "TOOLS",
    "dispatch",
    "is_supertable_tool",
    "reset_client",
]
