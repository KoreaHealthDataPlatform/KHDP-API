"""Search KHDP's public dataset catalog without any credentials.

Usage:
    python 01_anonymous_search.py <keyword> [--limit N]

The dataset search endpoint accepts anonymous requests; only file listing
and download require an `App Key` / `OAuth` / `API Token`.
"""

from __future__ import annotations

import argparse
import sys

from khdp import Session


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query", help="keyword to search for")
    p.add_argument("--limit", type=int, default=10, help="max results (1-100)")
    args = p.parse_args()

    with Session.open() as s:
        r = s.request(
            "GET",
            "/open/datasets",
            params={"query": args.query, "limit": args.limit},
        )
    r.raise_for_status()

    items = r.json().get("items", [])
    if not items:
        print(f"No datasets matched {args.query!r}.", file=sys.stderr)
        return 1

    for d in items:
        print(f"{d['code']:<25} {d.get('title', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
