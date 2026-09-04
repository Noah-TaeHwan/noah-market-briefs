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
