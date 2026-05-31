# Quickstart

[English](./quickstart.en.md) · **한국어** · [Español](./quickstart.es.md) · [中文](./quickstart.zh-CN.md) · [日本語](./quickstart.ja.md)

> *AI 번역. 정본: [quickstart.en.md](./quickstart.en.md). 마지막 동기화: 2026-05-30.*

KHDP API에 인증된 첫 호출이 성공하기까지 — 약 5분.

이 가이드는 [README](../README.md)를 보완합니다. README가 네 가지 진입 경로를 나란히 보여준다면, 여기서는 Python / CLI 경로를 끝까지 따라가고 마지막에 Claude Code 연결까지 마칩니다.

## 시작 전 준비

- Python ≥ 3.10
- 다음 중 하나의 자격증명:
  - **개인 API 토큰** — 가장 빠릅니다: <https://khdp.net> → *Settings → Account → API Token*. `khdp_pat_…`로 시작하는 문자열.
  - **`app_id`** — PKCE 로그인이 필요하다면 KHDP 팀에 신청하세요. CLI 계열 앱은 허용 리다이렉트 URL로 `http://127.0.0.1:*/callback`이 등록되어 있어야 합니다.
- 에이전트 단계용: [Claude Code](https://claude.com/claude-code) 설치 필요.

> 처음 세 단계는 `app_id` 없이도 완전히 동작합니다 — 개인 API 토큰만 있으면 됩니다 (공개 검색의 경우 자격증명도 불필요).

## 1. 설치

```bash
pipx install khdp          # 시스템 Python에서 격리
# 또는
pipx install 'khdp[keyring]'   # OS 키체인에 토큰 저장
```

확인:

```bash
khdp --version
khdp config              # 적용된 설정 출력
```

## 2. 설정

둘 중 하나의 경로를 선택하세요. 나중에 바꿔도 됩니다.

### 경로 A — 개인 API 토큰 (첫 실행에 권장)

```bash
export KHDP_TOKEN="khdp_pat_…"
```

이걸로 끝. `khdp login`이 필요 없고, 모든 호출이 직접 토큰을 사용합니다. 장기 토큰이며 refresh가 필요 없습니다.

### 경로 B — `app_id` + PKCE 로그인

```bash
export KHDP_APP_ID="00000000-0000-0000-0000-000000000000"
khdp login                 # 브라우저를 열어 콜백을 로컬에서 받음
khdp status                # 확인: 인증됨, 토큰 만료 시각
```

`--no-browser`는 헤드리스/원격 환경에서 URL만 출력합니다.

## 3. 공개 데이터셋 검색 (익명 가능)

CLI:

```bash
khdp datasets list --query heart --limit 5
```

Python에서 동일한 호출:

```python
from khdp import Session

with Session.open() as s:
    r = s.request("GET", "/datasets", params={"query": "heart", "limit": 5})
    for d in r.json()["items"]:
        print(d["code"], "—", d["title"])
```

출력에서 데이터셋 `code` 하나를 골라 두세요. 이후 단계에서는 `<CODE>`로 표기합니다.

## 4. Open 정책 데이터셋 살펴보기

파일 목록 조회에는 사용 중인 자격증명에 `datasets` 스코프가 필요합니다.

```bash
khdp datasets show     <CODE>
khdp datasets files    <CODE>            # 루트 목록
khdp datasets files    <CODE> --key imaging/
```

> `403 App does not have datasets scope`가 나면 KHDP 팀에 해당 앱의 `datasets` 스코프 부여를 요청하세요. 모든 호출자에게 동일하게 적용됩니다.

## 5. 파일 다운로드

먼저 dry-run으로 무엇이 처리될지 확인 — 바이트는 전송되지 않습니다:

```bash
khdp datasets download <CODE> --out ./data --dry-run
```

그 다음 실제 다운로드:

```bash
khdp datasets download <CODE> --out ./data
```

`download`는 서버의 `files-download-link-all` 엔드포인트를 페이지네이션(페이지당 1000키)하며 각 파일을 스트리밍합니다. 흐름만 검증할 때는 `--max-pages N`으로 N 페이지 후 중단할 수 있습니다.

> 다운로드는 `accessPolicy=open` 데이터셋에만 가능합니다. Restricted / Credentialed / ContributorReview 데이터셋은 `400 Is Not Open Access Dataset`을 반환합니다 — 접근 신청은 KHDP 웹 UI에서 진행하세요.

## 6. Claude Code(MCP)에서 호출

```bash
claude mcp add khdp -- khdp-mcp
cp -r wrappers/claude-code/skills/khdp-auth ~/.claude/skills/
```

Claude Code를 열고 시도:

> *"khdp 도구를 사용해서 KHDP에서 심장 질환 데이터셋을 검색하고, 상위 결과의 파일 목록을 보여줘."*

Claude Code가 MCP 서버를 호출하고, MCP 서버는 2단계에서 만들어진 토큰 캐시를 재사용합니다. 비밀번호는 LLM 컨텍스트를 거치지 않습니다.

동일한 MCP 서버가 [OpenAI Codex CLI](../wrappers/codex/), [Gemini CLI](../wrappers/gemini/), Cursor도 지원합니다.

## 흔한 함정

| 증상 | 가능한 원인 | 해결 |
| --- | --- | --- |
| 모든 호출에서 `401` | 헤더 오류, OAuth 토큰 만료, 또는 환경 불일치 | `khdp status`; `khdp refresh`; `khdp config` 확인 |
| `403 App does not have datasets scope` | 토큰을 발급한 앱에 `datasets` 스코프가 없음 | KHDP 팀에 스코프 요청 (OAuth에도 적용됨) |
| `403 Auth type "openApiApp" is not allowed` | 사용자 전용 엔드포인트를 OAuth/PAT 없이 호출 | OAuth 또는 PAT 사용 — submission은 사용자 전용 |
| `404 Dataset Not Found` | 잘못된 `code` 또는 미공개 `version` | 버전 생략 (`@latest`로 기본 설정) 또는 `khdp datasets list` 활용 |
| 다운로드 시 `400 Is Not Open Access Dataset` | 데이터셋이 Open 정책이 아님 | 외부 API로는 Open 데이터셋만 다운로드 가능 |
| `khdp login` 멈춤 | 앱에 loopback redirect URL 미등록 | KHDP 운영팀에 `http://127.0.0.1:*/callback` 등록 요청 |
| `khdp-mcp` 명령을 찾지 못함 | `pipx` 심볼릭 경로가 `PATH`에 없음 | `pipx ensurepath` 후 셸 재시작 |

## 다음에 읽을 것

- [API 레퍼런스 (Redoc)](https://khdp.ai/docs) — 모든 엔드포인트, 페이로드, 스코프, 에러 (기계 판독 spec: <https://khdp.ai/openapi.json>)
- [`AGENTS.md`](../AGENTS.md) — 코딩 에이전트로 connector를 자세히 다루기 (영어)
- [KHDP 공식 사양](https://khdp.net/docs/external-api) — 공식 사이트
- [보안 모델](../SECURITY.md) — PKCE, loopback redirect, 토큰 저장, 위협 모델 (영어)
