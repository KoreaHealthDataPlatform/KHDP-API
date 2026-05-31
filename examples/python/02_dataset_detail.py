"""Fetch full metadata for a single dataset.

Usage:
    python 02_dataset_detail.py <code> [<version>]

`<version>` defaults to `latest`; pass a semver like `1.0.0` to pin.
"""

from __future__ import annotations

import argparse
import json
import sys

from khdp import Session


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("code", help="dataset code, e.g. KHDP-OPEN-001")
    p.add_argument("version", nargs="?", default="latest")
    args = p.parse_args()

    with Session.open() as s:
        r = s.request("GET", f"/datasets/{args.code}/{args.version}")

    if r.status_code == 404:
        print(f"Dataset {args.code}@{args.version} not found.", file=sys.stderr)
        return 1
    r.raise_for_status()

    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
