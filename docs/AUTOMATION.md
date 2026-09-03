# 정기 시장 브리프 자동화 운영 계약

현재 자동화는 **활성으로 인정하지 않습니다.** 실제 disabled receipt도 아직 없어 상태는 `NOT_PROVEN`이며,
운영상 중지로 취급합니다. TradingCodex Stop hook blocker와 공개 재출시 blocker가 해결될 때까지 새 정기 실행을
만들거나 켜지 않습니다.

## 1. 스케줄러는 하나만

기본 선택은 **Orca Automation**입니다. 대안은 **Codex Scheduled Tasks**입니다.

- 두 시스템을 동시에 사용하지 않습니다.
- 활성화 전, 선택하지 않은 스케줄러의 네 작업이 모두 `disabled` 또는 부재라는 현재 증거를 남깁니다.
- 증거는 작업 ID, 스케줄, timezone, enabled/disabled 상태, 확인 시각을 포함한 export 또는 screenshot입니다.
- 기존 실행 상태를 읽지 못하면 `NOT_PROVEN`으로 멈춥니다. 중복 가능성을 추정으로 넘기지 않습니다.
- 스케줄러를 바꿀 때는 기존 네 작업 disable → disable 증거 확인 → 새 네 작업 생성 순서입니다.

## 2. 정확한 네 일정

| 작업 | 현지 시각 | timezone | 출력 윈도 |
|---|---:|---|---|
| KR pre | 08:00 | `Asia/Seoul` | `KR / preopen` |
| KR close | 15:45 | `Asia/Seoul` | `KR / close` |
| US pre | 08:30 | `America/New_York` | `US / preopen` |
| US close | 16:15 | `America/New_York` | `US / close` |

미국 작업은 고정 UTC가 아니라 `America/New_York`를 사용해 DST를 따릅니다. 서버 기본 timezone에 의존하지 않습니다.

## 3. 저장 프롬프트 계약

모든 작업의 저장 프롬프트 **첫 줄**은 정확히 다음과 같습니다.

```text
$tcx-workflow
```

그 다음 줄부터 시장·윈도·cutoff·출력 계약을 적습니다. `$tcx-automate`는 이 정기 리서치 본문에 넣지 않습니다.
`$tcx-automate`는 자동화 자체의 생성·수정·상태 관리 절차가 필요할 때만 별도 대화에서 사용합니다.

최소 공통 본문:

```text
$tcx-workflow
지정된 시장과 윈도의 현재-run 공개 근거만 사용해 PublicBriefV3 후보를 준비한다.
개인 Investor Context, 개인 보유·계좌·포지션, 실거래 요청, 종목 추천·목표가를 사용하거나 출력하지 않는다.
모든 숫자와 주장은 공개 SourceRef, as_of, retrieved_at, evidence_status를 가진다.
근거가 부족하면 추정하지 말고 partial 또는 not_proven으로 표시한다.
JSON 후보와 검증 결과까지만 준비한다. commit, push, deploy, Slack·카카오톡 전송은 하지 않는다.
```

작업별로 다음 네 줄 중 하나를 공통 본문 뒤에 추가합니다.

```text
market=KR, window=preopen, timezone=Asia/Seoul, scheduled_local_time=08:00
market=KR, window=close, timezone=Asia/Seoul, scheduled_local_time=15:45
market=US, window=preopen, timezone=America/New_York, scheduled_local_time=08:30
market=US, window=close, timezone=America/New_York, scheduled_local_time=16:15
```

저장 프롬프트와 자연어는 실행·실거래·발행 권한을 만들지 않습니다. TradingCodex children에도 실거래 권한을 주지 않습니다.

## 4. 휴장·조기 종료·불완전 근거

### 휴장

- 해당 거래소의 공식 캘린더를 현재-run 근거로 확인합니다.
- 휴장이 확인되면 `status: "skipped_market_closed"`로 기록하고 거래가 있었던 것처럼 지표를 만들지 않습니다.
- 캘린더를 확인하지 못하면 휴장으로 추정하지 않고 `NOT_PROVEN`으로 멈춥니다.

### 미국 조기 종료

- 정규 스케줄을 영구 변경하지 않습니다.
- 공식 NYSE 일정으로 확인한 날짜에만 **한 번짜리 override**를 사람 승인을 받아 만듭니다.
- override와 기존 US close가 중복 실행되지 않는 disable/skip 증거를 남깁니다.
- 다음 정상 거래일 전에 16:15 `America/New_York` 일정으로 복귀했는지 확인합니다.

### partial / NOT_PROVEN

- 일부 핵심 출처가 지연되면 확인된 범위만 `partial`로 기록하고 누락 이유를 `missing_data[]`에 남깁니다.
- 핵심 사실을 뒷받침할 현재-run evidence가 없으면 `not_proven`으로 낮춥니다.
- 실패를 이전 세션 값, 메모리, 개인 보유 정보로 메우지 않습니다.
- retry는 같은 source의 일시 오류에만 bounded하게 사용하고, 증거 없이 성공 상태로 바꾸지 않습니다.

## 5. 공개는 사람 gate

자동 작업이 허용되는 마지막 단계는 다음입니다.

1. current-run evidence 기반 PublicBriefV3 후보 작성
2. `python3 scripts/verify_brief.py <candidate>` 결과 기록
3. 로컬 정적 빌드 후보와 reviewable diff 준비

다음은 자동화하지 않습니다.

- commit 또는 push
- production deploy
- Slack·카카오톡·이메일 전송
- 공개 링크 재홍보
- 실거래 ticket 작성·승인·제출 또는 실거래 API 호출

사람은 source rights, 공개 금지 정보, 상태, diff, receipt를 검토하고 별도로 발행을 승인합니다.

## 6. 현재 선행 blocker: TradingCodex Stop hook

현재 실측에서 TradingCodex Stop hook은 **exit code 0이지만 stdout이 0바이트**입니다. Codex가 요구하는 유효한
Stop hook JSON을 내지 않아 `hook returned invalid stop hook JSON output` 오류가 발생합니다.

자동화를 활성화하기 전에 다음 순서를 모두 완료해야 합니다.

1. TradingCodex **upstream/core**에서 Stop no-op이 유효한 JSON을 stdout으로 반환하도록 수정
2. 이 워크스페이스를 수동 패치하지 말고 TradingCodex 공식 update/refresh 경로로 반영
3. Codex 완전 재시작
4. **새 task**에서 Stop hook의 exit code, stdout JSON, 오류 부재를 다시 실측
5. 한 번의 수동 dry run에서 V3 후보 → verifier → build까지 확인
6. 그 뒤에만 Orca 또는 Codex Scheduled Tasks 중 하나를 활성화

현재 turn에서 생성된 workspace hook을 직접 고치는 것은 허용된 Build 범위가 아니며 공식 core 수정도 아닙니다.
오류가 대화 후크에서 보이더라도 이를 무시한 채 무인 정기 실행을 켜지 않습니다.

## 7. 활성화 증거

네 작업을 켠 뒤 다음 receipt가 모두 있어야 “활성”이라고 말할 수 있습니다.

- 선택한 스케줄러 이름과 네 작업 ID
- 각 cron/local time/timezone과 enabled 상태
- 반대 스케줄러 네 작업의 disabled/absent 증거
- 각 시장·윈도의 1회 수동 실행 결과와 current-run provenance ID
- 생성된 V3 candidate의 verifier 결과
- 자동 commit/push/deploy/send가 0회였다는 확인
- 다음 실행 예정 시각

이 중 하나라도 없으면 자동화 상태는 `NOT_PROVEN`입니다.
