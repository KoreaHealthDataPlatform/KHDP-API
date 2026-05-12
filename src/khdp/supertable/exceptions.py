"""Exception hierarchy.

    SupertableError
    ├── AuthenticationError      (401)
    ├── PolicyRejected           (400, "rejected_by": "policy")
    ├── NotFound                 (404)
    ├── QueryFailed              (200 with state == "failed")
    └── QueryTimeout             (200 with state == "timeout")
"""

from __future__ import annotations


class SupertableError(Exception):
    """Base class for every error raised by the supertable client."""


class AuthenticationError(SupertableError):
    """HTTP 401 — missing or invalid Bearer token."""


class PolicyRejected(SupertableError):
    """HTTP 400 — the gateway's policy gate refused the SQL.

    The full list of reasons is on `.errors`. Common causes:
      - banned statement type (DDL/DML/PRAGMA/…),
      - banned function (read_parquet/glob/…),
      - missing date filter on a huge table,
      - LIMIT exceeded the server's hard cap.
    """

    def __init__(self, errors: list[str] | None = None, tables: list[str] | None = None):
        self.errors: list[str] = list(errors or [])
        self.tables: list[str] = list(tables or [])
        message = "; ".join(self.errors) if self.errors else "policy rejection"
        super().__init__(message)


class NotFound(SupertableError):
    """HTTP 404 — unknown table, dataset, or filter target."""


class QueryFailed(SupertableError):
    """The gateway accepted the SQL but DuckDB reported a runtime error."""


class QueryTimeout(SupertableError):
    """The query exceeded the gateway's statement timeout."""
