# KHDP API

[English](./README.md) · [한국어](./README.ko.md) · [Español](./README.es.md) · **简体中文** · [日本語](./README.ja.md)

> *AI 翻译。规范来源：[README.md](./README.md)。最近同步：2026-05-30。*

**韩国健康数据平台（Korea Health Data Platform）** 的开发者接口 — 通过 `curl`、Python 或任意 AI 编码代理来检索、下载和提交医学研究数据集。

- REST API 位于 `https://khdp.ai/v1` — 参见 [docs/REST_API.md](./docs/REST_API.md)。
- 匿名浏览可用；通过认证（App Key / OAuth / API Token）解锁下载和提交。
- 同一个已认证会话同时驱动 CLI、Python 库以及面向 Claude Code、Codex CLI、Cursor、Gemini CLI 的 MCP 服务器。

> 仓库：`khdp-api` · Python 包：`khdp`（`pip install khdp`）。

## 快速开始 — 四种调用 API 的方式

### 1. curl
```bash
curl 'https://khdp.ai/v1/datasets?query=heart&limit=5' | jq '.items[].code'
```

### 2. Python（`khdp` SDK）
```python
# pip install khdp
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    print([d["code"] for d in r.json()["items"]])
```

### 3. Claude Code（MCP）
```bash
pip install khdp
khdp login
claude mcp add khdp -- khdp-mcp
```
然后在 Claude Code 中提问：*"在 KHDP 中检索心脏疾病相关的数据集，并对前几条结果进行总结。"*

### 4. OpenAI Codex CLI
将 [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) 追加到 `~/.codex/config.toml`，然后执行一次 `khdp login`。

> 完整指南：[docs/quickstart.zh-CN.md](./docs/quickstart.zh-CN.md)。端点参考：[docs/REST_API.md](./docs/REST_API.md)。

## 从 AI 智能体使用

通过 AI 编码智能体（Claude Code、OpenAI Codex、Google Antigravity、Cursor、Gemini CLI 等）使用 KHDP？将下面这段粘贴给智能体：

> 请阅读 https://khdp.ai/AGENTS.md 并按其说明使用 KHDP API。当需要认证时，请先询问我希望使用 **OAuth（浏览器登录）** 还是 **PAT（个人访问令牌）**。

智能体随后会加载 [`AGENTS.md`](./AGENTS.md) — 该文件说明如何安装 `khdp`、与你一起选择认证方式、调用 API、处理错误，并按 PHI 等同方式对待数据集内容。

## 安装

```bash
pipx install khdp                 # 推荐 — 与系统 Python 隔离
pipx install 'khdp[keyring]'      # + 使用操作系统密钥环存储令牌
```

该包安装：
- `khdp` — CLI（login、datasets、submissions、原始 `api` 通道）
- `khdp-mcp` — 供编码代理使用的 MCP 服务器
- `import khdp` — Python 库

## 认证

三种凭证类型，在 CLI、SDK 和 MCP 之间可互换使用。

| 类型 | 头部 | 身份 | 典型用途 |
| --- | --- | --- | --- |
| **App Key** | `X-App-Id` + `X-App-Secret` | 应用本身 | 服务器机器人、公共目录镜像 |
| **OAuth (PKCE)** | `Authorization: Bearer <jwt>` | 用户 | CLI、MCP、代表用户行动的 SaaS |
| **API Token**（PAT） | `Authorization: Bearer khdp_pat_…` | 用户 | 笔记本、AI 代理（长期，无需刷新） |

向 KHDP 团队申请 `app_id`。个人 API 令牌可在 <https://khdp.net> 的 *Settings → Account → API Token* 中签发。

```toml
# ./khdp.local.toml （或 ~/.config/khdp/config.toml）
app_id     = "00000000-0000-0000-0000-000000000000"
# app_secret = "..."             # App Key
# api_key    = "khdp_pat_..."    # 个人 API 令牌
api_base   = "https://khdp.ai/v1"
```

或通过环境变量：`KHDP_APP_ID`、`KHDP_APP_SECRET`、`KHDP_TOKEN`。

## CLI

```bash
khdp login [--no-browser]                              # PKCE 登录（loopback 重定向）
khdp status | refresh | logout | config

khdp datasets list      [--query KW] [--policy open|restricted|...]
khdp datasets show      <code>[@<version>]
khdp datasets files     <code>[@<version>] [--key PREFIX]
khdp datasets download  <code>[@<version>] [--out DIR] [--dry-run]

khdp api METHOD PATH [--query K=V ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```

`--auth auto` 按以下顺序选择：API Token → 缓存的 OAuth → App Key。

## MCP 服务器

```bash
khdp mcp     # stdio 传输
```

| 工具 | 用途 |
| --- | --- |
| `khdp_auth_status`  | 是否已登录？令牌何时过期？ |
| `khdp_auth_refresh` | 轮换 refresh token。 |
| `khdp_auth_logout`  | 清除本地令牌。 |
| `khdp_api_request`  | 对任意 KHDP 端点进行认证 HTTP 透传。 |

MCP 服务器从不通过工具参数接收密码。登录通过用户终端中的 `khdp login` 在带外发起；MCP 服务器仅读取由此生成的令牌缓存。

## 代理 wrapper

| 平台 | 设置 |
| --- | --- |
| Claude Code | 运行 `claude mcp add khdp -- khdp-mcp` 并将 [`wrappers/claude-code/skills/khdp-auth`](./wrappers/claude-code/skills/khdp-auth) 复制到 `~/.claude/skills/` |
| OpenAI Codex CLI | 将 [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) 追加到 `~/.codex/config.toml` |
| Gemini CLI | 将 [`wrappers/gemini/settings.example.json`](./wrappers/gemini/settings.example.json) 合并到 `~/.gemini/settings.json` |

Cursor 使用相同的 MCP 服务器 — 在其 `mcp.servers` 配置中指向 `khdp-mcp`。

## 文档

- [Quickstart](./docs/quickstart.zh-CN.md) — 最初 5 分钟
- [REST API 参考](./docs/REST_API.md) — 端点、负载、scope、错误（英文）
- [`examples/`](./examples/) — 可运行的 Python 脚本（匿名检索、数据集详情、认证下载）
- [`AGENTS.md`](./AGENTS.md) — 从编码代理驱动 connector（英文）
- [规范说明](https://khdp.net/docs/external-api) — KHDP 官方文档站点

## 安全

- 在 loopback 重定向（RFC 8252）上进行 PKCE 登录（RFC 7636）。CLI 二进制中不包含客户端密钥。
- MCP 工具接口刻意省略密码参数 — 密码绝不会进入 LLM 上下文。
- 安装 `khdp[keyring]` 时令牌存储在操作系统密钥环中；否则保存在平台用户配置目录下权限为 `0600` 的 JSON 文件中。
- 按 `app_id` 隔离令牌。

完整威胁模型与报告政策见 [`SECURITY.md`](./SECURITY.md)。

## 开发

```bash
git clone https://github.com/KoreaHealthDataPlatform/khdp-api.git
cd khdp-api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## 许可证

MIT。参见 [LICENSE](./LICENSE)。
