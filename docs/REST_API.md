# KHDP External REST API

A practical, self-contained reference for the **Korea Health Data Platform
(KHDP)** external REST API — the HTTP surface that external services,
third‑party apps, CLIs, and AI agents use to search, download, and submit
datasets.

Any HTTP client works: `curl`, `fetch`, `requests`, `httpx`, etc. No SDK is
required. The [`khdp` connector](../README.md) in this repo is one convenience
wrapper over this API (CLI + Python library + MCP server); see
[AGENTS.md](../AGENTS.md) for the tool-driven path.

> **Canonical source.** The authoritative spec lives at
> <https://khdp.net/docs/external-api>. This file mirrors it for offline /
> in-repo use; if the two disagree, the official docs win.

---

## Base URL

| Environment | Base URL |
| --- | --- |
| Production (recommended) | `https://khdp.ai/v1` |
| Production (legacy alias) | `https://khdp.net/_api` |
| Test | (ask the KHDP ops team) |

`https://khdp.ai/v1/*` is a Cloudflare-fronted gateway that forwards 1:1
to `https://khdp.net/_api/*`. Either URL works for every endpoint listed
below; the `.ai` host is the canonical one and the entry point AI agents
are pointed at.

All paths below are relative to the base URL. Examples assume:

```bash
export BASE_URL="https://khdp.ai/v1"
```

---

## Authentication

There are **two** credential types plus an anonymous mode. They are not
better/worse — they target different scenarios.

| | Anonymous | App Key | OAuth (PKCE) |
| --- | --- | --- | --- |
| Acts as | nobody | **the app itself** | **a user** (app acts on their behalf) |
| Header(s) | none | `X-App-Id` + `X-App-Secret` | `Authorization: Bearer <jwt>` |
| Carries user identity | – | no | yes |
| User consent | – | none (ops approves the app) | per-app consent |
| Typical caller | public catalog browsing | sync bots, catalog mirrors, servers | analysis SaaS, CLI tools, MCP servers |

**One-liner:** App Key sees *"what this app may see publicly"*; OAuth sees
*"everything this app may touch as that user."*

### Personal API Key (PAT)

KHDP also issues a **personal API key** from the web UI (Settings → Account
→ API Token) as a `khdp_pat_*` token. It is sent as:

```
Authorization: Bearer khdp_pat_…
```

— i.e. the *same* header as an OAuth access token, but issued out-of-band
(one-click instead of the PKCE browser flow) and **long-lived** (no
refresh-token dance). One key per account; regenerate replaces.

