# Claude Code wrapper

Two ways to wire `khdp-connector` into Claude Code.

## 1. Register the MCP server (recommended)

```bash
claude mcp add khdp -- khdp mcp
```

This makes the `khdp_*` tools available in any Claude Code session.

## 2. Install the Skill

The Skill (`skills/khdp-auth/SKILL.md`) gives Claude triggering rules and
domain-specific guardrails (when to call `auth_login`, what *not* to do
with PHI, etc.). Drop the `skills/khdp-auth/` directory into one of:

- `~/.claude/skills/` — available across all projects
- `<repo>/.claude/skills/` — scoped to a repository

A user-level installer for convenience:

```bash
# macOS / Linux
cp -r skills/khdp-auth ~/.claude/skills/

# Windows (PowerShell)
Copy-Item -Recurse skills\khdp-auth $env:USERPROFILE\.claude\skills\
```

## Combined `.mcp.json` example

If you commit MCP config to your repo, this is the project-scoped form:

```json
{
  "mcpServers": {
    "khdp": {
      "command": "khdp",
      "args": ["mcp"]
    }
  }
}
```
