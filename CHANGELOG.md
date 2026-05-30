# Changelog

All notable changes to `khdp-connector`.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/)
and uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **`GET /REST_API.md`** on the `khdp.ai` gateway — 60-second
  edge-cached mirror of `docs/REST_API.md` from this repo's `main`,
  served from the canonical `khdp.ai` host alongside `/AGENTS.md`.

### Removed
- **`/v1/gpu/*` route on the gateway.** GPU rentals are not part of
  the `khdp.ai` surface; they continue to be served by the existing
  kgpu gateway at `api.kgpu.net/v1/*` directly. `KGPU_BASE` env var
  removed from `wrangler.toml`. CHANGELOG entry for 0.5.0 retained
  for history.

## [0.5.0] - 2026-05-30

### Changed
- **`DEFAULT_API_BASE` is now `https://khdp.ai/v1`** — the new
  AI-agent gateway (Cloudflare Worker, free tier) at <https://khdp.ai>.
  The Worker forwards `/v1/*` 1:1 to the existing
  `https://khdp.net/_api/*` backend, so all existing paths
  (`/open/datasets`, `/oauth/token`, `/external/oauth-login`, …) keep
  working unchanged. Users who explicitly set `KHDP_API_BASE` keep
  their value; only the implicit default changes.
- User-Agent bumped to `khdp/0.5.0` (CLI + `khdp pat new`).
- The agent-bootstrap prompt in all five language READMEs now points
  to `https://khdp.ai/AGENTS.md` (Cloudflare-fronted mirror) instead of
  the GitHub raw URL.

### Added
- `worker/` directory housing the `khdp-ai-gateway` Cloudflare Worker
  that serves <https://khdp.ai> (landing + `/AGENTS.md` proxy +
  `/v1/*` passthrough + `/healthz`). Auto-deploys on push to `main`.
- **`/v1/gpu/*` route** on the gateway → `api.kgpu.net/v1/*` (kgpu
  gateway on AWS auroc, brand-aligned URL). The `/gpu` segment is
  stripped; everything else (auth headers, query, body) passes
  through unchanged. Bytes for shell/exec stay on kgpu's existing
  SSH bastion at `ssh.kgpu.net:2222`.

## [0.4.0] - 2026-05-30

### Changed
- **Login is now OAuth 2.0 Authorization Code with PKCE** (RFC 7636)
  using a loopback redirect (RFC 8252 §7.3). The previous
  `mail + password` flow is preserved as commented-out reference but
  is no longer exposed in the CLI (`khdp login` opens a browser).
- `khdp login` accepts only `--no-browser` (prints the URL instead of
  launching one). `--email` / `--password-stdin` are removed.
- Token refresh now uses `POST /_api/oauth/refresh-token`
  (was `/member/refresh-token`).
- Token responses normalise `expires_in` (OAuth-standard) in addition
  to legacy `expireTime`.
- CLI dispatch switched to `args.func` so subparser groups can attach
  their own handlers; the previous `_DISPATCH` dict is gone.
- Auth modelled as three user-visible classes — `app_key` / `api_key` /
  `oauth` — selected per call via `--auth {auto,app-key,api-key,oauth}`.
  `auto` picks `api_key` → cached `oauth` → `app_key`.
- README rewritten as a promotion-first developer hub with four
  side-by-side Quick Start examples (curl / Python SDK / Claude Code
  MCP / Codex CLI).
- `REST_API.md` moved to `docs/REST_API.md` (git rename; history
  preserved). All sibling links updated.
- GitHub repo renamed `KHDPConnector` → `khdp-api`; PyPI package name
  unchanged (`khdp`). All `KHDPConnector` URL references in code and
  docs updated.
- **`KHDP_PAT` is the canonical env var** for personal access tokens.
  `KHDP_TOKEN` is kept as a **legacy alias** so existing setups keep
  working; both feed into `config.api_key` via the env-resolution
  layer, with `KHDP_PAT` winning when both are set.

