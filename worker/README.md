# khdp-ai-gateway

Cloudflare Worker fronting **`khdp.ai`** — the AI-agent entry point for the Korea Health Data Platform.

| Path | Behaviour |
| --- | --- |
| `GET /` | Minimal landing page pointing agents at `/AGENTS.md`. |
| `GET /AGENTS.md` | 60-second edge-cached mirror of [`AGENTS.md`](../AGENTS.md) from this repo's `main`. |
| `GET /REST_API.md` | 60-second edge-cached mirror of [`docs/REST_API.md`](../docs/REST_API.md) from this repo's `main`. |
| `ANY /v1/*` | Transparent alias of `khdp.net/_api/*` — `/v1/open/datasets`, `/v1/oauth/token`, `/v1/external/oauth-login` etc. all forward 1:1. Auth headers + query preserved; adds `X-Request-Id`; sets permissive CORS. |
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
curl http://localhost:8787/AGENTS.md   | head -5
curl http://localhost:8787/REST_API.md | head -5
curl 'http://localhost:8787/v1/open/datasets?query=heart&limit=2'
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
| `GITHUB_REST_API_RAW` | `raw.githubusercontent.com/KoreaHealthDataPlatform/khdp-api/main/docs/REST_API.md` | Source for `/REST_API.md` proxy. Point at a tag to pin. |
| `BACKEND_BASE` | `https://khdp.net/_api` | Upstream the `/v1/*` gateway forwards to (1:1 alias). |

No secrets are bound today. When per-call PAT introspection or token signing keys land, use `wrangler secret put <NAME>` and reference via `env.<NAME>`.

## Operations notes

- **Hop-by-hop headers** are stripped on both directions (`Connection`, `Transfer-Encoding`, `Host`, etc.).
- **Errors** thrown anywhere in the handler return `502` with `{ statusCode, errorCode: "GATEWAY_ERROR", message, requestId }`. Logs go to Workers Observability.
- **CORS** is permissive (`*`) for `/v1/*` so browser-based notebooks can call directly. Tighten when the API surface stabilises.
- **No mutating state** in the Worker itself — it's a stateless gateway. Adding rate limit / idempotency later will use Durable Objects + KV.
