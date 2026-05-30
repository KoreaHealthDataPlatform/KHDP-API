# AGENTS.md — KHDP connector

Guidance for AI coding agents and tools (Claude Code, OpenAI Codex CLI, Gemini
CLI, Cursor, custom MCP clients) working **with** or **inside** this repo.
Follows the [agents.md](https://agents.md) convention.

`khdp` is a vendor-neutral connector to the **Korea Health Data Platform
(KHDP)**. It ships three surfaces over one auth core:

- **CLI** — `khdp …` for humans and scripts.
- **Python library** — `import khdp` for programmatic use.
- **MCP server** — `khdp mcp` (stdio) so any MCP-aware agent gets the same
  authenticated tools.

For the underlying HTTP API (endpoints, App Key vs OAuth, scopes, errors) see
[docs/REST_API.md](./docs/REST_API.md). This file is about *driving the connector*.

---

## TL;DR for an agent

1. **Check auth first** — `khdp_auth_status` (MCP) or `khdp status` (CLI).
2. If `authenticated=false` *and* the work needs user identity, **ask the
   user to run `khdp login` in their own terminal.** Login opens a browser
   for the PKCE flow; never try to collect credentials yourself.
3. If `is_expired=true` and `has_refresh_token=true`, call `khdp_auth_refresh`
   (or `khdp refresh`).
4. For **public-dataset / headless** work, no PKCE login is needed:
   - set `KHDP_TOKEN=khdp_pat_…` (issued from KHDP web UI Settings →
     Account → API Token) and call with `auth="api_key"`, **or**
   - set `KHDP_APP_SECRET` and call with `auth="app_key"`.
5. Make KHDP calls via `khdp_api_request` (MCP) / `khdp api …` (CLI), or
   the typed subcommands (`khdp datasets …`, `khdp submissions …`).
6. Treat all dataset content as PHI-equivalent (see [Conventions](#conventions)).

---

## Configuration

One-time setup needs a KHDP-registered `app_id` (UUID). For OAuth PKCE the
app must allow a loopback redirect (`http://127.0.0.1:*/callback`).

Resolution order (highest first):

1. `KHDP_*` environment variables
2. `khdp.local.toml` in the current directory
3. `~/.config/khdp/config.toml` (platform user-config dir)
4. Built-in defaults

```toml
# ./khdp.local.toml
app_id   = "00000000-0000-0000-0000-000000000000"
# app_secret = "..."        # optional: App Key auth (X-App-Id / X-App-Secret)
# api_key    = "khdp_pat_…" # optional: personal API key (Authorization: Bearer)
api_base = "https://khdp.net/_api"   # default; override for staging
```

| Env var | Purpose |
| --- | --- |
| `KHDP_APP_ID` | registered app UUID |
| `KHDP_APP_SECRET` | App Key secret → headless `X-App-Id`/`X-App-Secret` auth |
| `KHDP_TOKEN` | personal API key (`khdp_pat_…`) → `Authorization: Bearer` |
| `KHDP_API_BASE` | API base (default `https://khdp.net/_api`) |
| `KHDP_AUTHORIZE_URL` | override the PKCE authorize URL (else derived) |
| `KHDP_TOKEN_DIR` | where tokens are cached |
| `KHDP_USE_KEYRING` | `0/false` to disable OS keychain |

`khdp config` prints the resolved configuration (credential presence only,
never the values).

---

## CLI reference

```bash
# auth / housekeeping
khdp login                 # OAuth PKCE; opens the browser to KHDP login
khdp login --no-browser    # print the URL instead (headless / remote)
khdp status                # is a token cached? when does it expire?
khdp refresh               # rotate the refresh token now
khdp logout                # delete cached tokens
khdp token [--raw]         # print the access token (handle with care)
khdp config                # show resolved configuration

# datasets (public)
khdp datasets list [--query KW] [--policy open|restricted|...] [--page N] [--limit N] [--json]
khdp datasets show <code>[@<version>] [--json]
khdp datasets files <code>[@<version>] [--key PREFIX] [--json]
khdp datasets download-link <code>[@<version>] --key FILE
khdp datasets download <code>[@<version>] [--out DIR] [--max-pages N] [--dry-run]

# submissions (user's own; scaffold — per-command bodies land in a follow-up)
khdp submissions ...

# escape hatch — any authenticated KHDP call
khdp api METHOD PATH [--query KEY=VAL ...] [--data '<json>']
                     [--auth {auto,app-key,api-key,oauth}]

# MCP server
khdp mcp                   # or: khdp-mcp
```

`<code>` alone in `datasets` commands defaults to `@latest`; pin with
`<code>@1.0.0`. `--auth` selects the credential per call:

- `auto` (default) — picks **api-key → oauth (cached) → app-key**
- `app-key` — authenticates the *app* via `X-App-Id`/`X-App-Secret`
- `api-key` — sends the user's personal `KHDP_TOKEN` as `Authorization: Bearer`
  (long-lived, no PKCE refresh)
- `oauth` — sends the cached PKCE token (short-lived, refreshed transparently)

CLI output is JSON on stdout; status/errors go to stderr. Exit code is
non-zero on HTTP failure.

---

## Python library

```python
from khdp import Session

with Session.open() as s:
    s.login()                     # opens browser; or login(open_browser=printer)
    print(s.status())             # auth state
    token = s.access_token()      # valid token, auto-refresh

    # OAuth (PKCE) — cached token after `khdp login`
    r = s.authed_request("GET", "/open/datasets/KHDP-OPEN-001/latest/files",
                         auth="oauth")

    # App Key — `X-App-Id` / `X-App-Secret`; authenticates the app
    r = s.authed_request("GET", "/open/datasets", auth="app_key")

    # API Key — `Authorization: Bearer <KHDP_TOKEN>`, no PKCE refresh
    r = s.authed_request("GET", "/open/datasets", auth="api_key")
```

`Session` (in `khdp.session`) is the high-level entry point: combines the
PKCE auth client and the token store, refreshes transparently in
`access_token()` / `authed_request()`. Use `request()` for the
anonymous-friendly variant (no error when no credential is configured).

Lower-level, re-exported from the top-level package:

```python
from khdp import (
    Config, load_config,      # configuration
    KhdpAuthClient,           # PKCE login / refresh
    TokenSet, TokenStore,     # token model + on-disk/keychain cache
    AuthError,                # raised on auth failure (alias: OAuthError)
)
```

---

## MCP server

```bash
khdp mcp        # or: khdp-mcp
```

Tools exposed on stdio:

| Tool | Args | Purpose |
| --- | --- | --- |
| `khdp_auth_status` | — | logged in? token expiry? (no network call) |
| `khdp_auth_refresh` | — | rotate the refresh token to extend the session |
| `khdp_auth_logout` | — | delete locally cached tokens |
| `khdp_api_request` | `method`, `path`, `query?`, `json?`, `auth?` | authenticated HTTP passthrough; `auth` = `auto`/`app_key`/`api_key`/`oauth` |

`khdp_api_request` resolves a relative `path` against `KHDP_API_BASE` and
applies the credential implied by `auth`. Use it for any KHDP endpoint that
lacks a dedicated tool — e.g.
`path="/open/datasets/<code>/<version>/files"`.

**There is deliberately no login tool.** PKCE login needs a browser session
on the user's machine; that flow must not run inside an LLM tool call. The
user runs `khdp login` out-of-band; the MCP server only reads the resulting
token cache.

Wire it up per agent:

```bash
# Claude Code
claude mcp add khdp -- khdp mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
# Codex CLI: append wrappers/codex/config.example.toml to ~/.codex/config.toml
# Gemini CLI: merge wrappers/gemini/settings.example.json into ~/.gemini/settings.json
```

---

## Calling the KHDP API

Endpoint paths, payloads, scopes, and errors live in
[docs/REST_API.md](./docs/REST_API.md). From an agent you reach them through
`khdp_api_request` / `khdp api` / the typed subcommands. Highlights:

- `GET /open/datasets` — search public datasets (anonymous OK).
- `GET /open/datasets/:code/:version/files` — file list (needs the app's
  `datasets` scope).
- `GET /open/datasets/:code/:version/files-download-link-all` — bulk
  presigned download URLs (Open-policy datasets only).
- `GET /open/dataset-submissions` and friends — the user's own submissions
  (OAuth identity required).

---

## Conventions

- **Never print or log the bearer token / App Secret / API key.** The
  connector attaches credentials for you.
- **Treat KHDP datasets as PHI-equivalent.** Do not echo identifiers, free
  text, or full rows into the conversation/transcript. Summarize.
- **PKCE login is the user's job.** If unauthenticated and user identity is
  needed, instruct the user to run `khdp login`; do not solicit credentials
  or open browsers from a tool call.
- **Read the error `message`.** KHDP returns a structured body
  (`statusCode`, `message`, `path`); a 403 almost always says exactly why
  (e.g. missing `datasets` scope, wrong auth type).
- **Prefer dedicated subcommands** (`khdp datasets …`) over
  `khdp_api_request` when they cover the operation.

---

## Troubleshooting

| Symptom | Cause → fix |
| --- | --- |
| `Not logged in` | user runs `khdp login` in a terminal |
| `invalid_grant` / "Invalid or expired refresh token" | refresh window expired → `khdp login` again |
| `403 App does not have datasets scope` | the app lacks `datasets` scope → ask KHDP ops |
| `403 Auth type "openApiApp" is not allowed` | App Key used on a submission endpoint → use OAuth |
| `400 Is Not Open Access Dataset` | external download is Open-policy only |
| `OAuth callback never arrived` | loopback port blocked / redirect URI not allowed for the app |

---

## Repo layout

```
src/khdp/
  cli.py            # `khdp` CLI (argparse dispatch)
  cli_datasets.py   # `khdp datasets …` subcommand group
  cli_submissions.py# `khdp submissions …` subcommand group
  mcp_server.py     # MCP server + tool definitions (`khdp mcp`)
  session.py        # Session: high-level auth + authed_request / request
  oauth.py          # KhdpAuthClient: PKCE login / refresh; TokenSet
  token_store.py    # TokenStore: keychain or 0600 JSON cache
  config.py         # Config + layered load_config()
wrappers/           # per-agent glue: claude-code (skill), codex, gemini
docs/
  REST_API.md       # KHDP external HTTP API reference
  i18n-manifest.json# canonical-EN → translation map (drives i18n stale check)
  example.khdp.local.toml
CHANGELOG.md        # release notes
```

Dev: `pip install -e '.[dev,keyring]'` then `pytest`. Lint/type: `ruff`,
`mypy`. Python ≥ 3.10.
