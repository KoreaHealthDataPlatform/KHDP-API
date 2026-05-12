"""SNUH SuperTable client — distributed as part of the ``khdp`` package.

Quick start::

    from khdp.supertable import Client

    with Client() as c:        # uses SUPERTABLE_BASE_URL + SUPERTABLE_TOKEN
        rows = c.query(
            "SELECT gender, COUNT(*) AS n FROM cdm.person GROUP BY 1"
        )
        for r in rows:
            print(r["gender"], r["n"])

A high-level overview, usage notes, examples, and the Claude Code skill
file live at the repo root in ``supertable/`` — they're shipped together
with the code so users get docs alongside the library.
"""

from .client import Client
from .exceptions import (
    AuthenticationError,
    NotFound,
    PolicyRejected,
    QueryFailed,
    QueryTimeout,
    SupertableError,
)

__all__ = [
    "Client",
    "SupertableError",
    "AuthenticationError",
    "NotFound",
    "PolicyRejected",
    "QueryFailed",
    "QueryTimeout",
]
