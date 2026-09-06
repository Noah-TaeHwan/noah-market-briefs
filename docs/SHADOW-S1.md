# 일일 발행 운영 (Orca 4작업)

하루 4회 후보 JSON을 쓰고 `scripts/publish_brief.sh`가 사이트로 올린다.
작업 이름 `*-shadow`는 유지한다. 프롬프트가 정본이다.

전송(Slack·카카오·메일)은 하지 않는다. 보유 종목·Investor Context는 쓰지 않는다.

## 작업 4개 (Orca, enabled)

| 작업 | 스케줄 (cron은 호스트 KST wall-clock) | ET 환산 | Orca ID |
|---|---|---|---|
| brief-kr-preopen-shadow | `0 8 * * *` = 08:00 KST | — | d9a9626a-c70c-4af1-8a2f-3d26428a2d09 |
| brief-kr-close-shadow | `45 15 * * *` = 15:45 KST | — | 89d491cc-edc7-41eb-9ecc-d90a945e7975 |
| brief-us-preopen-shadow | `30 21 * * *` = 21:30 KST | 08:30 EDT | 5078b6d9-c29d-40ad-bfb1-e516fe55793c |
| brief-us-close-shadow | `15 5 * * *` = 05:15 KST(익일) | 16:15 EDT | 5f5f2a91-0211-4df3-a049-f4c2cc12c44c |

- Repo: `id:a5cc7933-5e6f-44bf-8066-ec67721e1c7f`. provider `opencode`. `workspaceMode: new_per_run` (정본 checkout에 `existing` 금지).
- Orca CLI에 작업별 timezone 설정이 없어 cron은 호스트 wall-clock(KST)으로 평가된다.
- DST 의무: EST 전환일(2026-11-01) 전에 US cron을 +1시간(21:30→22:30, 05:15→06:15 KST)으로 옮긴다.
- 반대편(Codex Scheduled Tasks)은 부재 확인 (2026-09-06: `~/.codex/automations/`에 작업 정의 없음).
- `new_per_run`은 `origin/main`을 클론한다. `scripts/publish_brief.sh`가 main에 없으면 그 슬롯은 실패한다.

## 프롬프트 팩 (작업별 첫 줄·시장줄만 다르고 본문 공통)

```text
시장 브리프 V3 후보 준비
<시장줄 — 작업별로 아래 4줄 중 하나>
지정된 시장과 윈도의 공식 1차 출처 직접 조회 결과만 사용해 PublicBriefV3 후보를 준비한다.
개인 Investor Context, 개인 보유·계좌·포지션, 실거래 요청, 종목 추천·목표가를 사용하거나 출력하지 않는다.
모든 숫자와 주장은 공개 SourceRef, as_of, retrieved_at, evidence_status를 가진다.
근거가 부족하면 추정하지 말고 partial 또는 not_proven으로 표시한다.
후보 JSON은 작업트리 내 data/YYYY/MM/DD/<정본이름>.json 경로에 작성한다.
정본이름: korea-preopen.json / korea-close.json / us-preopen.json / us-close.json.
python3 scripts/verify_brief.py --strict와
python3 scripts/gate_check.py <후보> --now <UTC-Z> --calendar <open|closed|unknown>를 실행한다.
calendar는 해당 거래소 공식 캘린더로 확인하고, 미확인이면 unknown으로 둔다.
verify --strict가 통과하면 bash scripts/publish_brief.sh --calendar <동일값> [--now <UTC-Z>] <후보> 를 호출한다.
commit·push·PR을 에이전트가 직접 하지 않는다. 발행은 위 스크립트만 한다.
Slack·카카오톡·이메일 전송은 하지 않는다.
최종 메시지로 PR URL과 G1..G9 기록을 보고한다.
```

시장줄:

```text
market=KR, window=preopen, timezone=Asia/Seoul, scheduled_local_time=08:00
market=KR, window=close, timezone=Asia/Seoul, scheduled_local_time=15:45
market=US, window=preopen, timezone=America/New_York, scheduled_local_time=08:30
market=US, window=close, timezone=America/New_York, scheduled_local_time=16:15
```

## 발행 기록

| 날짜 | 시장·윈도 | verifier | 게이트 | 착지 |
|---|---|---|---|---|
| 2026-09-03 | US preopen | strict 통과 | HUMAN-GATE | PR #3 계열, V3 baseline |
| 2026-09-07 | KR preopen | strict 통과 | HUMAN-GATE | [PR #18](https://github.com/Noah-TaeHwan/noah-market-briefs/pull/18) |
| 2026-09-06 | KR close | strict 1/0/0 | G3/G5/G6/G7/G9 HUMAN-GATE, always_publish | [PR #19](https://github.com/Noah-TaeHwan/noah-market-briefs/pull/19) |

## Kill-switch

4작업을 한꺼번에 disable하면 일일 발행이 멈춘다. 브랜치 보호를 풀거나 `main`에 검사 없이 푸시하지 않는다.
