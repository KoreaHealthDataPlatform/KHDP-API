# khdp-ai-gateway

Cloudflare Worker fronting **`khdp.ai`** — the AI-agent entry point for the Korea Health Data Platform.

| Path | Behaviour |
| --- | --- |
| `GET /` | Minimal landing page pointing agents at `/AGENTS.md`. |
| `GET /AGENTS.md` | 60-second edge-cached mirror of [`AGENTS.md`](../AGENTS.md) from this repo's `main`. |
| `GET /openapi.json` | Bundled [OpenAPI 3.1 spec](../openapi/v1.json) for the API. Updated on every Worker deploy. |
| `GET /docs` | Redoc HTML page rendering `/openapi.json`. |
| `ANY /v1/*` | Short-canonical surface. `/v1/datasets/*` → `/_api/open/datasets/*`, `/v1/submissions/*` → `/_api/open/dataset-submissions/*`, `/v1/oauth/authorize` → 302 to `khdp.net/external/oauth-login`. Other `/v1/oauth/*` pass through 1:1. `/v1/open/*` and `/v1/external/*` return `404 LEGACY_PATH`. |
| `GET /healthz` | Liveness probe. |

Bytes (dataset downloads/uploads) never transit this Worker — KHDP returns presigned URLs that the client fetches directly from the origin object store.

## Local development

```bash
cd worker
npm install
npm run dev              # http://localhost:8787 — wrangler dev
```

Try:

```bash
curl http://localhost:8787/
curl http://localhost:8787/AGENTS.md    | head -5
curl http://localhost:8787/openapi.json | head -20
curl http://localhost:8787/docs         | head -10
curl 'http://localhost:8787/v1/datasets?query=heart&limit=2'
```

## Deploy

Manual:

```bash
export CLOUDFLARE_API_TOKEN=...      # token with Workers:Edit + Account:Read
npm run deploy                       # → workers.dev subdomain
```

CI (preferred): `.github/workflows/worker-deploy.yml` deploys on any push to `main` that changes `worker/**`. Requires the `CLOUDFLARE_API_TOKEN` repo secret.

## Custom domain (post-activation)

`khdp.ai` zone must be `active` in Cloudflare (NS migration complete). Then uncomment the `[[routes]]` blocks in `wrangler.toml`:

```toml
[[routes]]
pattern = "khdp.ai"
custom_domain = true

[[routes]]
pattern = "www.khdp.ai"
custom_domain = true
```

Re-run `npm run deploy`. Wrangler creates the custom-domain binding automatically.

## Configuration

`wrangler.toml` `[vars]`:

| Var | Default | Purpose |
| --- | --- | --- |
| `GITHUB_AGENTS_RAW` | `raw.githubusercontent.com/KoreaHealthDataPlatform/khdp-api/main/AGENTS.md` | Source for `/AGENTS.md` proxy. Point at a tag to pin. |
| `BACKEND_BASE` | `https://khdp.net/_api` | Upstream the `/v1/*` gateway forwards to. |
| `WEB_BASE` | `https://khdp.net` | Used by the `/v1/oauth/authorize` 302 redirect. |

The OpenAPI spec at `openapi/v1.json` is bundled into the Worker via `import` and served at `/openapi.json`. To update it, edit `openapi/v1.json` and redeploy — the next push to `main` triggers `worker-deploy.yml`.

No secrets are bound today. When per-call PAT introspection or token signing keys land, use `wrangler secret put <NAME>` and reference via `env.<NAME>`.

## Operations notes

- **Hop-by-hop headers** are stripped on both directions (`Connection`, `Transfer-Encoding`, `Host`, etc.).
- **Errors** thrown anywhere in the handler return `502` with `{ statusCode, errorCode: "GATEWAY_ERROR", message, requestId }`. Logs go to Workers Observability.
- **CORS** is permissive (`*`) for `/v1/*` so browser-based notebooks can call directly. Tighten when the API surface stabilises.
- **No mutating state** in the Worker itself — it's a stateless gateway. Adding rate limit / idempotency later will use Durable Objects + KV.
