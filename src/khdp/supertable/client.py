"""Sync HTTP client for the SuperTable SQL gateway."""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

import httpx

from khdp import __version__ as _khdp_version

from .exceptions import (
    AuthenticationError,
    NotFound,
    PolicyRejected,
    QueryFailed,
    QueryTimeout,
    SupertableError,
)

if TYPE_CHECKING:  # pragma: no cover
    import pandas as pd
    import polars as pl
    import pyarrow as pa


_USER_AGENT = f"khdp-supertable/{_khdp_version}"


class Client:
    """SuperTable HTTP client.

    Args:
        base_url: gateway URL (e.g. ``https://supertable.example.org``).
            Falls back to env ``SUPERTABLE_BASE_URL``.
        token: bearer token. Falls back to env ``SUPERTABLE_TOKEN``.
        timeout: per-request timeout in seconds (default 120).
        verify_tls: pass-through to httpx (default True).

    Use as a context manager to release sockets eagerly::

        with Client() as c:
            rows = c.query("SELECT * FROM fhir.patient LIMIT 10")
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        *,
        timeout: float = 120.0,
        verify_tls: bool | str = True,
        transport: httpx.BaseTransport | None = None,
    ):
        url = (base_url or os.environ.get("SUPERTABLE_BASE_URL", "")).rstrip("/")
        if not url:
            raise ValueError(
                "base_url is required (or set SUPERTABLE_BASE_URL env var)"
            )
        self.base_url = url
        self.token = token or os.environ.get("SUPERTABLE_TOKEN")

        headers: dict[str, str] = {"User-Agent": _USER_AGENT}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout,
            verify=verify_tls,
            transport=transport,
        )
        # path → (ETag, parsed body) for /v1/info revalidation
        self._info_etag_cache: dict[str, tuple[str, dict[str, Any]]] = {}

    # ── lifecycle ──────────────────────────────────────────────────────

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # ── catalog ────────────────────────────────────────────────────────

    def info(
        self,
        dataset: str | None = None,
        table: str | None = None,
        *,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Return the catalog manifest (or a narrowed slice).

        - ``info()``                 → every dataset / table / column + policy summary
        - ``info("fhir")``           → just the ``fhir`` dataset
        - ``info("fhir", "patient")`` → one table

        Responses are ETag-cached client-side; subsequent calls revalidate
        with ``If-None-Match`` and return the cached body on ``304``.
        """
        path = "/v1/info"
        if dataset:
            path += f"/{dataset}"
            if table:
                path += f"/{table}"
        return self._etag_cached_get(path, use_cache=use_cache)

    def stat(
        self,
        dataset: str | None = None,
        table: str | None = None,
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Return zone-map-derived statistics.

        Cheap tier only: per-table row count and per-column min/max/null
        count. No top-N, no histograms, no exact distinct counts. Pass
        ``refresh=True`` to bypass the gateway-side cache (1h TTL).
        """
        path = "/v1/stat"
        if dataset:
            path += f"/{dataset}"
            if table:
                path += f"/{table}"
        params: dict[str, Any] = {"refresh": "true"} if refresh else {}
        r = self._client.get(path, params=params)
        self._raise_for_status(r)
        return r.json()

    def datasets(self) -> list[str]:
        """Convenience: just the dataset names."""
        return list(self.info()["datasets"])

    def tables(self, dataset: str | None = None) -> list[dict[str, Any]]:
        """Convenience: ``info(dataset)["tables"]``."""
        return list(self.info(dataset)["tables"])

    def columns(self, dataset: str, table: str) -> list[dict[str, Any]]:
        """Convenience: ``info(dataset, table)["tables"][0]["columns"]``."""
        m = self.info(dataset, table)
        if not m["tables"]:
            raise NotFound(f"unknown table: {dataset}.{table}")
        return list(m["tables"][0]["columns"])

    # ── preview / sample ───────────────────────────────────────────────

    def head(
        self, dataset: str, table: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """First N rows of a table (max 100). Server crafts the SQL, so
        the policy gate is bypassed — read-only and audit-logged."""
        r = self._client.get(
            f"/v1/head/{dataset}/{table}", params={"limit": limit}
        )
        self._raise_for_status(r)
        return list(r.json()["data"])

    # ── query ──────────────────────────────────────────────────────────

    def query(
        self,
        sql: str,
        *,
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        """Run a SELECT and return the rows as ``list[dict]``.

        - Rows are objects keyed by column name (no separate ``columns``
          array).
        - If ``len(result) == limit`` the result may have been cut off
          server-side — re-issue with a larger ``limit`` (max 50 000) or
          aggregate in SQL.
        - Raises :class:`PolicyRejected` for policy failures,
          :class:`QueryTimeout` on statement-timeout, :class:`QueryFailed`
          on DuckDB runtime errors.
        """
        body: dict[str, Any] = {"sql": sql}
        if limit is not None:
            body["limit"] = limit
        if timeout_ms is not None:
            body["timeout_ms"] = timeout_ms
        r = self._client.post("/v1/query", json=body)
        self._raise_for_status(r)
        result = r.json()
        state = result.get("state")
        if state == "succeeded":
            return list(result.get("data") or [])
        if state == "timeout":
            raise QueryTimeout(result.get("error") or "statement timeout")
        raise QueryFailed(result.get("error") or "query failed")

    # ── DataFrame helpers (optional deps) ──────────────────────────────

    def df(
        self,
        sql: str,
        *,
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> "pd.DataFrame":
        """Run a SELECT and return a pandas DataFrame.

        Requires ``pandas`` (install with ``pip install supertable[pandas]``).
        """
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError(
                "pandas is required for .df(); install with "
                "`pip install supertable[pandas]`"
            ) from e
        rows = self.query(sql, limit=limit, timeout_ms=timeout_ms)
        return pd.DataFrame(rows)

    def polars(
        self,
        sql: str,
        *,
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> "pl.DataFrame":
        """Run a SELECT and return a polars DataFrame.

        Requires ``polars`` (install with ``pip install supertable[polars]``).
        """
        try:
            import polars as pl
        except ImportError as e:
            raise ImportError(
                "polars is required for .polars(); install with "
                "`pip install supertable[polars]`"
            ) from e
        rows = self.query(sql, limit=limit, timeout_ms=timeout_ms)
        return pl.DataFrame(rows)

    def arrow(
        self,
        sql: str,
        *,
        limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> "pa.Table":
        """Run a SELECT and return a pyarrow Table.

        Requires ``pyarrow`` (install with ``pip install supertable[arrow]``).
        """
        try:
            import pyarrow as pa
        except ImportError as e:
            raise ImportError(
                "pyarrow is required for .arrow(); install with "
                "`pip install supertable[arrow]`"
            ) from e
        rows = self.query(sql, limit=limit, timeout_ms=timeout_ms)
        return pa.Table.from_pylist(rows)

    # ── internals ──────────────────────────────────────────────────────

    def _etag_cached_get(self, path: str, *, use_cache: bool) -> dict[str, Any]:
        cached = self._info_etag_cache.get(path) if use_cache else None
        headers = {"If-None-Match": cached[0]} if cached else {}
        r = self._client.get(path, headers=headers)
        if r.status_code == 304 and cached:
            return cached[1]
        self._raise_for_status(r)
        body = r.json()
        etag = r.headers.get("ETag")
        if etag and use_cache:
            self._info_etag_cache[path] = (etag, body)
        return body

    def _raise_for_status(self, r: httpx.Response) -> None:
        if r.is_success or r.status_code == 304:
            return
        # Try to extract a structured detail
        detail: Any
        try:
            detail = r.json().get("detail", r.text)
        except Exception:
            detail = r.text
        code = r.status_code
        if code == 401:
            raise AuthenticationError(str(detail) or "unauthorized")
        if code == 404:
            raise NotFound(str(detail) or "not found")
        if code == 400 and isinstance(detail, dict) and detail.get("rejected_by") == "policy":
            raise PolicyRejected(detail.get("errors"), detail.get("tables"))
        if code == 400 and isinstance(detail, dict) and "error" in detail:
            # over-limit etc.
            raise SupertableError(str(detail["error"]))
        if code == 422:
            raise SupertableError(f"validation error: {detail}")
        if code >= 500:
            raise SupertableError(f"server error {code}: {detail}")
        # 4xx fallthrough
        raise SupertableError(f"HTTP {code}: {detail}")
