# S1 섀도 운영 (판정만 기록, 발행 없음)

S0 게이트(`scripts/gate_check.py`)를 실세션에 20회 적용해 판정만 기록한다.
발행·commit·push·PR·브랜치 생성은 하지 않는다. S1 완료 후 임계값을 조정하고 S2로 간다.

## 작업 4개 (Orca, 전부 disabled로 생성 — enable은 별도 게이트)

| 작업 | 스케줄 (cron은 호스트 KST wall-clock) | ET 환산 | Orca ID |
|---|---|---|---|
| brief-kr-preopen-shadow | `0 8 * * *` = 08:00 KST | — | d9a9626a-c70c-4af1-8a2f-3d26428a2d09 |
| brief-kr-close-shadow | `45 15 * * *` = 15:45 KST | — | 89d491cc-edc7-41eb-9ecc-d90a945e7975 |
| brief-us-preopen-shadow | `30 21 * * *` = 21:30 KST | 08:30 EDT | 5078b6d9-c29d-40ad-bfb1-e516fe55793c |
| brief-us-close-shadow | `15 5 * * *` = 05:15 KST(익일) | 16:15 EDT | 5f5f2a91-0211-4df3-a049-f4c2cc12c44c |

- Orca CLI에 작업별 timezone 설정이 없어 cron은 호스트 wall-clock(KST)으로 평가된다 (실측:
  `30 8`이 23:30Z가 아니라 KST 08:30으로 잡힘). US 2작업은 ET→KST로 환산한 cron을 쓴다.
- DST 의무: EST 전환일(2026-11-01) 전에 US cron을 +1시간(21:30→22:30, 05:15→06:15 KST)으로
  옮겨야 하며, 옮긴 뒤 nextRunAt(12:30Z→13:30Z, 20:15Z→21:15Z)으로 검증한다.
- 발화 검증済み (2026-09-06 실측 nextRunAt): KR pre 23:00Z, KR close 06:45Z,
  US pre 12:30Z, US close 20:15Z — 전부 disabled.

- 생성 명령 형태: `orca automations create --name <위 이름> --trigger 'cron ...' --timezone <위>
  --repo id:a5cc7933-5e6f-44bf-8066-ec67721e1c7f --workspace-mode new-per-run
  --provider opencode --disabled --prompt '<아래 프롬프트>'`
- 반대편(Codex Scheduled Tasks)은 부재 확인済み (2026-09-06 실측: `~/.codex/automations/`에
  `.run-jitter-salt`만 존재, 작업 정의 없음).

## 프롬프트 팩 (작업별 첫 줄·시장줄만 다르고 본문 공통)

공통 본문 (AUTOMATION §3 계약 + S1 섀도 지시):

```text
시장 브리프 V3 후보 준비
<시장줄 — 작업별로 아래 4줄 중 하나>
지정된 시장과 윈도의 공식 1차 출처 직접 조회 결과만 사용해 PublicBriefV3 후보를 준비한다.
개인 Investor Context, 개인 보유·계좌·포지션, 실거래 요청, 종목 추천·목표가를 사용하거나 출력하지 않는다.
모든 숫자와 주장은 공개 SourceRef, as_of, retrieved_at, evidence_status를 가진다.
근거가 부족하면 추정하지 말고 partial 또는 not_proven으로 표시한다.
후보 JSON은 작업트리 내 data/YYYY/MM/DD/<window>.json 경로에만 작성한다.
python3 scripts/verify_brief.py --strict와
python3 scripts/gate_check.py <후보> --now <UTC-Z> --calendar <open|closed|unknown>를 실행한다.
calendar는 해당 거래소 공식 캘린더로 확인하고, 미확인이면 unknown으로 둔다.
commit·push·PR·브랜치 생성·전송을 하지 않는다.
최종 메시지로 판정 1행을 보고한다: 날짜|시장|윈도|verifier|G1..G9|종합판정.
```

시장줄:

```text
market=KR, window=preopen, timezone=Asia/Seoul, scheduled_local_time=08:00
market=KR, window=close, timezone=Asia/Seoul, scheduled_local_time=15:45
market=US, window=preopen, timezone=America/New_York, scheduled_local_time=08:30
market=US, window=close, timezone=America/New_York, scheduled_local_time=16:15
```

## 판정 로그 (S1 종료 시 run history에서 수집)

| # | 날짜 | 시장·윈도 | verifier | G1..G9 | 종합 | 인간 대조 |
|---|---|---|---|---|---|---|
| 0 | 2026-09-03 | US preopen | strict 통과 | P F F P F F P P P | HUMAN-GATE | 일치 (정정+partial 기록) |

- Entry 0은 2026-09-06에 기존 V3 기록으로 소급 측정한 baseline이다
  (재현: `--now 2026-09-06T12:00:00Z --calendar open`, clean tree에서 G7 PASS).
  G6 첫등장 FAIL은 레거시에 V3 sources가 없어서이며, V3가 쌓이면 해소되는 fail-closed 정상 동작이다.
  G7은 작업트리 상태 의존이라 측정 시점의 staged 파일이 있으면 FAIL할 수 있다.

## Enable 게이트 (충족 전에는 켜지 않는다)

- [ ] Codex 쪽 4작업 disabled/absent 증거 (본 문서에 기록済み — 재확인 필요 시점에만 갱신)
- [ ] 각 시장·윈도의 1회 수동 실행 결과 (AUTOMATION §6 — 현재 US preopen만 존재, 3개 부족)
- [ ] S1 판정 로그 20행 + 인간 대조 일치율 + 임계값 조정記録
- [ ] kill-switch 동작 확인 (4작업 일괄 disable 1회)
