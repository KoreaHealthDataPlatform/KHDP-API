# KHDP API

[English](./README.md) · **한국어** · [Español](./README.es.md) · [中文](./README.zh-CN.md) · [日本語](./README.ja.md)

> *AI 번역. 정본: [README.md](./README.md). 마지막 동기화: 2026-05-30.*

**대한민국 의료 데이터 플랫폼(Korea Health Data Platform)** 개발자 인터페이스 — `curl`, Python, 또는 AI 코딩 에이전트에서 의료 연구 데이터셋을 검색·다운로드·제출할 수 있습니다.

- REST API: `https://khdp.ai/v1` — <https://khdp.ai/docs> 참고.
- 익명 조회 가능. 인증(OAuth / API Token)을 통해 다운로드와 제출이 가능합니다.
- 동일한 인증 세션이 CLI, Python 라이브러리, 그리고 Claude Code · Codex CLI · Cursor · Gemini CLI용 MCP 서버를 함께 구동합니다.

> Repo: `khdp-api` · Python 패키지: `khdp` (`pip install khdp`).

## 빠른 시작 — API 호출 4가지 방법

### 1. curl
```bash
curl 'https://khdp.ai/v1/datasets?query=heart&limit=5' | jq '.items[].code'
```

### 2. Python (`khdp` SDK)
```python
# pip install khdp
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    print([d["code"] for d in r.json()["items"]])
```

### 3. Claude Code (MCP)
```bash
pip install khdp
khdp login
claude mcp add khdp -- khdp-mcp
```
이후 Claude Code에게: *"KHDP에서 심장 질환 관련 데이터셋을 검색하고 상위 결과를 요약해줘."*

