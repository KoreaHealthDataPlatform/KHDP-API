# Quickstart

[English](./quickstart.en.md) · [한국어](./quickstart.ko.md) · [Español](./quickstart.es.md) · **简体中文** · [日本語](./quickstart.ja.md)

> *AI 翻译。规范来源：[quickstart.en.md](./quickstart.en.md)。最近同步：2026-05-30。*

从零到一次成功的 KHDP API 认证调用 — 大约五分钟。

本指南是 [README](../README.md) 的补充。README 并列展示了四种入口；本文将 Python / CLI 路径走通到底，最后再接上 Claude Code。

## 开始之前

- Python ≥ 3.10
- 以下任一凭证：
  - **个人 API 令牌** — 最快：<https://khdp.net> → *Settings → Account → API Token*。一个以 `khdp_pat_…` 开头的字符串。
  - **`app_id`** — 如需 PKCE 登录，请向 KHDP 团队申请。CLI 类应用必须将 `http://127.0.0.1:*/callback` 注册为允许的重定向 URL。
- 代理步骤需要：已安装 [Claude Code](https://claude.com/claude-code)。

> 前三个步骤完全不需要 `app_id` — 只需要个人 API 令牌（公开搜索甚至无需任何凭证）。

## 1. 安装

```bash
pipx install khdp          # 与系统 Python 隔离
# 或
pipx install 'khdp[keyring]'   # 将令牌保存在操作系统密钥环中
```

验证：

```bash
khdp --version
khdp config              # 打印解析后的配置
```

## 2. 配置

选择一种方式，之后可以更改。

### 方式 A — 个人 API 令牌（推荐首次使用）

```bash
export KHDP_TOKEN="khdp_pat_…"
```

完成。无需 `khdp login`；所有调用直接使用令牌。长期有效，无需刷新。

### 方式 B — `app_id` + PKCE 登录

```bash
export KHDP_APP_ID="00000000-0000-0000-0000-000000000000"
khdp login                 # 打开浏览器，本地捕获回调
khdp status                # 确认：已认证，令牌过期时间
```

`--no-browser` 在无头/远程机器上直接打印 URL。

## 3. 搜索公开数据集（匿名可用）

CLI：

```bash
khdp datasets list --query heart --limit 5
```

从 Python 进行同样的调用：

```python
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    for d in r.json()["items"]:
        print(d["code"], "—", d["title"])
```

从输出中挑一个数据集 `code` — 本指南余下部分将其记作 `<CODE>`。

## 4. 检查 Open 策略的数据集

文件列表需要所用凭证具备 `datasets` scope。

```bash
khdp datasets show     <CODE>
khdp datasets files    <CODE>            # 根目录列表
khdp datasets files    <CODE> --prefix imaging/
```

> 若收到 `403 App does not have datasets scope`，请向 KHDP 团队申请为您的应用授予 `datasets` scope。所有调用方都适用。

## 5. 下载文件

先执行 dry-run 查看将发生什么 — 不传输字节：

```bash
khdp datasets download <CODE> --out ./data --dry-run
```

然后真正下载：

```bash
khdp datasets download <CODE> --out ./data
```

`download` 对服务器的 `files` 端点进行分页（每页 1000 个 key）并以流方式下载每个文件。当仅为验证流程时，使用 `--max-pages N` 在 N 页后停止。

> 下载仅适用于 `accessPolicy=open` 的数据集。Restricted / Credentialed / ContributorReview 会返回 `400 Is Not Open Access Dataset` — 请通过 KHDP 网页申请访问。

## 6. 从 Claude Code（MCP）调用

```bash
claude mcp add khdp -- khdp-mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

打开 Claude Code 并尝试：

> *"使用 khdp 工具在 KHDP 中搜索心脏疾病数据集，然后向我展示首条结果的文件列表。"*

Claude Code 会调用 MCP 服务器，而后者复用第 2 步建立的令牌缓存。密码不会经过 LLM 上下文。

同一个 MCP 服务器也支持 [OpenAI Codex CLI](../wrappers/codex/)、[Gemini CLI](../wrappers/gemini/) 和 Cursor。

## 常见问题

| 现象 | 可能原因 | 解决方法 |
| --- | --- | --- |
| 任意调用返回 `401` | 头部错误、OAuth 令牌过期，或环境不匹配 | `khdp status`；`khdp refresh`；检查 `khdp config` |
| `403 App does not have datasets scope` | 颁发令牌的应用缺少 `datasets` scope | 向 KHDP 团队申请 scope（OAuth 也适用） |
| `403 Auth type "openApiApp" is not allowed` | 在用户专用端点上未使用 OAuth/PAT | 改用 OAuth 或 PAT — submissions 仅限用户调用 |
| `404 Dataset Not Found` | `code` 错误或 `version` 未发布 | 省略版本（默认 `@latest`）或使用 `khdp datasets list` |
| 下载时 `400 Is Not Open Access Dataset` | 数据集非 Open 策略 | 外部 API 仅可下载 Open 数据集 |
| `khdp login` 挂起 | 应用未注册 loopback 重定向 URL | 请求 KHDP 运营团队注册 `http://127.0.0.1:*/callback` |
| 找不到 `khdp-mcp` 命令 | `pipx` 的 shim 路径不在 `PATH` 中 | 运行 `pipx ensurepath` 并重新打开 shell |

## 接下来阅读

- [API 参考 (Redoc)](https://khdp.ai/docs) — 每个端点、负载、scope 和错误（机器可读规范：<https://khdp.ai/openapi.json>）
- [`AGENTS.md`](../AGENTS.md) — 深入从编码代理驱动 connector（英文）
- [KHDP 规范](https://khdp.net/docs/external-api) — 官方站点
- [安全模型](../SECURITY.md) — PKCE、loopback 重定向、令牌存储、威胁模型（英文）
