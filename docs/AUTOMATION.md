# 정기 시장 브리프 자동화 운영 계약

하루 4회 Orca 작업이 후보 JSON을 쓰고 `scripts/publish_brief.sh`가 사이트에 올린다.
G1–G9는 **기록만** 한다. 게이트가 HUMAN-GATE여도 `verify --strict`가 통과하면 그날 글은 발행한다.
Slack·카카오톡·이메일은 자동 보내지 않는다. 보유 종목·Investor Context는 JSON/HTML/커밋에 넣지 않는다.

끄려면 Orca 4작업을 한꺼번에 disable한다. Codex Scheduled Tasks와 동시에 켜지 않는다.

## 1. 스케줄러는 하나만

기본은 **Orca Automation**이다. 대안은 **Codex Scheduled Tasks**다.

- 두 시스템을 동시에 사용하지 않는다.
- 스케줄러를 바꿀 때는 기존 네 작업 disable → disable 증거 확인 → 새 네 작업 생성 순서다.
- 기존 실행 상태를 읽지 못하면 `NOT_PROVEN`으로 멈춘다. 중복을 추정으로 넘기지 않는다.

## 2. 정확한 네 일정

| 작업 | 현지 시각 | timezone | 출력 윈도 | 호스트 cron (KST) |
|---|---:|---|---|---|
| KR pre | 08:00 | `Asia/Seoul` | `KR / preopen` | `0 8 * * *` |
| KR close | 15:45 | `Asia/Seoul` | `KR / close` | `45 15 * * *` |
| US pre | 08:30 | `America/New_York` | `US / preopen` | `30 21 * * *` |
| US close | 16:15 | `America/New_York` | `US / close` | `15 5 * * *` |

Orca CLI는 작업별 timezone이 없다. cron은 호스트 wall-clock(KST)이다. US 두 작업은 ET→KST로 환산한다.
DST 의무: EST 전환일(2026-11-01) 전에 US cron을 +1시간(21:30→22:30, 05:15→06:15 KST)으로 옮긴다.

정본 파일명:

- `korea-preopen.json` / `korea-close.json` / `us-preopen.json` / `us-close.json`

`close.json` 같은 오명은 발행 스크립트가 위 네 이름 중 하나로 고친다.

## 3. 저장 프롬프트 계약

모든 작업의 저장 프롬프트 **첫 줄**은 정확히 다음과 같다.

```text
시장 브리프 V3 후보 준비
```

최소 공통 본문:

```text
시장 브리프 V3 후보 준비
지정된 시장과 윈도의 공식 1차 출처 직접 조회 결과만 사용해 PublicBriefV3 후보를 준비한다.
개인 Investor Context, 개인 보유·계좌·포지션, 실거래 요청, 종목 추천·목표가를 사용하거나 출력하지 않는다.
모든 숫자와 주장은 공개 SourceRef, as_of, retrieved_at, evidence_status를 가진다.
근거가 부족하면 추정하지 말고 partial 또는 not_proven으로 표시한다.
후보 JSON은 작업트리 내 data/YYYY/MM/DD/<정본이름>.json 경로에 작성한다.
python3 scripts/verify_brief.py --strict와
python3 scripts/gate_check.py <후보> --now <UTC-Z> --calendar <open|closed|unknown>를 실행한다.
calendar는 해당 거래소 공식 캘린더로 확인하고, 미확인이면 unknown으로 둔다.
verify --strict가 통과하면 bash scripts/publish_brief.sh --calendar <동일값> [--now <UTC-Z>] <후보> 를 호출한다.
Slack·카카오톡·이메일 전송은 하지 않는다.
최종 메시지로 PR URL과 G1..G9 기록을 보고한다.
```

작업별로 다음 네 줄 중 하나를 공통 본문 뒤에 추가한다.

```text
market=KR, window=preopen, timezone=Asia/Seoul, scheduled_local_time=08:00
market=KR, window=close, timezone=Asia/Seoul, scheduled_local_time=15:45
market=US, window=preopen, timezone=America/New_York, scheduled_local_time=08:30
market=US, window=close, timezone=America/New_York, scheduled_local_time=16:15
```

