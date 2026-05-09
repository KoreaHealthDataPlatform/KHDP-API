# Contributing to khdp

Thanks for your interest. `khdp` is the official OAuth/MCP connector
for the Korea Health Data Platform. Most contributions land as small,
focused PRs.

## Local setup

```bash
git clone https://github.com/KoreaHealthDataPlatform/KHDPConnector.git
cd KHDPConnector
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
```

## Before sending a PR

```bash
ruff check src tests
pytest
```

CI runs the same checks across Linux / macOS / Windows on Python
3.10–3.12. If your change adds a new tool or endpoint, please add a
test under `tests/` that exercises it with `pytest-httpx`.

## What we accept

- Bug fixes with a clear repro and a regression test.
- New MCP tools that map to a stable KHDP backend route (open an
  issue first to align on the tool name and schema).
- Documentation that improves the onboarding path for an external
  AI coding agent.
- Wrapper updates for new agent platforms (Cursor, Windsurf, …) under
  `wrappers/`.

## What we don't accept (yet)

- Code that bypasses KHDP's auth or audit policies.
- Tools that surface PHI or patient identifiers in agent context.
- Vendor-specific tool reimplementations — the wrappers carry config
  and prompts only; the tool surface lives in the MCP server.

## Code style

- Type-annotated Python 3.10+. We rely on `from __future__ import
  annotations` for forward references.
- `ruff` enforces formatting and import order. Keep the existing rule
  set in `pyproject.toml`.
- Public API additions deserve a short docstring explaining the
  *why*, not the *what*. Don't restate the signature.

## Reporting security issues

See [SECURITY.md](./SECURITY.md). Don't open public issues for
suspected vulnerabilities.

## License

By submitting a contribution you agree it will be released under the
project's [Apache-2.0 License](./LICENSE).
