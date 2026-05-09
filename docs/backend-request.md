# KHDP 백엔드팀에게 — CLI/MCP 커넥터 인증 요청서

수신: KHDP 인증 백엔드 담당자
발신: KHDP 커넥터 프로젝트 (서울대병원, vital@snu.ac.kr)
주제: 외부 AI 코딩 에이전트(Claude Code, Codex CLI, Gemini CLI 등)에서
KHDP 데이터·도구를 안전하게 사용하기 위한 CLI 전용 인증 경로 신설 요청
저장소: <https://github.com/KoreaHealthDataPlatform/KHDPConnector>

## 배경

연구자들이 외부 AI 코딩 에이전트에서 KHDP 데이터·도구를 호출할 수
있도록 하는 **벤더 중립 커넥터**를 준비했습니다 (저장소 위 참조).
구조는 PLAN.md 의 3-tier 모델을 따르며, 1차 산출물은 **KHDP MCP 서버**
하나로 모든 에이전트가 동일한 인증·감사 정책 아래에서 KHDP를
호출하게 만드는 것입니다.

이 커넥터가 실제로 동작하려면 **CLI/MCP 서버에서 KHDP에 로그인할 수
있는 경로**가 필요한데, 현재 KHDP가 외부 앱에 제공하는 인증 흐름은
브라우저 기반이며 코드↔토큰 교환 단계가 각 등록앱의 백엔드 시크릿에
의존합니다. 그 시크릿을 공개 CLI 바이너리에 담을 수 없으므로, 현
구조 그대로는 헤드리스/터미널 환경에서 로그인이 불가능합니다.

## 현 상황 요약

* **브라우저 redirect 경로**: `/external/oauth-login?appId=&redirectUrl=`
  → 사용자 로그인 → `?code=` 리턴. 코드 교환은 각 등록앱의 백엔드가
  자기 시크릿으로 KHDP 서버측 API를 호출해 처리.
* **`POST /_api/oauth/login` (이메일+비번)**: 동작은 하지만 LLM/CI
  파이프라인에 비밀번호를 흘리는 형태가 되어 보안 모델이 약함. MFA
  도입 시 무용지물.
* **외부 토큰 갱신**: `POST /_api/member/refresh-token` 으로 가능.

즉, 토큰을 **얻는** 경로가 CLI 환경에 안전하지 않은 형태로만
열려있는 상황입니다.

## 요청 사항 (우선순위 순)

### A. (가장 권장) CLI 전용 앱 등록 + RFC 7636 PKCE 토큰 엔드포인트

CLI/MCP 같은 **public client**(시크릿을 보관할 수 없는 클라이언트)를
지원하기 위한 표준 패턴입니다. 작업량 대비 효과가 가장 큽니다.

요청 변경:

1. **새 앱 종류 "public client / CLI"** 를 KHDP 앱 등록 콘솔에 추가.
   - `redirectUrl` 화이트리스트에 `http://127.0.0.1:*` 와
     `http://localhost:*` 패턴 허용 (RFC 8252 §7.3 "Loopback
     Interface Redirection" 권장).
   - 클라이언트 시크릿 미발급. 그 자리에 PKCE 코드 검증으로 대체.

2. **공개 토큰 엔드포인트 신설**: `POST /_api/oauth/token`

   요청:
   ```http
   POST /_api/oauth/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=authorization_code
   &code=<code>
   &code_verifier=<verifier>
   &client_id=<appId>
   &redirect_uri=<127.0.0.1 callback>
   ```

   응답 (현 KHDP `/oauth/login` 응답과 동일 shape):
   ```json
   { "accessToken": "...", "refreshToken": "...", "expireTime": 1730000000000 }
   ```

   `/external/oauth-login` 진입 시 `code_challenge` / `code_challenge_method=S256`
   를 함께 받아 쿼리에 전달, 토큰 교환 시 `code_verifier`로 검증
   (RFC 7636).

3. **선택**: `grant_type=refresh_token` 도 같은 엔드포인트에서 받게
   하면 client 측 코드 단순화에 도움 (현 `/_api/member/refresh-token`
   유지해도 무관).

이 경로가 추가되면 **현재 `khdp-connector` 코드의 OAuth 분기를 그대로
사용**할 수 있습니다 (별도 설계 필요 없음).

### B. (대안 / 보완) Personal Access Token (PAT)

CI / 자동화 / 헤드리스 서버 환경을 위해 표준 OSS 패턴으로 KHDP 웹
UI에 다음을 추가:

* "내 계정 → API 토큰" 페이지에서 사용자가 직접 PAT 발급/폐기
* 발급 시 **scope**(예: `dataset.read`, `omop.query`) 와 **유효기간**
  선택 가능
* 발급된 PAT은 단순히 `Authorization: Bearer <token>` 헤더로 KHDP API
  호출 가능 (만료 / 폐기 외 자동 갱신 없음)

이는 **OAuth 흐름을 우회**하므로 사람이 일회성으로 명시적으로
발급하는 형태의 권한이 됩니다. 사용자별 감사 로그에는
`auth_method=pat` 식으로 별도 표기를 권장합니다.

### C. (최소) `/oauth/redirect-url` 의 익명 호출 허용

현재 `GET /_api/oauth/redirect-url?appId=&redirectUrl=` 가 KHDP 세션
쿠키 없이는 403입니다. CLI 가 사전검증을 못해서 사용자에게 친절한
에러 메시지를 줄 수 없습니다. 익명 호출에서 `(appId, redirectUrl)`
쌍의 **유효성**만 알려주면(true/false) 충분합니다. PII 없는 단순
검증이라 보안상 안전합니다.

## 부탁드리는 의사결정

1. **A안 (PKCE) 도입 가능 여부 / 일정**
2. A안 도입 전이라도 **`khdp-connector`용 CLI 앱 1개를 사전 발급** 받을
   수 있는지. 발급 시 필요한 정보:
   - 앱 이름: `khdp-connector` (또는 `KHDP CLI`)
   - 용도: 외부 AI 코딩 에이전트 통합 (오픈소스, Apache-2.0)
   - 예상 redirectUrl 패턴: `http://127.0.0.1:0~65535/callback`
3. B안(PAT)을 별도 트랙으로 추가 검토 가능 여부

## 참고

* RFC 8252 — OAuth 2.0 for Native Apps
  <https://datatracker.ietf.org/doc/html/rfc8252>
* RFC 7636 — Proof Key for Code Exchange (PKCE)
  <https://datatracker.ietf.org/doc/html/rfc7636>
* GitHub의 PAT 모델 (참고용):
  <https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>
* `khdp-connector` 저장소:
  <https://github.com/KoreaHealthDataPlatform/KHDPConnector>

## 연락

추가 논의 필요 시 vital@snu.ac.kr 로 회신 부탁드립니다. 백엔드
관점에서 타협 가능한 지점이 있다면 그쪽에 맞춰 커넥터 쪽 구현을
조정하겠습니다.
