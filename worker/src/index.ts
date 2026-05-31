/**
 * khdp-ai-gateway — Cloudflare Worker fronting `khdp.ai`.
 *
 * Surfaces:
 *  - GET  /                  → minimal landing page pointing agents at /AGENTS.md
 *  - GET  /AGENTS.md         → mirror of the GitHub-hosted AGENTS.md (60s edge cache)
 *  - GET  /openapi.json      → bundled OpenAPI 3.1 spec for the API
 *  - GET  /docs              → Redoc HTML rendering /openapi.json
 *  - ANY  /v1/*              → passthrough to the KHDP backend (khdp.net/_api/*)
 *  - GET  /healthz           → liveness probe
 *
 * Bytes (dataset downloads/uploads) never transit this Worker — KHDP
 * returns presigned URLs that the client fetches directly from origin
 * storage.
 */

import openapiSpec from "../../openapi/v1.json";

export interface Env {
  GITHUB_AGENTS_RAW: string;
  BACKEND_BASE: string;
  WEB_BASE: string;
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
      if (url.pathname === "/AGENTS.md") {
        return mirrorMarkdown(req, ctx, env.GITHUB_AGENTS_RAW);
      }
      if (url.pathname === "/openapi.json") return openapiJson();
      if (url.pathname === "/docs" || url.pathname === "/docs/") return redocPage();
      if (url.pathname.startsWith("/v1/")) return v1Gateway(req, env, requestId);
      return notFound(requestId);
    } catch (err) {
      return errorResponse(err, requestId);
    }
  },
};

/** Proxy a GitHub-hosted Markdown file through the edge cache. */
async function mirrorMarkdown(
  req: Request,
  ctx: ExecutionContext,
  sourceUrl: string,
): Promise<Response> {
  const cache = caches.default;
  const cacheKey = new Request(req.url, { method: "GET" });
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const upstream = await fetch(sourceUrl, {
    cf: { cacheTtl: 60, cacheEverything: true },
  });
  const headers = new Headers({
    "Content-Type": "text/markdown; charset=utf-8",
    "Cache-Control": "public, max-age=60",
    "X-Source": sourceUrl,
    "Access-Control-Allow-Origin": "*",
  });
  const resp = new Response(upstream.body, { status: upstream.status, headers });
  ctx.waitUntil(cache.put(cacheKey, resp.clone()));
  return resp;
}

/** Forward /v1/* to the KHDP backend, preserving auth and query.
 *
 * The external surface uses short, agent-friendly canonical paths;
 * the Worker rewrites them onto the legacy nstri-back routes:
 *
 *   /v1/datasets/*           → /_api/open/datasets/*
 *   /v1/submissions/*        → /_api/open/dataset-submissions/*
 *   /v1/oauth/authorize      → 302 redirect to WEB_BASE/external/oauth-login
 *                              (browser-facing OAuth/PKCE login page, lives
 *                              at the web root, not under /_api)
 *
 * Everything else under /v1 (e.g. /oauth/token, /oauth/refresh-token,
 * /oauth/api-tokens) already matches the backend path 1:1.
 */
