# SNUH SuperTable — user-facing materials

This folder ships **with the `khdp` package** so users who install the
KHDP connector also get the SuperTable documentation, examples, and the
Claude Code skill alongside the Python client (`from khdp.supertable
import Client`).

```
supertable/
├── README.md              you are here
├── USAGE.md               complete reference for humans + LLMs
├── examples/              runnable Python scripts
│   ├── 01_quickstart.py
│   ├── 02_dataframe.py
│   └── 03_keyset_chunking.py
└── skills/supertable/SKILL.md   drop into ~/.claude/skills/ to enable
```

## TL;DR

SuperTable is a SQL gateway over SNUH's FHIR + OMOP CDM + surgery
schedule data. Two datasets are exposed: `fhir` (anonymized real FHIR
resources) and `cdm` (synthetic INSPIRE OMOP CDM).

```bash
pip install khdp                          # core client
pip install "khdp[pandas]"                # + DataFrame helper (optional)
```

```python
from khdp.supertable import Client

with Client(base_url="https://supertable.example.org",
            token="your-bearer-token") as c:
    rows = c.query(
        "SELECT gender, COUNT(*) AS n FROM cdm.person GROUP BY 1"
    )
    print(rows)            # [{'gender_concept_id': 8507, 'n': 102134}, ...]
```

Or set `SUPERTABLE_BASE_URL` and `SUPERTABLE_TOKEN` in your env and call
`Client()` with no arguments.

See **[USAGE.md](USAGE.md)** for the full reference, including the
catalog model, policy gate rules, error handling, and pagination
strategy. See **[examples/](examples/)** for runnable scripts.

## Claude / LLM integration

The same `khdp` package exposes an MCP server (`python -m khdp.mcp_server`
or `khdp-mcp`) that speaks both KHDP authentication and SuperTable
queries. Point any MCP-aware client (Claude Code, Codex CLI, Gemini CLI,
custom agents) at it and you'll get four SuperTable tools out of the
box:

| Tool | Purpose |
|---|---|
| `supertable_info`  | catalog manifest — schemas, columns, policy summary |
| `supertable_stat`  | zone-map stats (row count, MIN/MAX/null per column) |
| `supertable_head`  | sample rows of a table |
| `supertable_query` | run one SELECT |

For Claude Code specifically, copying `skills/supertable/SKILL.md` to
`~/.claude/skills/supertable/SKILL.md` gives the assistant a turnkey
operator's guide and triggers on relevant prompts.

## What lives where

- **Code**: `src/khdp/supertable/` in this repo (you're already inside it).
- **This folder**: docs + examples + Claude skill.
- **Server-side implementation** (FastAPI gateway, ETL, admin tools):
  internal repo, not distributed.

## Access

The gateway URL and bearer token are issued by the SNUH SuperTable team
out-of-band. The Python client and MCP server pick them up from env vars
(`SUPERTABLE_BASE_URL`, `SUPERTABLE_TOKEN`) by default; you can also
pass them directly to `Client(base_url=..., token=...)`.
