# Security policy

## Reporting a vulnerability

If you believe you've found a security issue in `khdp` or in the way
it interacts with the Korea Health Data Platform, **please do not
open a public GitHub issue**.

Instead, email **vital@snu.ac.kr** with:

- A clear description of the issue and its impact.
- Steps to reproduce, including the affected version of `khdp` and
  the KHDP environment (production / staging / on-prem).
- Any proof-of-concept code or logs (with PHI redacted).

We will acknowledge receipt within 5 business days and aim to provide
a fix or coordinated disclosure plan within 30 days for high-severity
issues.

## Scope

In scope:

- The `khdp` CLI / MCP server code in this repository.
- Token storage, refresh, and revocation handling.
- The wrapper configurations under `wrappers/` to the extent they
  affect what is sent across MCP boundaries.

Out of scope (please report to the relevant owner instead):

- KHDP backend vulnerabilities — report directly to KHDP operations
  via the same address; we will route as needed.
- Vulnerabilities in upstream dependencies (`httpx`, `mcp`, etc.) —
  please report upstream first; we'll bump versions on disclosure.
- Vulnerabilities in third-party AI coding agents (Claude Code,
  Codex CLI, Gemini CLI). Use their respective channels.

## Hardening checklist (for users)

- Always install via `pipx` or a per-project venv to keep the CLI
  isolated from your system Python.
- Use the `keyring` extra so refresh tokens go to the OS keychain
  rather than a JSON file.
- Never commit `khdp.local.toml` if you put a real `app_id` in it
  (the file is `.gitignore`d by default).
- Rotate refresh tokens by re-running `khdp login` after any incident
  on your machine; KHDP does not currently expose an explicit
  revocation endpoint, so local rotation is your strongest control.
- For CI usage, prefer environment variables (`KHDP_EMAIL`,
  `KHDP_PASSWORD`) sourced from a secrets manager. Never hard-code
  credentials into workflow files.

## What `khdp` will never do

- Print bearer tokens, refresh tokens, or passwords to stdout in the
  default verbosity. (`khdp token --raw` prints the access token only
  when explicitly asked.)
- Send credentials anywhere other than the configured KHDP API base.
- Accept passwords through the MCP tool surface — passwords would
  otherwise flow through the LLM context window.
