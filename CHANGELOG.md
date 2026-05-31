# Changelog

All notable changes to `khdp-connector`.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/)
and uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed
- **Files endpoints reshaped to REST-canonical collection/member**:
  - `GET /datasets/{c}/{v}/files` — flat paginated list with `{key,
    size, url}` per item plus an `archive` block. Replaces the
    historical `files-download-link-all` name (which leaked the
    implementation into the URL).
  - `GET /datasets/{c}/{v}/files/{key}` — single file's presigned URL.
    `{key}` is the full S3 object key, slashes and all — the gateway
    accepts every path segment after `/files/` as the key, so
    `/files/imaging/scan001.dcm` works directly without `%2F` encoding.
    Replaces `files/download-link?key=`.
  The old long forms now return `404 LEGACY_PATH` pointing at the
  canonical replacement.
- **OpenAPI `FileListing` schema** introduced (renaming
  `BulkPresignedUrls`); `items[].size` is now documented (the backend
  has always returned it).
- **SDK `khdp datasets files`** uses `/files` and accumulates pages
  with `continueToken`. New flags: `--prefix STR` (client-side filter)
  and `--max-pages N`; the old `--key DIR` directory argument is gone.
- **SDK `khdp datasets download-link --key FOO`** now hits
  `/files/FOO` directly (no query param). `--key` flag preserved on
  the SDK surface for now.

### Removed
- **Directory-mode dataset file listing** (the previous
  `/datasets/{c}/{v}/files` returning `{subDirs, contents}`) is no
  longer reachable through khdp.ai. The same path now serves the flat
  collection.

### Added
- **`archive` block on dataset detail responses** — when a pre-built
  zip exists for the requested version, `GET /v1/datasets/{code}/
  {version}` now includes an `archive` object describing the download.
  Bearer-authenticated callers get the presigned `url` (plus
  `expiresAt` and `sizeBytes` when the backend supplies them);
  anonymous callers see `available: true` but no URL. When no zip
  exists or the requested version isn't the latest published, `archive`
  is `{ available: false, format: "zip" }`. The Worker resolves `cvId`
  via the backend's `/dataset/code/{code}` lookup and calls
  `/files/compress-check` and (auth-gated) `/files/compress-link` in
  parallel with the primary request — no separate endpoint needed.
- **`/v1/me` and `/v1/me/balance`** — read-only account endpoints
  exposed through the gateway. Worker rewrites `/v1/me` →
  `/_api/member/profile` and `/v1/me/balance` → `/_api/credit/my-balance`
  on the existing nstri-back backend; no backend changes required.
  OpenAPI gains an `Account` tag with `Member` and `CreditBalance`
  schemas (loose: backend may return additional fields). AGENTS.md
  TL;DR suggests calling `/v1/me` at session start to confirm auth +
  identify the caller.

## [0.6.0] - 2026-05-31

### Changed
- **API spec is now OpenAPI 3.1**, bundled into the Worker at
  `openapi/v1.json` and served at <https://khdp.ai/openapi.json>
  with a Redoc-rendered companion at <https://khdp.ai/docs>. The
  prose `docs/REST_API.md` is removed.
- **SDK internal paths switched to short canonical** —
  `cli_datasets.py`, `cli_submissions.py`, and tests now call
  `/datasets/*` and `/submissions/*` instead of the legacy
  `/open/datasets/*` and `/open/dataset-submissions/*`. Consequence:
  SDK 0.6.0 only works against `https://khdp.ai/v1`; users who pin
  `KHDP_API_BASE` to the legacy `https://khdp.net/_api` should stay
  on SDK 0.5.x until that base is deprecated.
- `AGENTS.md` now tells agents to fetch the OpenAPI spec from
  <https://khdp.ai/openapi.json> at session start instead of reading
  the deleted REST_API.md.
- 5 language READMEs, 5 quickstarts, examples (Python scripts +
  Colab notebook), and the `examples/README.md` all point at
  <https://khdp.ai/docs> and <https://khdp.ai/openapi.json>.
- User-Agent bumped to `khdp/0.6.0`.

### Added
- `worker/src/index.ts` imports `openapi/v1.json` and serves it at
  `/openapi.json` + a small Redoc HTML at `/docs` and `/docs/`.
  Vitest covers both routes.

### Removed
- `docs/REST_API.md` (replaced by OpenAPI 3.1 spec).
- `GITHUB_REST_API_RAW` env var from `worker/wrangler.toml`.
- `/REST_API.md` route from the Worker.

## [Unreleased — pre-0.6.0 worker-only entries]

### Changed
- **Legacy long-form paths now hard-rejected.** The Worker returns
  `404 LEGACY_PATH` for `/v1/open/*` and `/v1/external/*` with a
  `canonical` field naming the short-form replacement
  (`/v1/open/datasets` → `/v1/datasets`, `/v1/open/dataset-submissions`
  → `/v1/submissions`, `/v1/external/oauth-login` →
  `/v1/oauth/authorize`). Previously these slipped through the
  passthrough; the surface is now strictly the documented short paths.
- **Short canonical paths on `/v1/*`.** The Worker rewrites the
  AI-agent-facing surface onto nstri-back's longer legacy paths so
  external docs can use the cleaner short names. khdp.ai is not yet
  public, so no back-compat is provided for the old long forms:
  - `/v1/datasets/*`     → backend `/_api/open/datasets/*`
  - `/v1/submissions/*`  → backend `/_api/open/dataset-submissions/*`
  - `/v1/oauth/authorize` → 302 redirect to `khdp.net/external/oauth-login`
    (browser-facing login page, lives at the web root not under `/_api`).
  `/v1/oauth/{token,refresh-token,api-tokens}` keep matching the
  backend path 1:1.
- `docs/REST_API.md`, `AGENTS.md`, and all five language READMEs now
  document the short canonical paths.
- New `WEB_BASE` env var in `worker/wrangler.toml` (`https://khdp.net`)
  for the OAuth authorize redirect.

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
