/**
 * Smoke tests for the Worker routes. Backend / GitHub fetches are mocked
 * via vitest's global `fetch`, so these run offline.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import worker from "../src/index";

function makeCtx(): ExecutionContext {
  return {
    waitUntil(_promise: Promise<unknown>): void {},
    passThroughOnException(): void {},
    props: {},
  } as unknown as ExecutionContext;
}

const env = {
  GITHUB_AGENTS_RAW: "https://example.org/AGENTS.md",
  BACKEND_BASE: "https://backend.example/_api",
  WEB_BASE: "https://web.example",
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("landing", () => {
  it("returns the landing HTML on GET /", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toMatch(/text\/html/);
    const body = await res.text();
    expect(body).toContain("KHDP for AI agents");
    expect(body).toContain("/AGENTS.md");
  });
});

describe("/healthz", () => {
  it("returns ok=true", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/healthz"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { ok: boolean; requestId: string };
    expect(body.ok).toBe(true);
    expect(typeof body.requestId).toBe("string");
  });
});

describe("/AGENTS.md", () => {
  it("proxies upstream with markdown content type", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response("# AGENTS\n", {
          status: 200,
          headers: { "Content-Type": "text/markdown" },
        }),
      ),
    );

    const res = await worker.fetch(
      new Request("https://khdp.ai/AGENTS.md"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toMatch(/text\/markdown/);
    expect(res.headers.get("Cache-Control")).toContain("max-age=60");
    expect(res.headers.get("X-Source")).toBe(env.GITHUB_AGENTS_RAW);
    const body = await res.text();
    expect(body).toContain("# AGENTS");
  });
});

describe("/openapi.json", () => {
  it("serves the bundled OpenAPI 3.1 spec", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/openapi.json"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toMatch(/application\/json/);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
    const body = (await res.json()) as {
      openapi: string;
      info: { title: string };
      paths: Record<string, unknown>;
    };
    expect(body.openapi).toMatch(/^3\./);
    expect(body.info.title).toContain("KHDP");
    expect(Object.keys(body.paths).length).toBeGreaterThan(5);
    expect(body.paths["/datasets"]).toBeDefined();
    expect(body.paths["/submissions"]).toBeDefined();
    expect(body.paths["/oauth/authorize"]).toBeDefined();
  });
});

describe("/docs", () => {
  it("serves the Redoc HTML rendering /openapi.json", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/docs"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toMatch(/text\/html/);
    const body = await res.text();
    expect(body).toContain('spec-url="/openapi.json"');
    expect(body).toContain("redoc.standalone.js");
  });

  it("also responds at /docs/ (trailing slash)", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/docs/"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
  });
});

describe("/v1/* gateway canonical aliases", () => {
  const stubUpstream = (
    body: object = { items: [] },
  ): { seen: { url: string; method: string } } => {
    const seen = { url: "", method: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.url = typeof input === "string" ? input : input.toString();
        seen.method = init?.method ?? "GET";
        return new Response(JSON.stringify(body), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    return { seen };
  };

  it("/v1/datasets → /_api/open/datasets", async () => {
    const { seen } = stubUpstream();
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets?query=heart&limit=2"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(seen.url).toBe(
      "https://backend.example/_api/open/datasets?query=heart&limit=2",
    );
    expect(res.headers.get("X-Request-Id")).toBeTruthy();
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
  });

  it("/v1/datasets/KHDP-001/latest/files → /_api/open/datasets/KHDP-001/latest/files", async () => {
    const { seen } = stubUpstream();
    await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/KHDP-001/latest/files?key=imaging/"),
      env,
      makeCtx(),
    );
    expect(seen.url).toBe(
      "https://backend.example/_api/open/datasets/KHDP-001/latest/files?key=imaging/",
    );
  });

  it("/v1/submissions → /_api/open/dataset-submissions", async () => {
    const { seen } = stubUpstream();
    await worker.fetch(
      new Request("https://khdp.ai/v1/submissions", {
        method: "POST",
        body: JSON.stringify({ title: "X" }),
        headers: { "Content-Type": "application/json" },
      }),
      env,
      makeCtx(),
    );
    expect(seen.method).toBe("POST");
    expect(seen.url).toBe("https://backend.example/_api/open/dataset-submissions");
  });

  it("/v1/submissions/{code}/{ver}/submit → /_api/open/dataset-submissions/{code}/{ver}/submit", async () => {
    const { seen } = stubUpstream();
    await worker.fetch(
      new Request("https://khdp.ai/v1/submissions/MY-001/1.0.0/submit", {
        method: "POST",
      }),
      env,
      makeCtx(),
    );
    expect(seen.url).toBe(
      "https://backend.example/_api/open/dataset-submissions/MY-001/1.0.0/submit",
    );
  });

  it("/v1/oauth/authorize → 302 redirect to WEB_BASE/external/oauth-login", async () => {
    const res = await worker.fetch(
      new Request(
        "https://khdp.ai/v1/oauth/authorize?client_id=x&code_challenge=y",
        { redirect: "manual" },
      ),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe(
      "https://web.example/external/oauth-login?client_id=x&code_challenge=y",
    );
  });

  it("/v1/oauth/token → /_api/oauth/token (passthrough, unchanged)", async () => {
    const { seen } = stubUpstream({ access_token: "X" });
    await worker.fetch(
      new Request("https://khdp.ai/v1/oauth/token", {
        method: "POST",
        body: JSON.stringify({ grant_type: "refresh_token" }),
        headers: { "Content-Type": "application/json" },
      }),
      env,
      makeCtx(),
    );
    expect(seen.method).toBe("POST");
    expect(seen.url).toBe("https://backend.example/_api/oauth/token");
  });

  it("returns 204 + CORS headers on preflight OPTIONS", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets", { method: "OPTIONS" }),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(res.headers.get("Access-Control-Allow-Methods")).toContain("POST");
  });
});


describe("unknown paths", () => {
  it("returns structured 404 JSON", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/nope"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { errorCode: string };
    expect(body.errorCode).toBe("NOT_FOUND");
  });
});

describe("legacy long-form paths", () => {
  it("/v1/open/datasets → 404 LEGACY_PATH suggesting /v1/datasets", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/open/datasets?limit=1"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as {
      errorCode: string;
      canonical: string;
      message: string;
    };
    expect(body.errorCode).toBe("LEGACY_PATH");
    expect(body.canonical).toBe("/v1/datasets");
    expect(body.message).toContain("/v1/datasets");
  });

  it("/v1/open/datasets/KHDP-001/latest/files → 404 suggesting /v1/datasets/KHDP-001/latest/files", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/open/datasets/KHDP-001/latest/files"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { canonical: string };
    expect(body.canonical).toBe("/v1/datasets/KHDP-001/latest/files");
  });

  it("/v1/open/dataset-submissions/MY-001/1.0.0/submit → 404 suggesting /v1/submissions/MY-001/1.0.0/submit", async () => {
    const res = await worker.fetch(
      new Request(
        "https://khdp.ai/v1/open/dataset-submissions/MY-001/1.0.0/submit",
      ),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { canonical: string };
    expect(body.canonical).toBe("/v1/submissions/MY-001/1.0.0/submit");
  });

  it("/v1/external/oauth-login → 404 suggesting /v1/oauth/authorize", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/external/oauth-login"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { canonical: string };
    expect(body.canonical).toBe("/v1/oauth/authorize");
  });
});
