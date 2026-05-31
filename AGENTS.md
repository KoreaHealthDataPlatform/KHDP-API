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

For the underlying HTTP API (endpoints, OAuth, scopes, errors)
**fetch the machine-readable OpenAPI 3.1 spec at <https://khdp.ai/openapi.json>**
or browse the human-readable Redoc page at <https://khdp.ai/docs>. This
file is about *driving the connector*.

---

## TL;DR for an agent

1. **Check auth first** — `khdp_auth_status` (MCP) or `khdp status` (CLI). Once authenticated, a single `GET /v1/me` confirms identity and `GET /v1/me/balance` shows the user's credit balance — useful as a session-start sanity check.
2. If `authenticated=false` *and* the work needs user identity,
   **don't silently pick a path — ask the user which they prefer**
   (see [Asking the user how to authenticate](#asking-the-user-how-to-authenticate)):
   - **OAuth (browser)** — they run `khdp login`; short-lived token,
     auto-refreshed. Best for interactive sessions.
   - **PAT** — long-lived `khdp_pat_*` token. **Issued only from the
     KHDP web UI** at <https://khdp.net> → *Settings → Account → API
     Token*; the user pastes it back and the agent runs `khdp pat set`
     to cache it locally. Best for notebooks, background work,
     headless setups.
   Never try to collect credentials yourself or open a browser from a
   tool call.
3. If `is_expired=true` and `has_refresh_token=true`, call `khdp_auth_refresh`
   (or `khdp refresh`).
4. *(Advanced)* App-developer credentials (`X-App-Id` + `X-App-Secret`,
   `--auth app-key`) exist for headless/server-to-server work but are
   **not part of the public agent surface** — they're confusing for
   end users and are reserved for ops-coordinated integrations. Stick
   to OAuth or PAT for everything user-facing.
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
# api_key    = "khdp_pat_…" # optional: personal API key (Authorization: Bearer)
api_base = "https://khdp.ai/v1"      # default; alias of khdp.net/_api
```

| Env var | Purpose |
| --- | --- |
| `KHDP_APP_ID` | registered app UUID (defaults to the official KHDP CLI app) |
| `KHDP_PAT` | personal access token (`khdp_pat_…`) → `Authorization: Bearer`. **Canonical** env var |
| `KHDP_APP_SECRET` | *(advanced)* app-developer headless auth; not part of the public surface |
| `KHDP_TOKEN` | legacy alias of `KHDP_PAT` (still recognised; `KHDP_PAT` wins if both are set) |
| `KHDP_API_BASE` | API base (default `https://khdp.ai/v1`, an alias of `https://khdp.net/_api`) |
| `KHDP_AUTHORIZE_URL` | override the PKCE authorize URL (defaults to `https://khdp.net/external/oauth-login`) |
| `KHDP_TOKEN_DIR` | where tokens are cached |
| `KHDP_USE_KEYRING` | `0/false` to disable OS keychain |

`khdp config` prints the resolved configuration (credential presence only,
never the values).

---

## Asking the user how to authenticate

When `khdp_auth_status` returns `authenticated=false` and the work
genuinely needs the user's identity (anything beyond anonymous dataset
search), **do not silently pick a path**. Surface both options to the
user and let them choose:

> KHDP needs you to authenticate. Two options:
>
> 1. **Browser login (OAuth / PKCE)** — run `khdp login` in your
>    terminal. The KHDP login page opens; sign in once and the token is
>    cached locally. Short-lived; refreshes automatically.
>
> 2. **Personal Access Token (PAT)** — a long-lived `khdp_pat_*` token.
>    Issuance is web-only: open <https://khdp.net> → *Settings →
>    Account → API Token*, issue/regenerate a token, paste it back to
>    me and I'll run `khdp pat set <token>` to save it locally.
>
> Which would you like?

(Phrase it in whatever language the user is conversing in.)

Default recommendation when the user doesn't have a preference:

- **OAuth** for interactive, one-shot sessions where the user is at
  their terminal anyway.
- **PAT** for notebooks, background/CI work, anything that should
  outlive a single shell session, or remote sessions where opening a
  local browser is awkward.

After the user chooses:

- **OAuth** → tell them to run `khdp login`; wait for confirmation,
  then re-check `khdp_auth_status`.
- **PAT (web-issued)** → ask them to paste the `khdp_pat_…` string; run
  `khdp pat set <token>` for them.
> Note: an older `khdp pat new` CLI subcommand exists that calls a
> backend OAuth-protected issuance endpoint. It is **not part of the
> public API surface** documented in <https://khdp.ai/openapi.json>
> and may be removed in a future release. New integrations should rely
> on web-UI-issued PATs.

For one-off shell injection without persisting anything,
`KHDP_PAT=khdp_pat_… khdp api …` works too (`KHDP_TOKEN` is the legacy
alias for the same).

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
    r = s.authed_request("GET", "/datasets/KHDP-OPEN-001/latest/files",
                         auth="oauth")

    # (Advanced) App Key — `X-App-Id` / `X-App-Secret`; authenticates the
    # app, not a user. Not part of the public surface; reserved for
    # ops-coordinated server-to-server integrations.
    # r = s.authed_request("GET", "/datasets", auth="app_key")

    # API Key — `Authorization: Bearer <KHDP_TOKEN>`, no PKCE refresh
    r = s.authed_request("GET", "/datasets", auth="api_key")
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
`path="/datasets/<code>/<version>/files"`.

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

Endpoint paths, payloads, scopes, and errors are described by the
canonical **OpenAPI 3.1** spec at <https://khdp.ai/openapi.json>
(human-readable Redoc at <https://khdp.ai/docs>). Agents should fetch
the spec once at session start — it lists every method, parameter,
required scope, and response schema, including the `Error` shape with
`statusCode` / `errorCode` / `message` / `requestId`. From an agent
you reach them through `khdp_api_request` / `khdp api` / the typed
subcommands. Highlights:

- `GET /datasets` — search public datasets (anonymous OK).
- `GET /datasets/:code/:version/files` — file list (needs the app's
  `datasets` scope).
- `GET /datasets/:code/:version/files-download-link-all` — bulk
  presigned download URLs (Open-policy datasets only).
- `GET /submissions` and friends — the user's own submissions
  (OAuth identity required).

---

## Conventions

- **Never print or log the bearer token / App Secret / API key.** The
  connector attaches credentials for you.
- **Treat KHDP datasets as PHI-equivalent.** Do not echo identifiers, free
  text, or full rows into the conversation/transcript. Summarize.
- **Authentication is the user's choice.** If unauthenticated and user
  identity is needed, ask which path they prefer (OAuth via `khdp login`
  vs. PAT issued from the KHDP web UI) — see
  [Asking the user how to authenticate](#asking-the-user-how-to-authenticate).
  Do not solicit credentials or open browsers from a tool call.
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
  i18n-manifest.json# canonical-EN → translation map (drives i18n stale check)
  example.khdp.local.toml
  quickstart.{en,ko,es,zh-CN,ja}.md
openapi/
  v1.json           # OpenAPI 3.1 spec, served at khdp.ai/openapi.json + khdp.ai/docs
worker/             # Cloudflare Worker fronting khdp.ai (gateway + spec hosting)
CHANGELOG.md        # release notes
```

Dev: `pip install -e '.[dev,keyring]'` then `pytest`. Lint/type: `ruff`,
`mypy`. Python ≥ 3.10.