### Added
- **Official KHDP CLI app baked in as default** — `Config.app_id` and
  `Config.authorize_url` default to the KHDP-registered PKCE public app
  (`d915a48e-…c1a34203f`) and `https://khdp.net/external/oauth-login`,
  so `khdp login` works without prior configuration. Override via env
  (`KHDP_APP_ID`, `KHDP_AUTHORIZE_URL`) or `khdp.local.toml` for staging
  / on-prem / own-app setups.
- `khdp config` output adds `authorize_url`, `has_app_secret`, and
  `has_api_key`.
- **PAT (Personal Access Token) support** — register a `khdp_pat_*`
  token issued from the KHDP web console and use it in place of the
  PKCE OAuth tokens. Unified with the existing `config.api_key` /
  `KHDP_TOKEN` path so any source — env (`KHDP_PAT` / `KHDP_TOKEN`),
  config TOML (`api_key = "khdp_pat_..."`), or the runtime store —
  works through the same `--auth api-key` / `auto` precedence.
  - `khdp pat set <token>` / `khdp pat status` / `khdp pat clear`
    (keyring + file fallback).
  - Precedence: `config.api_key` (env or TOML) → runtime store
    (`khdp pat set` / `khdp pat new`) → OAuth.
  - `khdp status` / `khdp pat status` report the active auth mode and
    PAT source.
- **`khdp pat new`** — issue a PAT in one step from an OAuth-logged-in
  CLI by calling `POST /oauth/api-tokens`; the new token is saved into
  the runtime store automatically. Options: `--name`, `--scopes <s>`
  (repeatable; omit for a super-PAT), `--expires-in-days N`,
  `--force` (revoke any existing active PAT instead of prompting),
  `--yes` / `-y` (auto-confirm the 409 overwrite prompt). Adds
  `Session.oauth_access_token()` for code paths that must not pick up a
  PAT.
- `khdp datasets` subcommand group:
  - `list`, `show`, `files`, `download-link`, `download`.
  - Ref form `<code>[@<version>]`; `<code>` alone defaults to `@latest`.
  - `download` paginates `files-download-link-all` (1000 keys/page),
    streams every file to `--out`, prints per-page + per-file progress
    (file count, byte totals formatted as KB/MB/GB).
  - `download --max-pages N` stops after N pages; `download --dry-run`
    lists keys/sizes without fetching.
- `khdp submissions` subcommand group — parser scaffolding only;
  per-command implementations land in a follow-up release.
- `config.authorize_url` (`KHDP_AUTHORIZE_URL`) overrides the KHDP web
  URL the browser is sent to during login.
- `Session.request()` for anonymous-allowed endpoints — uses the
  cached bearer if present, falls back to an anonymous call otherwise.
- `Session` re-exported at the `khdp` package root —
  `from khdp import Session` (the submodule path
  `from khdp.session import Session` continues to work).
- `docs/quickstart.en.md` — end-to-end walkthrough (install →
  configure → search → inspect → download → MCP) plus a common-gotchas
  table.
- Multilingual READMEs and Quickstart: **ko / es / zh-CN / ja**
  (AI-translated; each file carries an explicit "AI translation"
  notice and a `Last sync` line).
- i18n stale-check workflow + `docs/i18n-manifest.json`: PRs that
  change a tracked canonical EN doc without updating the matching
  translations get a sticky comment and an `i18n: stale` label.
- `examples/` directory with runnable artefacts that use the `khdp`
  SDK:
  - `examples/notebook/quickstart.ipynb` — Colab-ready tour
    (search → detail → auth → file listing → download).
  - `examples/python/01_anonymous_search.py`,
    `02_dataset_detail.py`,
    `03_authenticated_download.py`.

### Removed
- Stale `khdp_auth_login` MCP tool from the PLAN.md roadmap.
  Login is intentionally CLI-only (browser interaction required).

### Internal
- `_LoopbackCallbackHandler` HTTP server is now bound + listening
  *before* the browser is opened, removing a race where a fast
  redirect could arrive before the listener was up.
