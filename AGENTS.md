# Noah Market Briefs — 작업면

## 정본

- GitHub: https://github.com/Noah-TaeHwan/noah-market-briefs
- 로컬: `~/projects/noah-market-briefs` (이 Orca worktree도 같은 git)
- 사이트: https://noah-market-briefs.vercel.app/market-briefs
- `main` 머지 → Vercel production. 빌드 명령 없음(정적 파일).

구 이름 `noah-market-briefs-public`은 같은 레포로 301이다. 새 링크는 `-briefs`로 쓴다.

## 쓰지 말 것

- https://github.com/Noah-TaeHwan/noah-market-briefs-archived
- `~/projects/noah-market-briefs-archived`
- 그 레포의 열린 PR #4 `feat/startup-mvp-relaunch` — 보존만

## 브랜치

`main`에 직접 commit·push하지 않는다. `<type>/<short>` 피처 브랜치 + PR.

## 파이프라인

`data/YYYY/MM/DD/<window>.json` → `scripts/verify_brief.py` → `scripts/build.py` → HTML/`latest.json`/`rss.xml`.
런타임 의존성 0. `build.py`를 바꾸면 생성물을 다시 돌리고 CI의 `git diff --exit-code`가 통과해야 한다.
commit/push/deploy/메신저 전송은 사람 승인. 스케줄러는 켜지 않는다 — [docs/AUTOMATION.md](docs/AUTOMATION.md).

## 공개 경계

PublicBriefV3 계약은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
개인 보유·계좌·내부 경로·Investor Context를 JSON/HTML/커밋에 넣지 않는다.
`data/.named-holdings.local`은 gitignore. 없어도 verifier는 돌아가고, 가드만 꺼진다.

## 에이전트 라우팅 (2026-09-06)

`.opencode/agents/` 273개 전체를 상시 쓰지 않는다. DAILY 8개만 쓰고 나머지는 LIBRARY로 둔다.
파일 삭제 없음. 새 에이전트 파일 없음. 이 섹션이 라우터다.

### DAILY (매 세션 로드 후보)

| 작업 | 에이전트 파일 | 근거 |
|---|---|---|
| 최소 diff 수정 | `engineering-minimal-change-engineer.md` | CI `git diff --exit-code`, 생성물 손수정 금지 |
| PR 리뷰 | `engineering-code-reviewer.md` | 피처 브랜치 + PR 강제 |
| 파이프라인 구조 변경 | `engineering-backend-architect.md` | `verify→build→HTML/JSON/RSS`, stdlib only |
| verifier·시크릿 스캔 | `security-appsec-engineer.md` | fail-closed, 배포 전 민감정보 스캔 0건 |
| 공개 경계 가드 | `engineering-privacy-engineer.md` | 보유·계좌·내부 경로·Investor Context 금지 |
| 브리프 내용 근거 합성 | `research-synthesist.md` | claims·반대근거·가설·`not_proven` 규율 |
| 출처 권리 게이트 | `support-legal-compliance-checker.md` | `docs/SOURCES.md` 체크리스트 |
| 회귀 테스트 | `testing-test-automation-engineer.md` | `unittest discover`, py3.11–3.13 CI |

### LIBRARY (필요할 때만, 검색·수동 지정)

- `finance-investment-researcher.md` — 기본 출력(Buy/Hold/Sell·목표가)은 이 저장소 면책 위반이라 **사용 금지**.
  수치 해석이 필요하면 `research-synthesist.md` 경유로 근거 합성만 한다.
- `engineering-devops-automator.md` — commit/push/deploy/전송은 사람 승인, 스케줄러 OFF(`docs/AUTOMATION.md`)라 평시 미사용.
- `engineering-technical-writer.md` — `docs/` 변경시에만.
- `testing-accessibility-auditor.md`, `marketing-seo-specialist.md` — 렌더러·CSS·OG/unfurl 변경시에만.
- 나머지 260+ (k8s·solidity·게임·위챗·라라벨 등) — off-stack. 삭제하지 않고 두되 로드하지 않는다.

### 금지선 (에이전트 공통)

- 투자 권유·매매 지시·목표가·종목 추천 출력 금지. 근거 부족은 `partial`/`not_proven` + `missing_data[]`.
- `data/.named-holdings.local`·credential·내부 ID를 JSON/HTML/커밋/로그에 넣지 않는다.
- 생성 HTML 직접 수정 금지. 입력 JSON 또는 렌더러 수정 후 전체 재빌드.

### 디자인 크루 (시각 작업시에만 로드, 순서대로)

| 순서 | 작업 | 에이전트 파일 |
|---|---|---|
| 1 | IA·정보구조 | `design-ux-architect.md` |
| 2 | 사용자 리서치 | `design-ux-researcher.md` |
| 3 | 비주얼 시스템 | `design-ui-designer.md` |
| 4 | 브랜드 일관성 | `design-brand-guardian.md` |
| 5 | 구현 (바닐라) | `engineering-frontend-developer.md` |
| 6 | 사용성 워크스루 | `design-persona-walkthrough.md` |
| 7 | 마감 게이트 | `design-ui-finish-gate-reviewer.md` |

- `product-manager.md` — 방향 정의시에만. `product-feedback-synthesizer.md` — 독자 피드백 있을 때만.
- `testing-accessibility-auditor.md`·`marketing-seo-specialist.md`(LIBRARY)는 디자인 검수에 합류.
- 디자인 하드 제약: 런타임 의존성 0 유지. CDN·웹폰트·외부 JS 프레임워크 금지.
  인터랙션은 빌드 시점에 데이터 박아넣은 바닐라 JS+CSS만. 상태·근거 배지(`정정됨`·`근거 일부` 등)는
  리디자인에서도 반드시 생존. 생성 HTML 손수정 금지(렌더러 수정 후 전체 재빌드).
