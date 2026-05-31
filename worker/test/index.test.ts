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
    expect(body).toContain("KHDP Open API");
    expect(body).toContain("for AI Agents");
    expect(body).toContain("/docs");
    expect(body).toContain("/AGENTS.md");
    // No login button on the public landing.
    expect(body).not.toContain("Sign in");
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

  it("/v1/datasets/KHDP-001/latest/files → backend files-download-link-all (REST-canonical list)", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const u = typeof input === "string" ? input : input.toString();
        calls.push(u);
        if (u.endsWith("/dataset/code/KHDP-001")) {
          return new Response(JSON.stringify({ ciCode: "KHDP-001" }), { status: 200 });
        }
        return new Response(JSON.stringify({ items: [], continueToken: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/KHDP-001/latest/files?continueToken=TOK"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(calls).toContain(
      "https://backend.example/_api/open/datasets/KHDP-001/latest/files-download-link-all?continueToken=TOK",
    );
    const body = (await res.json()) as { archive: { available: boolean } };
    expect(body.archive.available).toBe(false);
  });

  it("/v1/datasets/KHDP-001/latest/files/imaging/a.dcm → backend files/download-link?key= (REST-canonical member)", async () => {
    const { seen } = stubUpstream({ url: "https://signed/" });
    await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/KHDP-001/latest/files/imaging/a.dcm"),
      env,
      makeCtx(),
    );
    expect(seen.url).toBe(
      "https://backend.example/_api/open/datasets/KHDP-001/latest/files/download-link?key=imaging%2Fa.dcm",
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

  it("/v1/me → /_api/member/profile", async () => {
    const { seen } = stubUpstream({ mId: 1, email: "a@b.c" });
    await worker.fetch(
      new Request("https://khdp.ai/v1/me", {
        headers: { Authorization: "Bearer khdp_pat_X" },
      }),
      env,
      makeCtx(),
    );
    expect(seen.url).toBe("https://backend.example/_api/member/profile");
  });

  it("/v1/me/balance → /_api/credit/my-balance", async () => {
    const { seen } = stubUpstream({ balance: "1000" });
    await worker.fetch(
      new Request("https://khdp.ai/v1/me/balance", {
        headers: { Authorization: "Bearer khdp_pat_X" },
      }),
      env,
      makeCtx(),
    );
    expect(seen.url).toBe("https://backend.example/_api/credit/my-balance");
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

describe("archive enrichment", () => {
  function stubBackend(handlers: Record<string, (init?: RequestInit) => Response | Promise<Response>>) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const u = typeof input === "string" ? input : input.toString();
        for (const [pattern, handler] of Object.entries(handlers)) {
          if (u.includes(pattern)) return handler(init);
        }
        return new Response("not stubbed: " + u, { status: 500 });
      }),
    );
  }

  it("attaches available=false when no zip exists", async () => {
    stubBackend({
      "/open/datasets/INSPIRE/1.3":
        () => new Response(JSON.stringify({ code: "INSPIRE", version: "1.3", title: "X", accessPolicy: "open" }), { status: 200 }),
      "/dataset/code/INSPIRE":
        () => new Response(JSON.stringify({ ciCode: "INSPIRE", cvId: 660, version: "1.3" }), { status: 200 }),
      "/dataset/660/files/compress-check":
        () => new Response(JSON.stringify({ isExist: false }), { status: 200 }),
    });
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    const body = (await res.json()) as { archive: { available: boolean; format: string } };
    expect(body.archive).toEqual({ available: false, format: "zip" });
  });

  it("anonymous + zip exists → available=true but no URL", async () => {
    stubBackend({
      "/open/datasets/INSPIRE/1.3":
        () => new Response(JSON.stringify({ code: "INSPIRE", version: "1.3", title: "X", accessPolicy: "open" }), { status: 200 }),
      "/dataset/code/INSPIRE":
        () => new Response(JSON.stringify({ ciCode: "INSPIRE", cvId: 660, version: "1.3" }), { status: 200 }),
      "/dataset/660/files/compress-check":
        () => new Response(JSON.stringify({ isExist: true }), { status: 200 }),
    });
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3"),
      env,
      makeCtx(),
    );
    const body = (await res.json()) as { archive: { available: boolean; url?: string } };
    expect(body.archive.available).toBe(true);
    expect(body.archive.url).toBeUndefined();
  });

  it("bearer + zip exists → archive.url is the presigned link", async () => {
    stubBackend({
      "/open/datasets/INSPIRE/1.3":
        () => new Response(JSON.stringify({ code: "INSPIRE", version: "1.3", title: "X", accessPolicy: "open" }), { status: 200 }),
      "/dataset/code/INSPIRE":
        () => new Response(JSON.stringify({ ciCode: "INSPIRE", cvId: 660, version: "1.3" }), { status: 200 }),
      "/dataset/660/files/compress-check":
        () => new Response(JSON.stringify({ isExist: true }), { status: 200 }),
      "/dataset/660/files/compress-link":
        () => new Response(JSON.stringify({ url: "https://obj.example/INSPIRE.zip?sig=abc", expiresAt: "2026-06-01T00:00:00Z", sizeBytes: 1234567 }), { status: 200 }),
    });
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3", {
        headers: { Authorization: "Bearer khdp_pat_abc" },
      }),
      env,
      makeCtx(),
    );
    const body = (await res.json()) as { archive: { available: boolean; url: string; expiresAt: string; sizeBytes: number; format: string } };
    expect(body.archive.available).toBe(true);
    expect(body.archive.url).toBe("https://obj.example/INSPIRE.zip?sig=abc");
    expect(body.archive.expiresAt).toBe("2026-06-01T00:00:00Z");
    expect(body.archive.sizeBytes).toBe(1234567);
    expect(body.archive.format).toBe("zip");
  });

  it("X-API-Key header → translated to Authorization: Bearer; archive.url populated", async () => {
    const sentHeaders: Record<string, string> = {};
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const u = typeof input === "string" ? input : input.toString();
        if (u.endsWith("/compress-link")) {
          const hdrs = new Headers(init?.headers as HeadersInit);
          sentHeaders["compress-link"] = hdrs.get("Authorization") ?? "";
        }
        if (u.includes("/open/datasets/INSPIRE/1.3")) {
          return new Response(JSON.stringify({ code: "INSPIRE", version: "1.3", title: "X", accessPolicy: "open" }), { status: 200 });
        }
        if (u.endsWith("/dataset/code/INSPIRE")) {
          return new Response(JSON.stringify({ ciCode: "INSPIRE", cvId: 660, version: "1.3" }), { status: 200 });
        }
        if (u.endsWith("/compress-check")) {
          return new Response(JSON.stringify({ isExist: true }), { status: 200 });
        }
        if (u.endsWith("/compress-link")) {
          return new Response(JSON.stringify({ url: "https://obj.example/X.zip" }), { status: 200 });
        }
        return new Response("not stubbed", { status: 500 });
      }),
    );
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3", {
        headers: { "X-API-Key": "khdp_pat_abc" },
      }),
      env,
      makeCtx(),
    );
    const body = (await res.json()) as { archive: { url?: string } };
    expect(body.archive.url).toBe("https://obj.example/X.zip");
    expect(sentHeaders["compress-link"]).toBe("Bearer khdp_pat_abc");
  });

  it("requested version != latest → archive omitted (available=false)", async () => {
    stubBackend({
      "/open/datasets/INSPIRE/1.2":
        () => new Response(JSON.stringify({ code: "INSPIRE", version: "1.2", title: "X", accessPolicy: "open" }), { status: 200 }),
      "/dataset/code/INSPIRE":
        () => new Response(JSON.stringify({ ciCode: "INSPIRE", cvId: 660, version: "1.3" }), { status: 200 }),
    });
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.2"),
      env,
      makeCtx(),
    );
    const body = (await res.json()) as { archive: { available: boolean } };
    expect(body.archive.available).toBe(false);
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

  it("/v1/datasets/{c}/{v}/files-download-link-all → 404 LEGACY_PATH suggesting /files", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3/files-download-link-all"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { errorCode: string; canonical: string };
    expect(body.errorCode).toBe("LEGACY_PATH");
    expect(body.canonical).toBe("/v1/datasets/INSPIRE/1.3/files");
  });

  it("/v1/datasets/{c}/{v}/files/download-link → 404 LEGACY_PATH suggesting /files/{key}", async () => {
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/datasets/INSPIRE/1.3/files/download-link?key=imaging%2Fa.dcm"),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(404);
    const body = (await res.json()) as { errorCode: string; canonical: string };
    expect(body.errorCode).toBe("LEGACY_PATH");
    expect(body.canonical).toBe("/v1/datasets/INSPIRE/1.3/files/{key}");
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
