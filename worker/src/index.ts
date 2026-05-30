/**
 * khdp-ai-gateway — Cloudflare Worker fronting `khdp.ai`.
 *
 * Surfaces:
 *  - GET  /                  → minimal landing page pointing agents at /AGENTS.md
 *  - GET  /AGENTS.md         → mirror of the GitHub-hosted AGENTS.md (60s edge cache)
 *  - ANY  /v1/*              → passthrough to the KHDP backend (khdp.net/_api/open/*)
 *  - GET  /healthz           → liveness probe
 *
 * Bytes (dataset downloads/uploads) never transit this Worker — KHDP
 * returns presigned URLs that the client fetches directly from origin
 * storage.
 */

export interface Env {
  GITHUB_AGENTS_RAW: string;
  BACKEND_BASE: string;
}

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    const requestId = crypto.randomUUID();

    if (req.method === "OPTIONS" && url.pathname.startsWith("/v1/")) {
      return preflight();
    }

    try {
      if (url.pathname === "/") return landing();
      if (url.pathname === "/healthz") return json({ ok: true, requestId });
      if (url.pathname === "/AGENTS.md") return agentsProxy(req, env, ctx);
      if (url.pathname.startsWith("/v1/")) return v1Gateway(req, env, requestId);
      return notFound(requestId);
    } catch (err) {
      return errorResponse(err, requestId);
    }
  },
};

/** Proxy GitHub raw AGENTS.md through the edge cache. */
async function agentsProxy(
  req: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  const cache = caches.default;
  const cacheKey = new Request(req.url, { method: "GET" });
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const upstream = await fetch(env.GITHUB_AGENTS_RAW, {
    cf: { cacheTtl: 60, cacheEverything: true },
  });
  const headers = new Headers({
    "Content-Type": "text/markdown; charset=utf-8",
    "Cache-Control": "public, max-age=60",
    "X-Source": env.GITHUB_AGENTS_RAW,
    "Access-Control-Allow-Origin": "*",
  });
  const resp = new Response(upstream.body, { status: upstream.status, headers });
  ctx.waitUntil(cache.put(cacheKey, resp.clone()));
  return resp;
}

/** Forward /v1/* to the KHDP backend, preserving auth and query. */
async function v1Gateway(
  req: Request,
  env: Env,
  requestId: string,
): Promise<Response> {
  const url = new URL(req.url);
  const upstreamPath = url.pathname.slice("/v1".length) || "/";
  const target = new URL(env.BACKEND_BASE + upstreamPath + url.search);

  const headers = passthroughHeaders(req.headers);
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
  headers.set("X-Request-Id", requestId);

  const upstream = await fetch(target.toString(), {
    method: req.method,
    headers,
    body: hasBody(req.method) ? req.body : undefined,
    redirect: "manual",
  });

  const responseHeaders = passthroughResponseHeaders(upstream.headers);
  responseHeaders.set("X-Request-Id", requestId);
  responseHeaders.set("Access-Control-Allow-Origin", "*");
  responseHeaders.set("Access-Control-Expose-Headers", "X-Request-Id");

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

function passthroughHeaders(input: Headers): Headers {
  const out = new Headers();
  for (const [k, v] of input) {
    if (!HOP_BY_HOP.has(k.toLowerCase())) out.append(k, v);
  }
  return out;
}

function passthroughResponseHeaders(input: Headers): Headers {
  const out = new Headers();
  for (const [k, v] of input) {
    if (!HOP_BY_HOP.has(k.toLowerCase())) out.append(k, v);
  }
  return out;
}

function hasBody(method: string): boolean {
  const m = method.toUpperCase();
  return m !== "GET" && m !== "HEAD";
}

function preflight(): Response {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type, X-App-Id, X-App-Secret, Idempotency-Key",
      "Access-Control-Max-Age": "86400",
    },
  });
}

function landing(): Response {
  return new Response(LANDING_HTML, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "public, max-age=300",
    },
  });
}

function notFound(requestId: string): Response {
  return new Response(
    JSON.stringify({
      statusCode: 404,
      errorCode: "NOT_FOUND",
      message: "Not Found. Try /, /AGENTS.md, /v1/datasets, or /healthz.",
      requestId,
    }, null, 2),
    {
      status: 404,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-Request-Id": requestId,
      },
    },
  );
}

function errorResponse(err: unknown, requestId: string): Response {
  const message = err instanceof Error ? err.message : String(err);
  return new Response(
    JSON.stringify({
      statusCode: 502,
      errorCode: "GATEWAY_ERROR",
      message,
      requestId,
    }, null, 2),
    {
      status: 502,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-Request-Id": requestId,
      },
    },
  );
}

function json(body: object): Response {
  return new Response(JSON.stringify(body, null, 2), {
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}

const LANDING_HTML = `<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>KHDP for AI agents</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  :root { color-scheme: light dark; }
  body { font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         max-width: 720px; margin: 4rem auto; padding: 0 1.25rem; }
  h1 { font-size: 1.6rem; margin: 0 0 .5rem; }
  code { background: rgba(127,127,127,.15); padding: .1rem .35rem; border-radius: .25rem; }
  blockquote { margin: 1.2rem 0; padding: .8rem 1rem; background: rgba(127,127,127,.1);
               border-left: 4px solid #888; }
  ul { padding-left: 1.25rem; }
  li { margin: .35rem 0; }
  small { color: #888; }
</style>
<h1>KHDP for AI agents</h1>
<p>The <strong>Korea Health Data Platform</strong>'s AI-agent entry point.</p>

<p>Tell your AI coding agent (Claude Code, OpenAI Codex, Google Antigravity, Cursor, Gemini CLI, …):</p>
<blockquote>
  Please read <code>https://khdp.ai/AGENTS.md</code> and follow its guidance for the KHDP API.
  When authentication is needed, ask me whether I prefer <strong>OAuth (browser login)</strong>
  or a <strong>Personal Access Token (PAT)</strong> before proceeding.
</blockquote>

<ul>
  <li><a href="/AGENTS.md">/AGENTS.md</a> — agent instructions (mirror)</li>
  <li><a href="/v1/datasets?limit=5">/v1/datasets</a> — REST API gateway (v1)</li>
  <li><a href="https://github.com/KoreaHealthDataPlatform/khdp-api">github.com/KoreaHealthDataPlatform/khdp-api</a> — connector + docs</li>
</ul>

<p><small>Bytes (dataset downloads/uploads) flow directly between you and the KHDP origin object store via presigned URLs — they never transit this gateway.</small></p>
</html>
`;
