# KHDP API

**English** · [한국어](./README.ko.md) · [Español](./README.es.md) · [中文](./README.zh-CN.md) · [日本語](./README.ja.md)

The developer interface for the **Korea Health Data Platform** — search, download, and submit medical research datasets from `curl`, Python, or any AI coding agent.

- REST API at `https://khdp.net/_api` — see [docs/REST_API.md](./docs/REST_API.md).
- Anonymous browsing works; authentication (App Key / OAuth / API Token) unlocks downloads and submissions.
- One authenticated session powers the CLI, Python library, and an MCP server for Claude Code, Codex CLI, Cursor, and Gemini CLI.

> Repo: `khdp-api` · Python package: `khdp` (`pip install khdp`).

## Quick start — four ways to call the API

### 1. curl
```bash
curl 'https://khdp.net/_api/open/datasets?query=heart&limit=5' | jq '.items[].code'
```

### 2. Python (`khdp` SDK)
```python
# pip install khdp
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/open/datasets", params={"query": "heart", "limit": 5})
    print([d["code"] for d in r.json()["items"]])
```

### 3. Claude Code (MCP)
```bash
pip install khdp
khdp login
claude mcp add khdp -- khdp-mcp
```
Then ask Claude Code: *"Search KHDP for heart-disease datasets and summarize the top hits."*

### 4. OpenAI Codex CLI
Append [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) to `~/.codex/config.toml`, then `khdp login` once.

> Full walkthrough: [docs/quickstart.en.md](./docs/quickstart.en.md). Endpoint reference: [docs/REST_API.md](./docs/REST_API.md).

## Use it from an AI agent

Working with KHDP through an AI coding agent (Claude Code, OpenAI Codex, Google Antigravity, Cursor, Gemini CLI, …)? Paste this into the agent:

> Please read https://github.com/KoreaHealthDataPlatform/khdp-api/blob/main/AGENTS.md and follow its guidance for the KHDP API. When authentication is needed, ask me whether I prefer **OAuth (browser login)** or a **Personal Access Token (PAT)** before proceeding.

The agent then loads [`AGENTS.md`](./AGENTS.md) — which tells it how to install `khdp`, pick the right auth path with you, call the API, handle errors, and treat dataset content as PHI-equivalent.

## Install

```bash
pipx install khdp                 # recommended — isolates from system Python
pipx install 'khdp[keyring]'      # + OS-keychain token storage
```

The package installs:
- `khdp` — CLI (login, datasets, submissions, raw `api` escape hatch)
- `khdp-mcp` — MCP server for coding agents
- `import khdp` — Python library

## Authentication

Three credential types, interchangeable across CLI, SDK, and MCP.

| Type | Header(s) | Identity | Typical use |
| --- | --- | --- | --- |
| **App Key** | `X-App-Id` + `X-App-Secret` | the app | server bots, public catalog mirrors |
| **OAuth (PKCE)** | `Authorization: Bearer <jwt>` | the user | CLI, MCP, SaaS acting on the user's behalf |
| **API Token** (PAT) | `Authorization: Bearer khdp_pat_…` | the user | notebooks, AI agents (long-lived, no refresh) |

Get an `app_id` from the KHDP team. Personal API tokens come from *Settings → Account → API Token* at <https://khdp.net>.

```toml
# ./khdp.local.toml  (or ~/.config/khdp/config.toml)
app_id     = "00000000-0000-0000-0000-000000000000"
# app_secret = "..."             # App Key
# api_key    = "khdp_pat_..."    # personal API token
api_base   = "https://khdp.net/_api"
```

Or via env: `KHDP_APP_ID`, `KHDP_APP_SECRET`, `KHDP_TOKEN`.

## CLI

```bash
khdp login [--no-browser]                              # PKCE login (loopback redirect)
khdp status | refresh | logout | config

khdp datasets list      [--query KW] [--policy open|restricted|...]
khdp datasets show      <code>[@<version>]
khdp datasets files     <code>[@<version>] [--key PREFIX]
khdp datasets download  <code>[@<version>] [--out DIR] [--dry-run]

khdp api METHOD PATH [--query K=V ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```

`--auth auto` picks: API Token → cached OAuth → App Key.

## MCP server

```bash
khdp mcp     # stdio transport
```

| Tool | Purpose |
| --- | --- |
| `khdp_auth_status`  | Logged in? When does the token expire? |
| `khdp_auth_refresh` | Rotate the refresh token. |
| `khdp_auth_logout`  | Clear local tokens. |
| `khdp_api_request`  | Authenticated HTTP passthrough to any KHDP endpoint. |

The MCP server never accepts a password through tool arguments. Login is initiated out-of-band via `khdp login` in the user's terminal; the MCP server reads the resulting token cache.

## Agent wrappers

| Platform | Setup |
| --- | --- |
| Claude Code | `claude mcp add khdp -- khdp-mcp` and copy [`wrappers/claude-code/skills/khdp-auth`](./wrappers/claude-code/skills/khdp-auth) to `~/.claude/skills/` |
| OpenAI Codex CLI | Append [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) to `~/.codex/config.toml` |
| Gemini CLI | Merge [`wrappers/gemini/settings.example.json`](./wrappers/gemini/settings.example.json) into `~/.gemini/settings.json` |

Cursor uses the same MCP server — point its `mcp.servers` config at `khdp-mcp`.

## Documentation

- [Quickstart](./docs/quickstart.en.md) — first five minutes
- [REST API reference](./docs/REST_API.md) — endpoints, payloads, scopes, errors
- [`examples/`](./examples/) — runnable Python scripts (anonymous search, dataset detail, authenticated download)
- [`AGENTS.md`](./AGENTS.md) — driving the connector from a coding agent
- [Canonical spec](https://khdp.net/docs/external-api) — official documentation site

## Security

- PKCE login (RFC 7636) over a loopback redirect (RFC 8252). No client secret in the CLI binary.
- The MCP tool surface deliberately omits a password parameter — passwords never reach the LLM context.
- Tokens are stored in the OS keychain when `khdp[keyring]` is installed; otherwise in a `0600` JSON file in the platform user-config directory.
- Per-app token isolation by `app_id`.

See [`SECURITY.md`](./SECURITY.md) for the full threat model and reporting policy.

## Development

```bash
git clone https://github.com/KoreaHealthDataPlatform/khdp-api.git
cd khdp-api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## License

MIT. See [LICENSE](./LICENSE).
