---
name: khdp-auth
description: Authenticate to the Korea Health Data Platform (KHDP) and call its APIs through the KHDP MCP server. Use whenever the user asks to log in to KHDP, check their KHDP login status, fetch data from KHDP, or call any khdp.net / snuh.ai API. Triggers on phrases like "KHDP login", "khdp 로그인", "KHDP 인증", "KHDP API", or any mention of the Korea Health Data Platform.
---

# KHDP Authentication Skill

This skill connects Claude Code to the **Korea Health Data Platform
(KHDP)** through the `khdp-connector` MCP server.

KHDP uses a custom *appId / password / Bearer-token* scheme — not
standard OAuth 2.0 / OIDC. The connector handles the protocol; this
skill just tells Claude when and how to use it.

## When to use

Activate this skill any time the user mentions:

- KHDP, Korea Health Data Platform, 한국 보건의료 데이터 플랫폼
- `khdp.net` or `snuh.ai` URLs
- Logging in / out of a KHDP environment
- Fetching datasets, OMOP CDM tables, or audit logs from KHDP
- "KHDP 로그인", "KHDP 인증", "KHDP에서 데이터 가져와줘"

## Setup (one time)

```bash
pipx install khdp-connector
claude mcp add khdp -- khdp mcp
```

The user must also configure their `app_id` and `redirect_url` (see
the connector README) and run `khdp login` once in a terminal — login
prompts for an email + password and **must not** be initiated through
this skill.

After setup, the following MCP tools are available:

| Tool                | Purpose                                          |
| ------------------- | ------------------------------------------------ |
| `khdp_auth_status`  | Show whether the user is logged in.              |
| `khdp_auth_refresh` | Rotate the refresh token to extend the session.  |
| `khdp_auth_logout`  | Delete locally cached tokens.                    |
| `khdp_api_request`  | Authenticated GET/POST against the KHDP API.     |

Note: there is **no** `khdp_auth_login` MCP tool. Login requires a
password, and KHDP-connector deliberately keeps that off the LLM
context. If status reports `authenticated=false`, ask the user to run
`khdp login` in their terminal.

## How to use

1. **Always check status first** with `khdp_auth_status`. If
   `is_expired=true` and `has_refresh_token=true`, call
   `khdp_auth_refresh` before doing data work.

2. **If `authenticated=false`**, do not try to log in yourself. Ask
   the user to run `khdp login` in their terminal and report back.

3. **For data calls**, prefer dedicated tools when they appear in
   future versions (e.g. `khdp_dataset_list`, `khdp_omop_query`). Fall
   back to `khdp_api_request` only when no specific tool covers the
   endpoint.

4. **Never print the access token** in chat. The MCP layer attaches
   the bearer header — there's no need to surface it.

## Negative examples (do NOT do)

- Do NOT ask the user to paste their KHDP password into the chat or
  into a tool argument. Login happens out-of-band.
- Do NOT call `khdp_auth_logout` unless the user explicitly asks.
- Do NOT generate medical interpretations from KHDP data — KHDP's UI
  copy policy forbids diagnostic phrasing in agent output.

## References

- KHDP connector source: <https://github.com/KoreaHealthDataPlatform/khdp-api>
- MCP specification: <https://modelcontextprotocol.io>