자연어는 실거래 권한을 만들지 않는다. 사이트 발행은 위 스크립트만 한다.

## 4. 휴장·조기 종료·불완전 근거

### 휴장

- 해당 거래소의 공식 캘린더로 휴장을 확인하고 `--calendar closed|open|unknown`에 넣는다.
- 휴장이어도 `verify --strict`가 통과하면 그날 후보는 발행한다. 게이트는 기록만.
- 캘린더를 확인하지 못하면 휴장으로 추정하지 않고 `unknown`으로 둔다.

### 미국 조기 종료

- 정규 스케줄을 영구 변경하지 않는다.
- 공식 NYSE 일정으로 확인한 날짜에만 **한 번짜리 override**를 사람 승인을 받아 만든다.
- override와 기존 US close가 중복 실행되지 않는 disable/skip 증거를 남긴다.
- 다음 정상 거래일 전에 16:15 `America/New_York` 일정으로 복귀했는지 확인한다.

### partial / NOT_PROVEN

- 일부 핵심 출처가 지연되면 확인된 범위만 `partial`로 기록하고 누락 이유를 `missing_data[]`에 남긴다.
- 핵심 사실을 뒷받침할 현재-run evidence가 없으면 `not_proven`으로 낮춘다.
- 실패를 이전 세션 값, 메모리, 개인 보유 정보로 메우지 않는다.
- retry는 같은 source의 일시 오류에만 bounded하게 사용하고, 증거 없이 성공 상태로 바꾸지 않는다.

## 5. 사이트 발행은 스크립트, 전송은 금지

허용되는 마지막 자동 단계는 `scripts/publish_brief.sh`다.

1. 공식 1차 출처 직접 조회 기반 PublicBriefV3 후보 작성
2. `python3 scripts/verify_brief.py --strict` — 실패하면 발행 중단 (아카이브 보호)
3. `python3 scripts/gate_check.py` — 결과만 로그. exit 1은 계속, exit 2(사용법)는 중단
4. `data/<date>-<slug>` 브랜치에 오늘 JSON + 생성 HTML + 이웃 adjacent-nav HTML + 해당 `YYYY/MM/DD/index.html`(4창구 상태 카드) + `index.html`/`latest.json`/`rss.xml`을 올린다
5. required CI(`verify` 3.11/3.12/3.13)가 초록이면 `gh pr merge --squash` (사람 PR 클릭 없음, `--admin` 금지)

자동화하지 않는다.

- Slack·카카오톡·이메일 전송
- 공개 링크 재홍보
- 실거래 ticket 작성·승인·제출 또는 실거래 API 호출
- `main` 직접 push, 브랜치 보호 해제, required check 없이 머지

코드·문서 변경은 계속 `<type>/<short>` 피처 브랜치 + PR이다. 브리프 JSON과 생성 사이트 파일만 이 스크립트가 올린다.

Vercel 빌드 명령은 없다. JSON만 올리면 화면이 안 바뀐다.

## 5-2. 폐기 — S3-only 자동 머지

예전 계약(G1–G9 전부 PASS일 때만 자동 머지, S0→S3 단계 상승)은 폐기했다.
현재 계약은 §5 `always_publish`다. 게이트는 기록만.

## 6. 활성 증거와 kill-switch

네 작업이 enabled이고 아래가 있으면 자동화를 활성으로 말한다.

- 스케줄러 이름 Orca, 작업 ID 네 개 — [docs/SHADOW-S1.md](SHADOW-S1.md)
- 각 cron/local time과 enabled 상태
- 반대 스케줄러(Codex Scheduled Tasks) 작업 정의 부재
- leftover 착지: 2026-09-06 KR close → [PR #19](https://github.com/Noah-TaeHwan/noah-market-briefs/pull/19) · production `2026/09/06/korea-close.html`
- 전송 자동화 0회

kill-switch: Orca 4작업을 한꺼번에 disable. 새 스케줄러나 Codex cron을 만들지 않는다.
