# KHDPConnector

Auth + MCP connector for the **Korea Health Data Platform (KHDP)**.

`khdp-connector` is a CLI-first Python package that handles login
against the KHDP central auth API and exposes the resulting Bearer
session through a Model Context Protocol (MCP) server. The same MCP
server backs thin wrappers for **Claude Code**, **OpenAI Codex CLI**,
and **Gemini CLI** so KHDP authentication looks the same across every
coding-agent surface.

> **Status:** alpha. APIs and tool names will move during Phase 0–1 of
> the [PLAN.md](./PLAN.md) roadmap.

## How it talks to KHDP

The connector uses KHDP's password-based auth API. It implements two
endpoints that are safe for headless / CLI use:

* `POST /_api/oauth/login {appId, redirectUrl, mail, password}` →
  `{accessToken, refreshToken, expireTime}`
* `POST /_api/member/refresh-token {refreshToken}` →
  same shape, rotated.

All subsequent KHDP API calls go out with `Authorization: Bearer
<accessToken>`.

```
┌────────────────────────────────────────────────────────────┐
│  Claude Code   ·   Codex CLI   ·   Gemini CLI   ·  …       │
│        │              │              │                      │
│        └──────── MCP (stdio JSON-RPC) ───────┐             │
│                                              ▼             │
│                                    khdp-connector (this)   │
│                                              │             │
│                                              ▼             │
│   POST /_api/oauth/login          POST /_api/member/...    │
│       (login + refresh)               (any KHDP endpoint)  │
│                          khdp.net                          │
└────────────────────────────────────────────────────────────┘
```

## Install

```bash
pipx install khdp-connector            # recommended; isolates from system Python
# or
pip install khdp-connector
# or with OS-keychain support:
pipx install 'khdp-connector[keyring]'
```

## One-time configuration

You need a KHDP-registered `app_id` (UUID) and a registered
`redirect_url`. Drop them into a config file or env vars:

```toml
# ./khdp.local.toml
app_id       = "00000000-0000-0000-0000-000000000000"
redirect_url = "https://example.org/khdp-cli"
api_base     = "https://khdp.net/_api"  # default; override for staging
```

…or:

```bash
export KHDP_APP_ID=00000000-0000-0000-0000-000000000000
export KHDP_REDIRECT_URL=https://example.org/khdp-cli
```

> **Don't have an `app_id` yet?** Coordinate with the KHDP team to
> register a CLI-class app. snuh.ai's public `app_id` won't work for
> the CLI — its `redirect_url` allowlist excludes anything outside
> `snuh.ai`.

## CLI usage

```bash
khdp login          # prompts for email + password (or use --email / --password-stdin)
khdp status         # is a token cached? when does it expire?
khdp refresh        # force a refresh-token rotation
khdp api GET /member/me              # authenticated KHDP API call
khdp logout         # delete cached tokens
khdp config         # print resolved configuration
khdp mcp            # run the MCP server on stdio (for agents)
```

Configuration resolution order (highest first):

1. `KHDP_*` environment variables
2. `khdp.local.toml` in the current working directory
3. `~/.config/khdp/config.toml` (or platform equivalent)
4. Built-in defaults

For non-interactive use:

```bash
KHDP_EMAIL=me@example.com khdp login --password-stdin <<< "$KHDP_PASSWORD"
```

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

Future tools (per [PLAN.md](./PLAN.md)) will add dataset I/O, OMOP
queries, audit log retrieval, and IRB result-pinning.

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

- **No secret in the binary.** The CLI ships only the user-provided
  `app_id`. There is no embedded client secret.
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

## Roadmap

See [PLAN.md](./PLAN.md) for the full roadmap. The current
implementation covers Phase 1 (auth) and a generic API passthrough.
Dataset I/O, OMOP analysis, and IRB-grade result pinning land in later
phases.

## License

Apache 2.0. See [LICENSE](./LICENSE).
