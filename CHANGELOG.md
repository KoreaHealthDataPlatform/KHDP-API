# Changelog

All notable changes to `khdp-connector`.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/)
and uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Added
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
  URL the browser is sent to during login. Default is derived from
  `api_base` host with `/external/oauth-login`.
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