### 4. OpenAI Codex CLI
[`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml)을 `~/.codex/config.toml`에 추가한 뒤 `khdp login` 한 번 실행.

> 자세한 안내: [docs/quickstart.ko.md](./docs/quickstart.ko.md). 엔드포인트 레퍼런스: <https://khdp.ai/docs>.

## AI 에이전트로 사용하기

AI 코딩 에이전트(Claude Code, OpenAI Codex, Google Antigravity, Cursor, Gemini CLI 등)에 KHDP를 다루게 하시려면 아래 프롬프트를 그대로 붙여넣으세요:

> https://khdp.ai/AGENTS.md 를 읽고 KHDP API 사용 지침을 그대로 따라주세요. 인증이 필요하면 진행 전에 **OAuth (브라우저 로그인)** 와 **PAT (개인 액세스 토큰)** 중 어느 쪽을 선호하는지 저에게 물어봐 주세요.

에이전트는 [`AGENTS.md`](./AGENTS.md) 를 읽어 `khdp` 설치, 인증 경로 선택, API 호출, 에러 처리, 데이터셋의 PHI-equivalent 취급까지 안내받습니다.

## 설치

```bash
pipx install khdp                 # 권장 — 시스템 Python에서 격리
pipx install 'khdp[keyring]'      # + OS 키체인에 토큰 저장
```

다음 3가지가 함께 설치됩니다:
- `khdp` — CLI (login, datasets, submissions, raw `api` 이스케이프)
- `khdp-mcp` — 코딩 에이전트용 MCP 서버
- `import khdp` — Python 라이브러리

## 인증

CLI · SDK · MCP에서 모두 사용 가능한 3가지 인증 방식.

| 방식 | 헤더 | 신원 | 일반 용도 |
| --- | --- | --- | --- |
| **OAuth (PKCE)** | `Authorization: Bearer <jwt>` | 사용자 | CLI, MCP, 사용자 권한 위임 SaaS |
| **API Token** (PAT) | `Authorization: Bearer khdp_pat_…` | 사용자 | 노트북, AI 에이전트 (장기 토큰, refresh 불필요) |

`app_id`는 KHDP 운영팀에 신청하세요. 개인 API 토큰은 <https://khdp.net>의 *Settings → Account → API Token*에서 발급받습니다.

```toml
# ./khdp.local.toml  (또는 ~/.config/khdp/config.toml)
app_id     = "00000000-0000-0000-0000-000000000000"
# api_key    = "khdp_pat_..."    # 개인 API 토큰
api_base   = "https://khdp.ai/v1"
```

또는 환경변수: `KHDP_APP_ID`, `KHDP_TOKEN`.

## CLI

```bash
khdp login [--no-browser]                              # PKCE 로그인 (loopback redirect)
khdp status | refresh | logout | config

khdp datasets list      [--query KW] [--policy open|restricted|...]
khdp datasets show      <code>[@<version>]
khdp datasets files     <code>[@<version>] [--prefix STR]
khdp datasets download  <code>[@<version>] [--out DIR] [--dry-run]

khdp api METHOD PATH [--query K=V ...] [--data '{...}']
                     [--auth {auto,app-key,api-key,oauth}]
```

`--auth auto`는 다음 순서로 자격증명을 선택합니다: API Token → 캐시된 OAuth.

## MCP 서버

```bash
khdp mcp     # stdio 전송
```

| 도구 | 용도 |
| --- | --- |
| `khdp_auth_status`  | 로그인 상태와 토큰 만료 시각 확인. |
| `khdp_auth_refresh` | refresh token 회전. |
| `khdp_auth_logout`  | 로컬 토큰 삭제. |
| `khdp_api_request`  | KHDP의 모든 엔드포인트에 인증된 HTTP 통과 호출. |

MCP 서버는 도구 인자로 비밀번호를 절대 받지 않습니다. 로그인은 별도로 사용자의 터미널에서 `khdp login`을 통해 수행되며, MCP 서버는 그 결과 토큰 캐시만 읽습니다.

## 에이전트 래퍼

| 플랫폼 | 설정 |
| --- | --- |
| Claude Code | `claude mcp add khdp -- khdp-mcp` 그리고 [`wrappers/claude-code/skills/khdp-auth`](./wrappers/claude-code/skills/khdp-auth)를 `~/.claude/skills/`에 복사 |
| OpenAI Codex CLI | [`wrappers/codex/config.example.toml`](./wrappers/codex/config.example.toml)을 `~/.codex/config.toml`에 추가 |
| Gemini CLI | [`wrappers/gemini/settings.example.json`](./wrappers/gemini/settings.example.json)을 `~/.gemini/settings.json`에 병합 |

Cursor는 같은 MCP 서버를 사용합니다 — `mcp.servers` 설정에서 `khdp-mcp`를 가리키도록 하세요.

## 문서

- [Quickstart](./docs/quickstart.ko.md) — 처음 5분
- [REST API 레퍼런스](https://khdp.ai/docs) — 엔드포인트, 페이로드, 스코프, 에러 (영어)
- [`examples/`](./examples/) — 실행 가능한 Python 스크립트 (익명 검색, 데이터셋 상세, 인증 다운로드)
- [`AGENTS.md`](./AGENTS.md) — 코딩 에이전트에서 connector 다루기 (영어)
- [공식 사양](https://khdp.net/docs/external-api) — KHDP 공식 문서 사이트

## 보안

- loopback redirect(RFC 8252) 기반 PKCE 로그인(RFC 7636). CLI 바이너리에 클라이언트 시크릿이 내장되어 있지 않습니다.
- MCP 도구 인터페이스는 비밀번호 파라미터를 의도적으로 노출하지 않습니다 — 비밀번호가 LLM 컨텍스트에 닿지 않습니다.
- `khdp[keyring]` 설치 시 OS 키체인에 토큰을 저장합니다. 그 외에는 플랫폼 사용자 설정 디렉터리의 `0600` JSON 파일에 저장됩니다.
- `app_id` 단위 토큰 격리.

전체 위협 모델과 제보 정책은 [`SECURITY.md`](./SECURITY.md) 참고.

## 개발

```bash
git clone https://github.com/KoreaHealthDataPlatform/khdp-api.git
cd khdp-api
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e '.[dev,keyring]'
pytest
```

## 라이선스

MIT. [LICENSE](./LICENSE) 참고.
