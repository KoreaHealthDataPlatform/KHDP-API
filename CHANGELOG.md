# Changelog

All notable changes to `khdp-connector`.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/)
and uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-05-29

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

### Added
- **PAT (Personal Access Token) support** — register a token issued
  from the KHDP web console (`khdp_pat_*`) and use it instead of the
  PKCE OAuth tokens.
  - `khdp pat set <token>` / `khdp pat status` / `khdp pat clear`
    (keyring + file fallback).
  - `KHDP_PAT` env variable; precedence: `env` → store → OAuth.
  - PAT 가 있으면 `Session.access_token()` 이 PAT 를 그대로 반환
    (refresh / expiry 처리 없음 — PAT 자체가 장기 토큰).
  - `khdp status` / `khdp pat status` 에 현재 활성 인증 모드 표시.
- **`khdp pat new`** — OAuth 로그인 한 상태에서 `POST /oauth/api-tokens`
  를 호출해 PAT 를 발급 + 즉시 keyring/파일에 저장한다.
  - 옵션: `--name` / `--scopes <s>` (반복) / `--expires-in-days N`.
  - scope 생략 시 super-PAT (모든 권한 통과) 로 발급.
  - 1인 1 PAT 정책 — 기존 active 가 있으면 서버가 409 + existingPrefix
    응답. CLI 가 prefix 안내 후 confirm 받는다.
  - `--force` 는 처음부터 `?force=true` 로 호출, `--yes` 는 409
    prompt 자동 승인.
  - `Session.oauth_access_token()` (PAT 무시, OAuth 토큰만) 추가.
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

### Removed
- Stale `khdp_auth_login` MCP tool from the PLAN.md roadmap.
  Login is intentionally CLI-only (browser interaction required).

### Internal
- `_LoopbackCallbackHandler` HTTP server is now bound + listening
  *before* the browser is opened, removing a race where a fast
  redirect could arrive before the listener was up.
