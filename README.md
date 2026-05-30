# KHDPConnector

Auth + MCP connector for the **Korea Health Data Platform (KHDP)**.

`khdp` is a CLI-first Python package that:

- handles login against the KHDP central auth API,
- exposes the authenticated surface through a Model Context Protocol
  (MCP) server (4 tools),
- comes with thin wrappers for **Claude Code**, **OpenAI Codex CLI**,
  and **Gemini CLI** so the experience is uniform across coding agents.

For the raw HTTP API (endpoints, payloads, scopes, errors) see
[REST_API.md](./REST_API.md). For agent/tool usage see
[AGENTS.md](./AGENTS.md).

> **Note (2026-05):** the previously bundled SNUH SuperTable Python
> client (`khdp.supertable`) has been removed. SNUH SuperTable is now
> a plain HTTPS service that exposes its own AGENTS.md and JSON
> endpoints — any HTTP client (curl, requests, fetch) can use it
> directly, no library required.

## How it talks to KHDP

The connector authenticates against KHDP via the **OAuth 2.0
Authorization Code flow with PKCE** (RFC 7636), using a **loopback
redirect** (RFC 8252 §7.3) so the CLI can capture the auth code on the
user's own machine without exposing a password to the CLI process or
the LLM context.

* `GET <khdp web>/external/oauth-login?appId&redirectUrl&codeChallenge&...`
  -- the user's browser is sent here. KHDP's web UI handles login and
  consent, then redirects to `http://127.0.0.1:<port>/callback?code=...`.
* `POST /_api/oauth/token        {code, appId, codeVerifier}` -- the
  CLI exchanges the authorization code for a Bearer token pair.
* `POST /_api/oauth/refresh-token {appId, refreshToken}` -- rotate an
  expired access token.

All subsequent KHDP API calls go out with `Authorization: Bearer
<accessToken>`.

The connector supports the three KHDP credential classes:

* **App Key** (authenticates the *app*, not a user) — `X-App-Id` /
  `X-App-Secret`. Manual issuance via the KHDP team. Set `app_secret`
  (`KHDP_APP_SECRET`) alongside `app_id`.
* **API Key** (per-user personal token, long-lived, **no PKCE refresh**) —
  `Authorization: Bearer khdp_pat_…`. Issued from KHDP Settings → Account
  → API Token; set `KHDP_TOKEN` and the connector uses it directly with no
  `khdp login`.
* **OAuth** (per-user, browser interaction, short-lived) —
  `Authorization: Bearer <access_token>`. Obtain via `khdp login` (PKCE);
  the connector refreshes the rotated token transparently.

Pick a credential per call with
`khdp api --auth {auto,app-key,api-key,oauth}` — default `auto` picks:
**api-key → oauth (cached) → app-key**.

```
┌────────────────────────────────────────────────────────────┐
│  Claude Code   ·   Codex CLI   ·   Gemini CLI   ·  …       │
│        │              │              │                      │
│        └──────── MCP (stdio JSON-RPC) ───────┐             │
│                                              ▼             │
│                                    khdp-connector (this)   │
│                                              │             │
│   khdp login (PKCE / browser)                │             │
│                                              ▼             │
│   POST /_api/oauth/token       POST /_api/oauth/...        │
│        (auth-code → tokens)         (any KHDP endpoint)    │
│                          khdp.net                          │
└────────────────────────────────────────────────────────────┘
```

## Install

```bash
pipx install khdp            # recommended; isolates from system Python
# or
pip install khdp
# or with OS-keychain support:
pipx install 'khdp[keyring]'
```

## One-time configuration

You need a KHDP-registered `app_id` (UUID). The CLI uses a loopback
redirect (`http://127.0.0.1:<port>/callback`) -- the KHDP backend
matches IP-literal loopbacks ignoring port, so a single registered
loopback entry on the app is enough.

```toml
# ./khdp.local.toml
app_id   = "00000000-0000-0000-0000-000000000000"
# app_secret = "..."        # optional: App Key auth (X-App-Id / X-App-Secret)
# api_key    = "khdp_pat_…" # optional: personal API key (Authorization: Bearer)
api_base   = "https://khdp.net/_api"  # default; override for staging
```

…or:

```bash
export KHDP_APP_ID=00000000-0000-0000-0000-000000000000
export KHDP_APP_SECRET=...   # optional (App Key)
export KHDP_TOKEN=khdp_pat_… # optional (API Key — from KHDP Settings → API Token)
```