async function v1Gateway(
  req: Request,
  env: Env,
  requestId: string,
): Promise<Response> {
  const url = new URL(req.url);
  let tail = url.pathname.slice("/v1".length) || "/";

  // Reject the long forms — only canonical short paths are supported.
  const legacy = legacyHint(tail);
  if (legacy) return legacyReject(legacy, requestId);

  if (tail === "/datasets" || tail.startsWith("/datasets/")) {
    tail = "/open/datasets" + tail.slice("/datasets".length);
  } else if (tail === "/submissions" || tail.startsWith("/submissions/")) {
    tail = "/open/dataset-submissions" + tail.slice("/submissions".length);
  } else if (tail === "/me") {
    tail = "/member/profile";
  } else if (tail === "/me/balance") {
    tail = "/credit/my-balance";
  } else if (tail === "/oauth/authorize") {
    const target =
      env.WEB_BASE.replace(/\/$/, "") + "/external/oauth-login" + url.search;
    return Response.redirect(target, 302);
  }

  const target = env.BACKEND_BASE.replace(/\/$/, "") + tail + url.search;

  const headers = passthroughHeaders(req.headers);
  headers.set("X-Forwarded-Host", url.host);
  headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
  headers.set("X-Request-Id", requestId);

  const upstream = await fetch(target, {
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

/**
 * Detect legacy long-form paths and return the canonical replacement.
 * Returns null for paths that aren't legacy (let them pass through to the
 * normal rewrite + forwarder).
 */
function legacyHint(tail: string): { incoming: string; canonical: string } | null {
  // /v1/open/datasets[/*]  →  /v1/datasets[/*]
  if (tail === "/open/datasets" || tail.startsWith("/open/datasets/")) {
    return {
      incoming: "/v1" + tail,
      canonical: "/v1/datasets" + tail.slice("/open/datasets".length),
    };
  }
  // /v1/open/dataset-submissions[/*]  →  /v1/submissions[/*]
  if (
    tail === "/open/dataset-submissions" ||
    tail.startsWith("/open/dataset-submissions/")
  ) {
    return {
      incoming: "/v1" + tail,
      canonical:
        "/v1/submissions" + tail.slice("/open/dataset-submissions".length),
    };
  }
  // /v1/external/oauth-login  →  /v1/oauth/authorize
  if (tail === "/external/oauth-login") {
    return { incoming: "/v1/external/oauth-login", canonical: "/v1/oauth/authorize" };
  }
  // Generic /v1/open/* and /v1/external/* are explicitly removed surface.
  if (tail.startsWith("/open/") || tail === "/open") {
    return { incoming: "/v1" + tail, canonical: "" };
  }
  if (tail.startsWith("/external/") || tail === "/external") {
    return { incoming: "/v1" + tail, canonical: "" };
  }
  return null;
}

function legacyReject(
  hint: { incoming: string; canonical: string },
  requestId: string,
): Response {
  const message = hint.canonical
    ? `${hint.incoming} is not a supported path on khdp.ai. Use ${hint.canonical} instead.`
    : `${hint.incoming} is not a supported path on khdp.ai. See https://khdp.ai/REST_API.md for the current surface.`;
  return new Response(
    JSON.stringify(
      {
        statusCode: 404,
        errorCode: "LEGACY_PATH",
        message,
        canonical: hint.canonical || null,
        requestId,
      },
      null,
      2,
    ),
    {
      status: 404,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        "X-Request-Id": requestId,
        "Access-Control-Allow-Origin": "*",
      },
    },
  );
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

function openapiJson(): Response {
  return new Response(JSON.stringify(openapiSpec, null, 2), {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "public, max-age=300",
      "Access-Control-Allow-Origin": "*",
    },
  });
}

function redocPage(): Response {
  return new Response(REDOC_HTML, {
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

const REDOC_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>KHDP Open API for AI Agents — Reference</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body { margin: 0; padding: 0; }</style>
</head>
<body>
<redoc spec-url="/openapi.json"></redoc>
<script src="https://cdn.redocly.com/redoc/latest/bundles/redoc.standalone.js"></script>
</body>
</html>
`;

const LANDING_HTML = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>KHDP Open API for AI Agents</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="KHDP Open API for AI Agents — a small REST surface over the Korea Health Data Platform.">
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", system-ui, sans-serif;
    color: #111;
    background: #fff;
    -webkit-font-smoothing: antialiased;
  }
  main {
    max-width: 620px;
    margin: 0 auto;
    padding: clamp(3rem, 12vh, 9rem) 1.5rem 4rem;
  }
  h1 {
    font-size: clamp(2.25rem, 6.5vw, 3.25rem);
    font-weight: 800;
    line-height: 1.08;
    letter-spacing: -0.02em;
    margin: 0 0 1.25rem;
  }
  h1 .sub {
    display: block;
    color: #8a8a8a;
    font-weight: 500;
  }
  .lede {
    font-size: 1.0625rem;
    color: #5a5a5a;
    margin: 0 0 2.25rem;
  }
  .cta {
    display: flex;
    gap: 1.5rem;
    align-items: center;
    flex-wrap: wrap;
    margin: 0;
  }
  .btn {
    display: inline-block;
    background: #111;
    color: #fff;
    text-decoration: none;
    padding: 0.75rem 1.25rem;
    border-radius: 4px;
    font-weight: 600;
    font-size: 1rem;
    transition: background .15s;
  }
  .btn:hover { background: #2a2a2a; }
  .link {
    color: #8a8a8a;
    text-decoration: none;
    font-size: 1rem;
    font-weight: 500;
    transition: color .15s;
  }
  .link::after { content: "  \\2192"; }
  .link:hover { color: #111; }
  @media (prefers-color-scheme: dark) {
    body { color: #f4f4f4; background: #0a0a0a; }
    h1 .sub { color: #6a6a6a; }
    .lede { color: #a5a5a5; }
    .btn { background: #f4f4f4; color: #0a0a0a; }
    .btn:hover { background: #e0e0e0; }
    .link { color: #6a6a6a; }
    .link:hover { color: #f4f4f4; }
  }
</style>
</head>
<body>
<main>
  <h1>KHDP Open API<span class="sub">for AI Agents</span></h1>
  <p class="lede">A small REST surface over the Korea Health Data Platform — datasets, submissions, OAuth — for agents and researchers.</p>
  <p class="cta">
    <a class="btn" href="/docs">View API docs</a>
    <a class="link" href="/AGENTS.md">AGENTS.md</a>
  </p>
</main>
</body>
</html>
`;
