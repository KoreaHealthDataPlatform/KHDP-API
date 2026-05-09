# KHDP — Agent guide for OpenAI Codex CLI

This file follows the [`AGENTS.md`](https://agents.md) convention so any
Codex-style agent picks up KHDP-specific context without further setup.

## Authentication

KHDP uses a custom *appId / password / Bearer-token* scheme rather
than standard OAuth/OIDC. The `khdp-connector` MCP server (see
`config.example.toml` next to this file) exposes:

- `khdp_auth_status`  — check before doing anything else
- `khdp_auth_refresh` — rotate the refresh token to extend the session
- `khdp_auth_logout`  — delete locally cached tokens
- `khdp_api_request`  — authenticated HTTP passthrough

There is **no** `khdp_auth_login` MCP tool. Login requires a password
and is run by the user out-of-band: `khdp login` in their terminal.

## Workflow

1. Call `khdp_auth_status` first.
2. If `authenticated=false`, ask the user to run `khdp login` in a
   terminal and report back. Do not request the password yourself.
3. If `is_expired=true` and `has_refresh_token=true`, call
   `khdp_auth_refresh` before further calls.
4. Use `khdp_api_request` for any KHDP endpoint that does not yet
   have a dedicated MCP tool. Path is relative to `KHDP_API_BASE`
   (default `https://khdp.net/_api`).

## Conventions

- Never print the bearer token. The MCP layer attaches it for you.
- Treat KHDP datasets as PHI-equivalent: do not echo identifiers,
  free text, or full rows in the conversation.
- Use `khdp_result_pin` (when available) to snapshot results for IRB
  reproducibility — do not expect Codex's transcript alone to suffice.

## Troubleshooting

- "Not logged in" → user runs `khdp login` in their terminal.
- "Refresh Token Is Not Validate" (sic) → the refresh window has
  expired; user must `khdp login` again.
- 403 from `khdp_api_request` → the requested endpoint may be
  app-scoped (only callable from a specific KHDP-registered app's
  origin). Check the API path and `app_id` configuration.
