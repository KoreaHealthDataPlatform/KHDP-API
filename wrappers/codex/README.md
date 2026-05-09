# OpenAI Codex CLI wrapper

Codex picks up MCP servers from `~/.codex/config.toml` and prompt
context from `AGENTS.md` files in the workspace.

## Install

```bash
pipx install khdp-connector
```

## Wire up Codex

1. Append the contents of `config.example.toml` to your
   `~/.codex/config.toml` (create the file if missing).
2. Copy `AGENTS.md` to the root of any KHDP-using project, or merge its
   contents into an existing `AGENTS.md`.

## Verify

```bash
codex --help
# Then in a Codex session:
#   "What KHDP tools do you have?"
# The agent should list the khdp_* tools.
```

## Notes

- Codex sandboxing: `khdp mcp` opens a local TCP socket for the OAuth
  loopback redirect. If you run Codex in a strict sandbox profile you
  may need to add an exception for `127.0.0.1` outbound.
- `khdp_auth_login` will only work when Codex is run on a machine with a
  default browser — i.e. not inside a headless container. For headless
  flows, run `khdp login` once on a workstation, then export
  `KHDP_TOKEN_DIR` to point at the same directory.
