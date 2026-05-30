"""Search for an Open dataset and download all its files.

Picks the first dataset with `accessPolicy=open` matching the keyword,
walks the paginated bulk download-link endpoint, and streams each file
to `--out`. Requires `KHDP_TOKEN` (a `khdp_pat_*` personal API token) in
the environment.

Usage:
    KHDP_TOKEN=khdp_pat_… python 03_authenticated_download.py <keyword> [--out DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from khdp import Session


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("query")
    p.add_argument("--out", type=Path, default=Path("./data"))
    args = p.parse_args()

    if not os.environ.get("KHDP_TOKEN"):
        print("KHDP_TOKEN is not set. Issue one at "
              "https://khdp.net → Settings → Account → API Token.", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)

    with Session.open() as s, httpx.Client(timeout=30) as raw:
        # 1. Find the first Open dataset matching the keyword.
        r = s.request(
            "GET",
            "/open/datasets",
            params={"query": args.query, "accessPolicy": 0, "limit": 1},
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            print(f"No Open datasets matched {args.query!r}.", file=sys.stderr)
            return 1
        code = items[0]["code"]
        print(f"Downloading {code} → {args.out}")

        # 2. Walk the bulk presigned-URL endpoint, page by page.
        continue_token: str | None = None
        total = 0
        while True:
            params = {"continueToken": continue_token} if continue_token else {}
            r = s.authed_request(
                "GET", f"/open/datasets/{code}/latest/files-download-link-all",
                params=params,
            )
            r.raise_for_status()
            page = r.json()
            for item in page.get("items", []):
                # 3. Stream each presigned URL to disk; signature is in the URL.
                rel = Path(urlsplit(item["url"]).path).name or item["key"]
                dest = args.out / item["key"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                with raw.stream("GET", item["url"]) as resp:
                    resp.raise_for_status()
                    with dest.open("wb") as f:
                        for chunk in resp.iter_bytes():
                            f.write(chunk)
                total += 1
                print(f"  {item['key']} ({rel})")
            continue_token = page.get("continueToken")
            if not continue_token:
                break

    print(f"Done. {total} file(s) downloaded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
