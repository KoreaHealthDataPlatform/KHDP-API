# Gemini CLI wrapper

Gemini CLI (≥ 0.2) supports MCP servers via `~/.gemini/settings.json`
and Gemini Extensions for per-project bundles.

## Install (per user)

```bash
pipx install khdp-connector
```

Then merge `settings.example.json` into `~/.gemini/settings.json`.

## Install as a Gemini Extension (per project)

```bash
mkdir -p .gemini/extensions/khdp
cp wrappers/gemini/extension.json .gemini/extensions/khdp/gemini-extension.json
cp wrappers/gemini/GEMINI.md      .gemini/extensions/khdp/GEMINI.md
```

Restart Gemini CLI; it will discover the extension on launch.

## Notes

- Gemini's tool-use loop sometimes calls `khdp_api_request` even when a
  more specific tool is suggested in `GEMINI.md`. Keep the tool roster
  short to bias the model toward the right call.
- For shared / CI environments, set `KHDP_TOKEN_DIR` so all sessions on
  the host share a single token cache.
