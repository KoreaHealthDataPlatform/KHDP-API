# Quickstart

**English** · [한국어](./quickstart.ko.md) · [Español](./quickstart.es.md) · [中文](./quickstart.zh-CN.md) · [日本語](./quickstart.ja.md)

From zero to a successful authenticated KHDP API call — about five minutes.

This walkthrough complements [the README](../README.md), which lists four entry points side-by-side. Here we take the Python / CLI path end-to-end and finish by wiring up Claude Code.

## Before you start

- Python ≥ 3.10
- One of the following credentials:
  - **Personal API token** — fastest: <https://khdp.net> → *Settings → Account → API Token*. A string starting with `khdp_pat_…`.
  - **`app_id`** — request one from the KHDP team if you need PKCE login. CLI-class apps must register `http://127.0.0.1:*/callback` as an allowed redirect URL.
- For the agent step: [Claude Code](https://claude.com/claude-code) installed.

> The first three steps work fully without an `app_id` — they only need a personal API token (or no credentials at all for public search).

## 1. Install

```bash
pipx install khdp          # isolates from system Python
# or
pipx install 'khdp[keyring]'   # store tokens in the OS keychain
```

Verify:

```bash
khdp --version
khdp config              # prints the resolved configuration
```

## 2. Configure

Pick one path. You can change your mind later.

### Path A — Personal API token (recommended for first run)

```bash
export KHDP_TOKEN="khdp_pat_…"
```

That's it. No `khdp login` needed; all calls use the token directly. Long-lived, no refresh dance.

### Path B — `app_id` + PKCE login

```bash
export KHDP_APP_ID="00000000-0000-0000-0000-000000000000"
khdp login                 # opens the browser, captures the callback locally
khdp status                # confirm: authenticated, token expiry
```

`--no-browser` prints the URL for headless / remote machines.

## 3. Search public datasets (anonymous works)

CLI:

```bash
khdp datasets list --query heart --limit 5
```

Same call from Python:

```python
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    for d in r.json()["items"]:
        print(d["code"], "—", d["title"])
```

Pick a dataset `code` from the output — for the rest of this guide we'll write it as `<CODE>`.

## 4. Inspect an Open-policy dataset

File listing requires the `datasets` scope on whichever credential you're using.

```bash
khdp datasets show     <CODE>
khdp datasets files    <CODE>            # root listing
khdp datasets files    <CODE> --prefix imaging/
```

> If you get `403 App does not have datasets scope`, ask the KHDP team to grant your app the `datasets` scope. This applies to all callers.

## 5. Download files

Dry-run first to see what would happen — no bytes transferred:

```bash
khdp datasets download <CODE> --out ./data --dry-run
```

Then download:

```bash
khdp datasets download <CODE> --out ./data
```

`download` paginates the server's `files-download-link-all` endpoint (1000 keys per page) and streams each file. Use `--max-pages N` to stop after N pages when verifying flow.

> Downloads only work for `accessPolicy=open` datasets. Restricted / Credentialed / ContributorReview datasets return `400 Is Not Open Access Dataset` — use the KHDP web UI for access requests.

## 6. Call from Claude Code (MCP)

```bash
claude mcp add khdp -- khdp-mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

Open Claude Code and try:

> *"Use the khdp tools to search KHDP for heart-disease datasets, then show me the file listing of the top hit."*

Claude Code calls the MCP server, which reuses the same token cache you populated in step 2. No password ever flows through the LLM context.

The same MCP server backs [OpenAI Codex CLI](../wrappers/codex/), [Gemini CLI](../wrappers/gemini/), and Cursor.

## Common gotchas

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `401` on any call | wrong header, expired OAuth token, or wrong environment | `khdp status`; `khdp refresh`; check `khdp config` |
| `403 App does not have datasets scope` | the app issuing the token lacks `datasets` scope | request scope from KHDP team (applies to OAuth too) |
| `403 Auth type "openApiApp" is not allowed` | called a user-only endpoint without OAuth/PAT auth | use OAuth or PAT — submissions are user-only |
| `404 Dataset Not Found` | wrong `code` or unpublished `version` | omit version (defaults to `@latest`) or use `khdp datasets list` |
| `400 Is Not Open Access Dataset` on download | dataset is not Open-policy | only Open datasets are downloadable via the external API |
| `khdp login` hangs | loopback redirect URL not registered on the app | ask KHDP ops to register `http://127.0.0.1:*/callback` |
| `khdp-mcp` not found | `pipx` shim path not on `PATH` | `pipx ensurepath` and reopen the shell |

## What to read next

- [API reference (Redoc)](https://khdp.ai/docs) — every endpoint, payload, scope, and error (machine-readable spec at <https://khdp.ai/openapi.json>)
- [`AGENTS.md`](../AGENTS.md) — driving the connector from a coding agent in depth
- [Canonical KHDP spec](https://khdp.net/docs/external-api) — official site
- [Security model](../SECURITY.md) — PKCE, loopback redirect, token storage, threat model
