# Release Process

`khdp` 의 PyPI 배포 절차. `main` 브랜치를 기준으로 한다.

PyPI 등록: https://pypi.org/project/khdp/ — Trusted Publishing
(`pypi` environment, GitHub Actions OIDC) 설정 완료.

---

## 1. 사전 확인

```bash
# 작업이 모두 main 에 머지되었는지
git checkout main && git pull origin main

# 테스트·린트
pip install -e '.[dev]'
ruff check src tests
pytest -q

# 빌드 통과
python -m pip install --upgrade build
python -m build
ls dist/
# → khdp-<version>.tar.gz, khdp-<version>-py3-none-any.whl
```

---

## 2. 버전 bump

```bash
# pyproject.toml
sed -i '' 's/^version = ".*"/version = "X.Y.Z"/' pyproject.toml
```

[Semantic Versioning](https://semver.org/) 기준:
- patch (`0.3.x`): 버그 수정 / 문서
- minor (`0.x.0`): 하위호환 기능 추가
- major (`x.0.0`): 호환 깨지는 변경

---

## 3. CHANGELOG 정리

`[Unreleased]` 섹션 아래에 `[X.Y.Z] - YYYY-MM-DD` 섹션을 새로 만들고
새 release 에 포함될 항목을 옮긴다. `[Unreleased]` 는 빈 채로 남겨 둠
(다음 작업이 쌓일 자리).

```markdown
## [Unreleased]

## [X.Y.Z] - 2026-MM-DD

### Added
- ...

### Changed
- ...
```

---

## 4. 커밋 + tag

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "release: vX.Y.Z"
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

---

## 5. GitHub Release 발행

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z" \
  --notes-file <(awk '/^## \[X.Y.Z\]/,/^## \[/{if(/^## \[X.Y.Z\]/||!/^## \[/)print}' CHANGELOG.md)
```

또는 웹 UI 에서 https://github.com/KoreaHealthDataPlatform/KHDPConnector/releases/new
에서 tag `vX.Y.Z` 선택 → "Publish release".

GitHub Release 가 published 되면 `.github/workflows/publish.yml` 이
자동 트리거되어:

1. `python -m build` 로 sdist + wheel 생성
2. `pypa/gh-action-pypi-publish@release/v1` 로 PyPI (`khdp`) 에 업로드

---

## 6. 검증

```bash
# PyPI 반영 (1-2분)
curl -s https://pypi.org/pypi/khdp/json | python3 -c \
  "import sys, json; print(json.load(sys.stdin)['info']['version'])"

# 설치 시 새 버전이 잡히는지
pipx install --force khdp
khdp --version
```

---

## 수동 publish (긴급)

GitHub Release 없이 즉시 publish 가 필요할 때 (예: hotfix):

```bash
gh workflow run publish.yml --ref main
```

`workflow_dispatch` 트리거. 단, version 이 PyPI 에 이미 있으면 publish
단계에서 거절된다 — 반드시 pyproject.toml version 이 새 값이어야 함.

---

## 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| publish step 이 403 (`Invalid token`) | PyPI Trusted Publishing 설정이 풀렸을 가능성. PyPI 프로젝트 settings > Publishing 에 GitHub repo + workflow + environment(`pypi`) 등록 재확인 |
| 같은 version 재업로드 실패 | PyPI 는 동일 version 재업로드를 허용하지 않음. version 을 bump 하거나 PyPI 에서 yank 후 재시도 |
| build 산출물 누락 | `pyproject.toml` 의 `[tool.hatch.build.targets.wheel] packages = ["src/khdp"]` 확인 |
| CI 는 통과인데 publish 가 안 트리거됨 | Release 가 "draft" 상태이면 트리거 안 됨 — "Publish release" 클릭 필요 |
