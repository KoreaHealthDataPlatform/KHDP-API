# Quickstart

[English](./quickstart.en.md) · [한국어](./quickstart.ko.md) · [Español](./quickstart.es.md) · [中文](./quickstart.zh-CN.md) · **日本語**

> *AI 翻訳。正本: [quickstart.en.md](./quickstart.en.md)。最終同期: 2026-05-30。*

ゼロから認証付きの KHDP API 呼び出しが成功するまで — 約 5 分。

本ガイドは [README](../README.md) を補完するものです。README が 4 つのエントリーポイントを並べて示すのに対し、ここでは Python / CLI のパスを最後まで通し、最後に Claude Code を組み込みます。

## 始める前に

- Python ≥ 3.10
- 以下のいずれかの資格情報:
  - **個人 API トークン** — 最速: <https://khdp.net> → *Settings → Account → API Token*。`khdp_pat_…` で始まる文字列です。
  - **`app_id`** — PKCE ログインが必要な場合は KHDP チームに申請してください。CLI 系のアプリは許可リダイレクト URL として `http://127.0.0.1:*/callback` を登録する必要があります。
- エージェントのステップ用: [Claude Code](https://claude.com/claude-code) のインストール。

> 最初の 3 ステップは `app_id` なしで完全に動作します — 個人 API トークン（または公開検索の場合は資格情報なし）だけで十分です。

## 1. インストール

```bash
pipx install khdp          # システム Python から分離
# または
pipx install 'khdp[keyring]'   # OS キーチェーンにトークンを保存
```

確認:

```bash
khdp --version
khdp config              # 解決された設定を表示
```

## 2. 設定

どちらかを選択してください。後から変更可能です。

### パス A — 個人 API トークン（初回に推奨）

```bash
export KHDP_TOKEN="khdp_pat_…"
```

これで完了。`khdp login` は不要で、すべての呼び出しがトークンを直接使用します。長寿命で refresh の必要がありません。

### パス B — `app_id` + PKCE ログイン

```bash
export KHDP_APP_ID="00000000-0000-0000-0000-000000000000"
khdp login                 # ブラウザを開きコールバックをローカルで受け取る
khdp status                # 確認: 認証済み、トークン有効期限
```

`--no-browser` はヘッドレス / リモート環境向けに URL を表示します。

## 3. 公開データセットを検索（匿名で可能）

CLI:

```bash
khdp datasets list --query heart --limit 5
```

Python で同じ呼び出し:

```python
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    for d in r.json()["items"]:
        print(d["code"], "—", d["title"])
```

出力からデータセットの `code` を 1 つ選んでください — 以降のガイドでは `<CODE>` と表記します。

## 4. Open ポリシーのデータセットを確認

ファイル一覧の取得には、利用する資格情報に `datasets` スコープが必要です。

```bash
khdp datasets show     <CODE>
khdp datasets files    <CODE>            # ルート一覧
khdp datasets files    <CODE> --prefix imaging/
```

> `403 App does not have datasets scope` が返る場合は、KHDP チームに該当アプリへの `datasets` スコープ付与を依頼してください。すべての呼び出し元に同様に適用されます。

## 5. ファイルのダウンロード

まずは dry-run で動作を確認 — バイトは転送されません:

```bash
khdp datasets download <CODE> --out ./data --dry-run
```

その後、実際のダウンロード:

```bash
khdp datasets download <CODE> --out ./data
```

`download` はサーバーの `files` エンドポイントをページネーション（1 ページあたり 1000 キー）し、各ファイルをストリーミング取得します。フローの検証だけ行いたい場合は `--max-pages N` で N ページ後に停止できます。

> ダウンロードは `accessPolicy=open` のデータセットに限ります。Restricted / Credentialed / ContributorReview は `400 Is Not Open Access Dataset` を返します — アクセス申請は KHDP の Web UI から行ってください。

## 6. Claude Code（MCP）から呼び出す

```bash
claude mcp add khdp -- khdp-mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

Claude Code を開いて試してみてください:

> *「khdp ツールを使って KHDP で心疾患関連のデータセットを検索し、トップヒットのファイル一覧を表示して。」*

Claude Code は MCP サーバーを呼び出し、MCP サーバーはステップ 2 で作られたトークンキャッシュを再利用します。パスワードが LLM コンテキストを通過することはありません。

同じ MCP サーバーは [OpenAI Codex CLI](../wrappers/codex/)、[Gemini CLI](../wrappers/gemini/)、Cursor もサポートしています。

## よくあるつまずき

| 症状 | 考えられる原因 | 対処 |
| --- | --- | --- |
| あらゆる呼び出しで `401` | ヘッダー誤り、OAuth トークンの期限切れ、または環境の不一致 | `khdp status`、`khdp refresh`、`khdp config` を確認 |
| `403 App does not have datasets scope` | トークンを発行したアプリに `datasets` スコープが無い | KHDP チームにスコープ付与を依頼（OAuth にも適用） |
| `403 Auth type "openApiApp" is not allowed` | ユーザー専用のエンドポイントを OAuth/PAT なしで呼び出した | OAuth または PAT を使用 — submission はユーザー専用 |
| `404 Dataset Not Found` | `code` 誤り、または `version` 未公開 | バージョンを省略（既定で `@latest`）または `khdp datasets list` を活用 |
| ダウンロード時に `400 Is Not Open Access Dataset` | データセットが Open ポリシーではない | 外部 API でダウンロードできるのは Open のみ |
| `khdp login` が応答しない | アプリに loopback リダイレクト URL が未登録 | KHDP 運用チームに `http://127.0.0.1:*/callback` の登録を依頼 |
| `khdp-mcp` コマンドが見つからない | `pipx` の shim パスが `PATH` に無い | `pipx ensurepath` を実行してシェルを開き直す |

## 次に読むもの

- [API リファレンス (Redoc)](https://khdp.ai/docs) — すべてのエンドポイント、ペイロード、スコープ、エラー（機械可読仕様: <https://khdp.ai/openapi.json>）
- [`AGENTS.md`](../AGENTS.md) — コーディングエージェントから connector を駆動する詳細（英語）
- [KHDP 正規仕様](https://khdp.net/docs/external-api) — 公式サイト
- [セキュリティモデル](../SECURITY.md) — PKCE、loopback リダイレクト、トークン保存、脅威モデル（英語）
