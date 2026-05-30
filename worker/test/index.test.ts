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
  KGPU_BASE: "https://kgpu.example",
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

describe("/v1/* gateway", () => {
  it("forwards /v1/open/datasets transparently to BACKEND_BASE/open/datasets", async () => {
    const seen: { url: string; method: string } = { url: "", method: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.url = typeof input === "string" ? input : input.toString();
        seen.method = init?.method ?? "GET";
        return new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/open/datasets?query=heart&limit=2"),
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

  it("forwards /v1/oauth/token to BACKEND_BASE/oauth/token (no /open prefix)", async () => {
    const seen: { url: string; method: string } = { url: "", method: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.url = typeof input === "string" ? input : input.toString();
        seen.method = init?.method ?? "GET";
        return new Response(JSON.stringify({ access_token: "X" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/oauth/token", {
        method: "POST",
        body: JSON.stringify({ grant_type: "refresh_token" }),
        headers: { "Content-Type": "application/json" },
      }),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(seen.url).toBe("https://backend.example/_api/oauth/token");
    expect(seen.method).toBe("POST");
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

describe("/v1/gpu/* gateway", () => {
  it("forwards /v1/gpu/me to KGPU_BASE/v1/me", async () => {
    const seen: { url: string } = { url: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        seen.url = typeof input === "string" ? input : input.toString();
        return new Response(JSON.stringify({ credits: 100 }), { status: 200 });
      }),
    );
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/gpu/me", {
        headers: { Authorization: "Bearer kgpu_test" },
      }),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(seen.url).toBe("https://kgpu.example/v1/me");
    expect(res.headers.get("X-Request-Id")).toBeTruthy();
  });

  it("forwards POST /v1/gpu/pods/{id}/exec with body", async () => {
    const seen: { url: string; method: string } = { url: "", method: "" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        seen.url = typeof input === "string" ? input : input.toString();
        seen.method = init?.method ?? "GET";
        return new Response("{}", { status: 200 });
      }),
    );
    const res = await worker.fetch(
      new Request("https://khdp.ai/v1/gpu/pods/abc123/exec", {
        method: "POST",
        body: JSON.stringify({ argv: ["nvidia-smi"] }),
        headers: { "Content-Type": "application/json" },
      }),
      env,
      makeCtx(),
    );
    expect(res.status).toBe(200);
    expect(seen.method).toBe("POST");
    expect(seen.url).toBe("https://kgpu.example/v1/pods/abc123/exec");
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
