# KHDP API

[English](./README.md) · [한국어](./README.ko.md) · [Español](./README.es.md) · [中文](./README.zh-CN.md) · **日本語**

> *AI 翻訳。正本: [README.md](./README.md)。最終同期: 2026-05-30。*

**Korea Health Data Platform**（韓国医療データプラットフォーム）の開発者向けインターフェイス — `curl`、Python、または任意の AI コーディングエージェントから医療研究データセットを検索・ダウンロード・提出できます。

- REST API は `https://khdp.ai/v1` — <https://khdp.ai/docs> を参照。
- 匿名閲覧が可能。認証（OAuth / API Token）によりダウンロードと提出が解放されます。
- 同一の認証セッションが CLI、Python ライブラリ、そして Claude Code・Codex CLI・Cursor・Gemini CLI 向けの MCP サーバーを動かします。

> リポジトリ: `khdp-api` · Python パッケージ: `khdp`（`pip install khdp`）。

## クイックスタート — API を呼ぶ 4 つの方法

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
そして Claude Code に: *「KHDP で心疾患関連のデータセットを検索して、上位の結果を要約してください。」*

### 4. OpenAI Codex CLI
[`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) を `~/.codex/config.toml` に追記し、一度だけ `khdp login` を実行します。

> 詳しいガイド: [docs/quickstart.ja.md](./docs/quickstart.ja.md)。エンドポイントリファレンス: <https://khdp.ai/docs>。

## AI エージェントから使う

AI コーディングエージェント（Claude Code、OpenAI Codex、Google Antigravity、Cursor、Gemini CLI など）から KHDP を使いますか？次の文をエージェントに貼り付けてください：

> https://khdp.ai/AGENTS.md を読み、KHDP API の指示にそって作業してください。認証が必要になったら、進める前に **OAuth（ブラウザログイン）** と **PAT（個人アクセストークン）** のどちらを希望するか私に確認してください。

エージェントはその後 [`AGENTS.md`](./AGENTS.md) を読み込み、`khdp` のインストール、認証方法の選定、API 呼び出し、エラー対応、データセット内容を PHI 同等として扱う指針までを得ます。

## インストール

```bash
pipx install khdp                 # 推奨 — システム Python から分離
pipx install 'khdp[keyring]'      # + OS キーチェーンにトークンを保存
```

このパッケージにより以下が利用可能になります:
- `khdp` — CLI（login、datasets、submissions、生の `api` エスケープ）
- `khdp-mcp` — コーディングエージェント向けの MCP サーバー
- `import khdp` — Python ライブラリ

## 認証

CLI・SDK・MCP の間で互換的に使える 3 種類の資格情報。

| 種別 | ヘッダー | アイデンティティ | 主な用途 |
| --- | --- | --- | --- |
| **OAuth (PKCE)** | `Authorization: Bearer <jwt>` | ユーザー | CLI、MCP、ユーザーの代理として動作する SaaS |
| **API Token**（PAT） | `Authorization: Bearer khdp_pat_…` | ユーザー | ノートブック、AI エージェント（長寿命、refresh 不要） |

`app_id` は KHDP チームに申請してください。個人 API トークンは <https://khdp.net> の *Settings → Account → API Token* から発行できます。

```toml
# ./khdp.local.toml  （または ~/.config/khdp/config.toml）
app_id     = "00000000-0000-0000-0000-000000000000"
# api_key    = "khdp_pat_..."    # 個人 API トークン
api_base   = "https://khdp.ai/v1"
```

または環境変数: `KHDP_APP_ID`、`KHDP_TOKEN`。

## CLI

```bash
khdp login [--no-browser]                              # PKCE ログイン（loopback リダイレクト）
khdp status | refresh | logout | config

khdp datasets list      [--query KW] [--policy open|restricted|...]
khdp datasets show      <code>[@<version>]
khdp datasets files     <code>[@<version>] [--key PREFIX]
khdp datasets download  <code>[@<version>] [--out DIR] [--dry-run]

khdp api METHOD PATH [--query K=V ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```

`--auth auto` は次の順序で資格情報を選択します: API Token → キャッシュ済み OAuth。

## MCP サーバー

```bash
khdp mcp     # stdio トランスポート
```

| ツール | 用途 |
| --- | --- |
| `khdp_auth_status`  | ログイン状態とトークンの有効期限を確認。 |
| `khdp_auth_refresh` | refresh token をローテート。 |
| `khdp_auth_logout`  | ローカルトークンを削除。 |
| `khdp_api_request`  | KHDP の任意のエンドポイントに対する認証付き HTTP パススルー。 |

MCP サーバーはツール引数からパスワードを受け取りません。ログインはユーザーのターミナルから `khdp login` で帯域外に実行され、MCP サーバーは生成されたトークンキャッシュを読み取るだけです。

## エージェントラッパー

| プラットフォーム | 設定 |
| --- | --- |
| Claude Code | `claude mcp add khdp -- khdp-mcp` を実行し、[`wrappers/claude-code/skills/khdp-auth`](./wrappers/claude-code/skills/khdp-auth) を `~/.claude/skills/` にコピー |
| OpenAI Codex CLI | [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml) を `~/.codex/config.toml` に追記 |
| Gemini CLI | [`wrappers/gemini/settings.example.json`](./wrappers/gemini/settings.example.json) を `~/.gemini/settings.json` にマージ |

Cursor は同じ MCP サーバーを利用します — `mcp.servers` 設定で `khdp-mcp` を指定してください。

## ドキュメント

- [Quickstart](./docs/quickstart.ja.md) — 最初の 5 分
- [REST API リファレンス](https://khdp.ai/docs) — エンドポイント、ペイロード、スコープ、エラー（英語）
- [`examples/`](./examples/) — 実行可能な Python スクリプト（匿名検索、データセット詳細、認証付きダウンロード）
- [`AGENTS.md`](./AGENTS.md) — コーディングエージェントから connector を駆動する（英語）
- [正規仕様](https://khdp.net/docs/external-api) — KHDP 公式ドキュメントサイト

## セキュリティ

- loopback リダイレクト（RFC 8252）の上での PKCE ログイン（RFC 7636）。CLI バイナリにクライアントシークレットを含みません。
- MCP ツール表面は意図的にパスワード引数を持ちません — パスワードが LLM コンテキストに到達することはありません。
- `khdp[keyring]` をインストールした場合は OS キーチェーンに、それ以外は OS のユーザー設定ディレクトリ下の `0600` JSON ファイルにトークンを保存します。
- `app_id` 単位のトークン分離。

完全な脅威モデルと報告ポリシーは [`SECURITY.md`](./SECURITY.md) を参照。

## 開発

```bash
git clone https://github.com/KoreaHealthDataPlatform/khdp-api.git
cd khdp-api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## ライセンス

MIT。[LICENSE](./LICENSE) を参照。