Use this for AI tools / notebooks / scripts that want the user's identity
without running the PKCE flow each session. See KHDP's
[quickstart with AI tools](https://khdp.net/docs/external-api/quickstart-with-ai-tools).

### App Key

Two values issued by the KHDP ops team. Send both on every request.

```bash
export KHDP_APP_ID="<app_id>"
export KHDP_APP_SECRET="<secret_key>"

curl "$BASE_URL/datasets?page=1&limit=10" \
  -H "X-App-Id: $KHDP_APP_ID" \
  -H "X-App-Secret: $KHDP_APP_SECRET"
```

Best for headless server/batch/bot access to **public (Open-policy)**
datasets. Needs the `datasets` scope for file listing/download (see below).

### OAuth (PKCE, RFC 7636) — Authorization Code + Refresh Rotation

Use when you need the **user's identity** (their own dataset submissions,
uploads). Works for public clients with no client secret (mobile, desktop,
CLI). See the [OAuth flow](#oauth-flow-pkce) section for the full sequence.

```bash
export KHDP_TOKEN="<access_token>"

curl "$BASE_URL/datasets/<code>/<version>/files" \
  -H "Authorization: Bearer $KHDP_TOKEN"
```

> Keep tokens in env vars / a secret store, never in shell history, source,
> commits, or docs.

---

## Scopes & permission model

Authorization is gated by the **app's scopes**, applied on *both* call paths
(App Key and OAuth).

| App scope | Meaning |
| --- | --- |
| `datasets` | may call the datasets API (query + download) |
| `oauth` | may obtain OAuth tokens from users |

Scopes are currently granted by the ops team at app-approval time (a
self-service management screen is planned). The key rule:

> Even when calling with an **OAuth user token**, the **app that issued the
> token** must hold the `datasets` scope for download endpoints. The app
> gate is checked first, independently of user consent.

The only difference between the two call paths is *whose authority* clears
the same gate:

- **App Key** → app identity → public data only.
- **OAuth** → user identity → public data **plus the user's own resources**.

### Picking an auth method

1. Need to **create/modify/submit** datasets? → **OAuth** (required).
2. Otherwise, do you touch the **user's own** (non-public) data? → **OAuth**.
3. Public data only? → **App Key** (simplest). Anonymous works for
   search/detail.

> A user's CLI on their own PC is "a tool acting with the user's authority,"
> so it uses **OAuth** (PKCE + loopback redirect, RFC 8252) — not App Key.

---

## Datasets — query & download (`/datasets/*`)

| # | Method | Path | Anon | App Key | OAuth |
| --- | --- | --- | :---: | :---: | :---: |
| 1 | GET | `/datasets` | ✅ | ✅ | ✅ |
| 2 | GET | `/datasets/:code/:version` | ✅ | ✅ | ✅ |
| 3 | GET | `/datasets/:code/:version/files` | ❌ | ✅ | ✅ |
| 4 | GET | `/datasets/:code/:version/files/download-link` | ❌ | ✅ | ✅ |
| 5 | GET | `/datasets/:code/:version/files-download-link-all` | ❌ | ✅ | ✅ |

`:version` accepts a semver (`1.0.0`) or `latest`. File list/download require
the `datasets` scope. **Download links are issued for `accessPolicy=Open`
datasets only**; others return `400 Is Not Open Access Dataset`.

### 1. `GET /datasets` — search / list (anonymous OK)

Query params: `page` (default 1), `limit` (default 10, max 100), `query`
(keyword), `type` (`ciType`, repeatable), `accessPolicy`
(`0=Open,1=Restricted,2=Credentialed,3=ContributorReview`, repeatable).

```bash
curl "$BASE_URL/datasets?query=heart&accessPolicy=0&page=1&limit=20"
```

### 2. `GET /datasets/:code/:version` — detail (anonymous OK)

```bash
curl "$BASE_URL/datasets/KHDP-OPEN-001/1.0.0"
curl "$BASE_URL/datasets/KHDP-OPEN-001/latest"
```

### 3. `GET /datasets/:code/:version/files` — file list (`datasets` scope)

Query param: `key` (directory prefix; empty = root).

```bash
curl "$BASE_URL/datasets/KHDP-OPEN-001/1.0.0/files?key=imaging/" \
  -H "X-App-Id: $KHDP_APP_ID" -H "X-App-Secret: $KHDP_APP_SECRET"
```

### 4. `GET .../files/download-link` — single presigned URL (Open only)

Query param: `key` (required, file key).

```bash
curl "$BASE_URL/datasets/KHDP-OPEN-001/1.0.0/files/download-link?key=imaging/scan001.dcm" \
  -H "Authorization: Bearer $KHDP_TOKEN"
# → { "url": "https://..." }
```

GET the returned URL directly to download (the signature is in the URL — no
auth header needed).

### 5. `GET .../files-download-link-all` — bulk presigned URLs (Open only)

Paginates via `continueToken` (omit on first call; absent/`null` in the
response means last page).

```bash
curl "$BASE_URL/datasets/KHDP-OPEN-001/1.0.0/files-download-link-all" \
  -H "X-App-Id: $KHDP_APP_ID" -H "X-App-Secret: $KHDP_APP_SECRET"
```

```json
{
  "items": [
    { "key": "imaging/scan001.dcm", "url": "https://..." },
    { "key": "imaging/scan002.dcm", "url": "https://..." }
  ],
  "continueToken": "..."
}
```

---

## Dataset submissions — create/upload/submit (`/submissions/*`)

**OAuth only.** These touch the user's own resources; an App Key call returns
`403 Auth type "openApiApp" is not allowed for this endpoint`. You may only
operate on your own `code`/`version`.

| # | Method | Path |
| --- | --- | --- |
| 1 | GET | `/submissions/licenses` |
| 2 | GET | `/submissions` |
| 3 | POST | `/submissions` |
| 4 | POST | `/submissions/:code/:version/files/directory` |
| 5 | POST | `/submissions/:code/:version/files/presigned-url` |
| 6 | GET | `/submissions/:code/:version/files` |
| 7 | GET | `/submissions/:code/:version/files/download-url` |
| 8 | DELETE | `/submissions/:code/:version/files` |
| 9 | POST | `/submissions/:code/:version/submit` |
| 10 | GET | `/submissions/:code/:version` |

### Flow

```
POST /submissions                         → create (returns code, version)
POST .../:code/:version/files/directory       (option) → make a directory
POST .../:code/:version/files/presigned-url            → get an upload URL
PUT  <uploadUrl>                                        → upload the bytes (separate step)
GET  .../:code/:version/files                          → verify
POST .../:code/:version/submit                         → finalize (Writing → review)
```

Only `Writing`-stage submissions can be edited; after submit, use the KHDP
web UI. Field constraints (per the official docs): `title` ≤200, `version`
semver, `code` no `/ \ : * ? " < > |` or whitespace, `summary` ≤500,
`accessPolicy` ∈ `open`/`restricted`/`credentialed`/`contributor_review`.

---

## OAuth flow (PKCE) {#oauth-flow-pkce}

```
[prep]   code_verifier  = random 43–128 chars
         code_challenge = base64url(SHA256(code_verifier))

[authorize]  GET /oauth/authorize
               ?client_id=<app_id>&redirect_uri=<registered>
               &code_challenge=<challenge>&code_challenge_method=S256&state=<random>
             → user logs in + consents → redirect_uri?code=...&state=...

[token]      POST /oauth/token
               grant_type=authorization_code, code, code_verifier,
               client_id, redirect_uri
             → { access_token, refresh_token, expires_in }
```

### CLI / desktop — loopback redirect (RFC 8252)

Register a redirect URI like `http://127.0.0.1:<port>/callback`
(KHDP matches IP-literal loopbacks ignoring port). The tool spins up a
temporary localhost server to catch the callback. Prefer `127.0.0.1` /
`[::1]` over `localhost`.

### Refresh — rotation

```bash
curl -X POST "$BASE_URL/oauth/token" -H 'Content-Type: application/json' \
  -d '{"grant_type":"refresh_token","refresh_token":"<current refresh_token>"}'
# → { "access_token": "...", "refresh_token": "...", "expires_in": 3600 }
```

The refresh token is **one-time**: replace it with the new one from the
response; reusing the old one returns `400 invalid_grant` (theft detection).
Store both tokens in an OS keychain / credential store.

---

## Errors

All errors share this shape:

```json
{ "statusCode": 403, "timestamp": "2026-05-12T12:34:56.789Z",
  "path": "/datasets/KHDP-OPEN-001/1.0.0/files",
  "message": "App does not have datasets scope" }
```

| Status | Meaning | Common `message` → cause |
| --- | --- | --- |
| `400` | bad request / rule violation | `Is Not Open Access Dataset` (non-Open download) · `invalid_grant` (bad code/refresh or PKCE mismatch) · `version must be in format ...` |
| `401` | authentication failed | wrong App Secret / unknown App Id · expired or invalid OAuth token (refresh it) |
| `403` | authenticated but not allowed | `App does not have datasets scope` · `App is not approved` · `Auth type "openApiApp" is not allowed for this endpoint` (App Key on a submission endpoint → use OAuth) · `Auth type "anonymous" is not allowed ...` · accessing another user's resource |
| `404` | not found | `Dataset Not Found: <code>@<version>` (check code/version, must be published) |
| `409` | conflict | `Code is Duplicated` · `Directory Name [...] Is Exists` |
| `5xx` | server error | retry; if it persists, contact KHDP |

Troubleshooting quick hits:

- **401** → check header names/values, `Authorization: Bearer ` spacing,
  token expiry, and that the token matches the environment (test token vs
  prod base).
- **403** → read `message` first; verify the issuing app has `datasets`
  scope (applies to OAuth calls too); App Key cannot call submission
  endpoints.
- **400 Is Not Open Access Dataset** → external download is Open-only;
  verify `accessPolicy=open` via the dataset detail endpoint.

---

## Using this API through the `khdp` connector

The connector wraps the OAuth (PKCE), App Key, and API Key paths. See
[AGENTS.md](../AGENTS.md) for full agent usage. Quick map:

| Goal | Raw HTTP | Connector |
| --- | --- | --- |
| Call as the user (OAuth PKCE) | `curl -H "Authorization: Bearer <pkce_token>"` | `khdp api … --auth oauth` |
| Call as the user (API key) | `curl -H "Authorization: Bearer khdp_pat_…"` | `khdp api … --auth api-key` (`KHDP_TOKEN`) |
| Call as the app | `curl -H "X-App-Id: …" -H "X-App-Secret: …"` | `khdp api … --auth app-key` |
| User login (PKCE) | `GET /oauth/authorize` → `POST /oauth/token` | `khdp login` (`--no-browser` for headless) |
| Token refresh | `POST /oauth/token` (`refresh_token` grant) | `khdp refresh` (or auto on call) |
| Public dataset search/list/detail | `GET /datasets[...]` | `khdp datasets list / show` |
| Public dataset files / download | `GET /datasets/.../files[-download-link-all]` | `khdp datasets files / download` |
| From an AI agent | — | MCP tool `khdp_api_request` (optional `auth`) |