> **Don't have an `app_id` yet?** Coordinate with the KHDP team to
> register a CLI-class app with `http://127.0.0.1:*/callback` listed
> as an allowed redirect URL.

## CLI usage

### Auth + housekeeping
```bash
khdp login          # PKCE: opens the browser to the KHDP login page,
                    # captures the redirect on a local loopback server
khdp login --no-browser   # print the URL instead (headless / remote)
khdp status         # is a token cached? when does it expire?
khdp refresh        # force a refresh-token rotation
khdp logout         # delete cached tokens
khdp config         # print resolved configuration
khdp mcp            # run the MCP server on stdio (for agents)
```

### Datasets
```bash
khdp datasets list [--query KW] [--policy open|restricted|...] [--page N] [--limit N] [--json]
khdp datasets show <code>[@<version>] [--json]
khdp datasets files <code>[@<version>] [--key PREFIX] [--json]
khdp datasets download-link <code>[@<version>] --key FILE
khdp datasets download <code>[@<version>] [--out DIR] [--max-pages N] [--dry-run]
```

* `<code>` alone defaults to `@latest`. `<code>@1.0.0` pins a version.
* `download` paginates the server's `files-download-link-all`
  (1000 keys per page) and streams every file to `--out`. Use
  `--dry-run` to list keys/sizes without fetching; use `--max-pages N`
  to stop early when only verifying the flow.

### Submissions (scaffold)
Parser is wired but per-command implementations land in a follow-up
commit. `khdp submissions <cmd>` currently prints `not implemented yet`.

### Escape hatch
```bash
khdp api METHOD PATH [--query KEY=VAL ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```
Use this for any endpoint not covered by a verb above (debugging,
ops-only routes, …). Output is raw JSON on stdout, status on stderr.

Configuration resolution order (highest first):

1. `KHDP_*` environment variables
2. `khdp.local.toml` in the current working directory
3. `~/.config/khdp/config.toml` (or platform equivalent)
4. Built-in defaults

## MCP server

```bash
khdp mcp
# or
khdp-mcp
```

Tools exposed on `stdio`:

| Tool | Purpose |
| --- | --- |
| `khdp_auth_status`  | Is the user logged in? When does the token expire? |
| `khdp_auth_refresh` | Rotate the refresh token to extend the session. |
| `khdp_auth_logout`  | Delete locally cached tokens. |
| `khdp_api_request`  | Authenticated HTTP passthrough to the KHDP API. |

The MCP server **never** accepts a password through tool arguments —
passwords would otherwise flow through the LLM context window. Login
is initiated out-of-band via `khdp login` in the user's terminal; the
MCP server just reads the resulting token cache.

## Wrappers

The same MCP server backs a thin wrapper per agent platform.

### Claude Code

```bash
claude mcp add khdp -- khdp mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

### OpenAI Codex CLI

Append `wrappers/codex/config.example.toml` to `~/.codex/config.toml`,
copy `wrappers/codex/AGENTS.md` to your project root.

### Gemini CLI

Merge `wrappers/gemini/settings.example.json` into
`~/.gemini/settings.json`, or install as a Gemini Extension under
`.gemini/extensions/khdp/`.

## Development

```bash
git clone https://github.com/KoreaHealthDataPlatform/KHDPConnector.git
cd KHDPConnector
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## Security model

- **No secret in the binary.** Any credentials (`app_secret`, `api_key`,
  refresh tokens) are user-provided config — never embedded. PKCE login
  needs no client secret at all.
- **Password never leaves the local machine** unencrypted; it goes
  only to KHDP's TLS endpoint, never to the LLM, never to the MCP
  context. The MCP tool surface deliberately omits a password
  argument.
- **Per-app token isolation.** Multiple KHDP apps on one machine are
  kept separate by `app_id`.
- **Token storage.** OS keychain (Keychain / Credential Manager /
  Secret Service) when the `keyring` extra is installed; otherwise a
  JSON file with `0600` permissions in the platform user-config dir.
- **No revocation endpoint exposed by KHDP today.** `khdp logout` only
  clears local state. Access tokens expire naturally; refresh tokens
  go invalid the next time the access token is rotated.

## License

MIT. See [LICENSE](./LICENSE).
