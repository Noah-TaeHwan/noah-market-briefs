# V3 세션 최소 슬라이스 — 설계 문서

**작성일:** 2026-09-04
**제품:** Noah Market Briefs
**상태:** 승인됨. 구현 계획 `docs/superpowers/plans/2026-09-04-v3-session-min-slice.md`.
**결정:** Approach A. 새 최상위 필드 없음.

## 1. 문제와 근거

공개 V3는 `data/2026/09/03/us-preopen.json` 하나다. JOLTS 네 지표는 `confirmed`이고, 같은 세션의 지수·환율·변동성은 `missing_data` 한 줄로만 묶여 있다. 이후 US·KR V3도 같은 침묵이 가능하면 브리프가 다시 얇아진다.

북극성은 C→B→D다. 이 슬라이스는 브리프 품질이다. 방문자 크롬, 작성 UX, 가설 루프, 보유 민감도, 자동화, 카카오/Slack은 범위 밖이다.

## 2. 목표

`schema_version == 3`인 모든 공개 레코드는 세 세션 슬롯을 **침묵하지 않는다.** 각 슬롯은 정규 `metric_id` 메트릭이거나, 아래 표의 정확한 `missing_data.label`이다. 값이 없어도 공개는 된다. 슬롯이 둘 다 없으면 ERROR다.

## 3. 비목표

- V3 최상위·중첩 스키마에 `equity`/`fx`/`vol` 객체를 추가하지 않는다.
- `hypotheses[]`/`reviews[]` 루프를 이 슬라이스에서 켜지 않는다.
- `brief_id`·`out_path`·URL을 바꾸지 않는다. `status=corrected` 이중 레코드를 만들지 않는다.
- `cutoff_at_utc`를 시장 종가를 넣으려고 앞당기지 않는다.
- 유료 터미널, DXY, 실시간 시세, 스케줄러, 카카오 unfurl, Slack 공개 공유를 켜지 않는다.
- KR V3 JSON을 새로 만들지 않는다. 계약만 잠근다.
- 미커밋 위생(`AGENTS.md` 등)을 이 PR에 섞지 않는다.
- source rights·숫자 진위는 verifier가 보증하지 않는다. 사람 PR 게이트다.

## 4. 슬롯 계약

`market_code`로 라벨만 갈린다. `metric_id`는 US/KR 공통이다. 환율은 USD/KRW만 쓴다.

| 슬롯 | `metric_id` | US `missing_data.label` | KR `missing_data.label` | US 시리즈 | KR 시리즈 |
|---|---|---|---|---|---|
| equity | `metric-session-equity` | `S&P 500` | `코스피` | FRED `SP500` | 코스피 |
| fx | `metric-session-fx` | `USD/KRW` | `USD/KRW` | FRED `DEXKOUS` | USD/KRW |
| vol | `metric-session-vol` | `VIX` | `VKOSPI` | FRED `VIXCLS` | VKOSPI |

커버리지(슬롯당, OR):

1. `metrics[]`에 해당 `metric_id`가 있다. 표시 `label`은 자유다.
2. `missing_data[]`에 위 표의 **완전 일치** label이 있다. 부분 문자열·묶음 라벨(`같은 세션의 주가지수·환율·변동성`)은 어떤 슬롯도 커버하지 않는다.

메트릭과 missing이 같은 슬롯에 같이 있으면 통과한다. `metric_id` 중복 금지는 이 슬라이스에서 추가하지 않는다.

적용 대상: `schema_version == 3` 전부(`partial`/`published`/`failed`/`skipped_market_closed`/`corrected`). v1/v2는 그대로 둔다.

Verifier는 슬롯 침묵만 ERROR로 올린다. `status`를 슬롯 채움에 따라 바꾸거나 강제하지 않는다.

작성 규칙(사람·JSON, verifier 밖):

- 세 슬롯 중 하나라도 missing이면 `status`는 `partial`을 유지한다.
- 세 슬롯이 모두 메트릭이면 `published`로 올려도 된다.
- 기존 묶음 `missing_data` 한 줄은 지우고, 슬롯별 메트릭 또는 슬롯별 missing으로 바꾼다.

## 5. 시각·출처

이미 있는 규칙: `cutoff_at_utc` ≤ `generated_at_utc`. 이 슬라이스에서 cutoff를 바꾸지 않는다.

추가: parse 가능한 V3 `metrics[].as_of`는 모두 `cutoff_at_utc`보다 늦으면 ERROR다. 세션 슬롯만이 아니라 기존 JOLTS 메트릭에도 같은 가드를 쓴다.

US 숫자 출처(구현 시 공개 페이지에서 사람이 옮김):

- https://fred.stlouisfed.org/series/SP500
- https://fred.stlouisfed.org/series/DEXKOUS (`Won per USD`)
- https://fred.stlouisfed.org/series/VIXCLS

관측값은 **cutoff 이하인 마지막 공식 일별 종가**다. preopen이라고 cutoff 이후의 “세션 전일 종가”를 넣지 않는다. 이번 US 레코드의 cutoff는 `2026-09-01T14:00:00Z`(ET 10:00, 당일 정규장 마감 전)이므로, 세션일 `2026-09-03`의 전일 종가(9/2)는 cutoff 밖이다. 그때는 (a) cutoff 이하 마지막 프린트를 메트릭으로 넣고 `note`에 관측일과 cutoff 경계를 쓰거나, (b) 해당 슬롯을 missing으로 남긴다. 공개 페이지에서 숫자를 못 가져오면 (b)다. 숫자를 지어내지 않는다.

KR은 이후 첫 V3에서 KRX/BOK 공개 페이지를 쓴다. 이번 PR에 KR JSON은 없다.

SourceRef는 기존 닫힌 필드만. HTTPS. `source_id`는 payload 안 유일. 유료 터미널 URL 금지.

`public_receipt_sha256`는 형식만 검사하는 기존 정책을 유지한다. 이 슬라이스에서 해시를 재계산하지 않는다.

## 6. 이번 PR이 만지는 파일

| 파일 | 역할 |
|---|---|
| `scripts/verify_brief.py` | 세 슬롯 커버리지 + 메트릭 `as_of` ≤ cutoff |
| `tests/test_verify.py` | 픽스처를 새 계약에 맞추고 아래 네 테스트 추가 |
| `data/2026/09/03/us-preopen.json` | 유일 실데이터 패치. summary/`next_handoff`/묶음 missing을 결과에 맞게 고친다 |
| `docs/ARCHITECTURE.md` | 슬롯 계약 한 소절. 스키마 표에 필드를 추가하지 않는다 |
| `scripts/build.py` 산출물 | 같은 PR에서 `build.py` 재생성. 렌더러 로직은 JSON이 바뀌면 따라간다. 새 템플릿 분기 없음 |

`_valid_v3_record()`는 KR이다. 기존 `metric-kospi`를 세션 슬롯으로 재해석하지 않는다. 픽스처에 KR 세 라벨 missing(또는 세 세션 메트릭)을 넣어 기존 V3 테스트가 침묵 ERROR로 무너지지 않게 한다. `test_v3_accepts_closed_public_support_fields`의 `missing_data`도 세 정규 라벨을 포함해야 한다.

`tests/test_build.py`의 렌더 스텁은 verifier를 타지 않으면 그대로 둔다.

## 7. 테스트

TDD. 구현 전에 실패하는 테스트부터.

1. 세 슬롯 침묵 → ERROR
2. 세 정규 missing label → 통과
3. 세 세션 메트릭 → 통과
4. 메트릭 둘 + missing 하나 → 통과

그다음 `python3 -m unittest discover -s tests -v`, `python3 scripts/verify_brief.py --strict`, `python3 scripts/build.py`. 신규 의존성·네트워크 호출 없음. 숫자의 참/거짓은 테스트가 아니라 PR 리뷰다.

## 8. 품질·출시 경계

- 기존 skip link, 상태 배지, 투자 권유 아님, 공개 payload 경계를 유지한다.
- 부분 공개를 완전 시장 브리프로 위장하지 않는다. cutoff 밖 종가를 세션 전일 종가처럼 쓰지 않는다.
- commit/push 전에 `/ponytail-review`와 `bash ~/.agents/hooks/record-ponytail-review.sh`.
- 제품은 `<type>/<short>` + PR. `main` 직접 커밋 금지.
- 자동화 활성화와 카카오/Slack은 이 PR에서 실행하지 않는다.

## 9. 결정

세션 최소 슬라이스는 닫힌 V3 목록(`metrics[]`, `missing_data[]`, `sources[]`)만 사용한다. 구현은 이 문서 승인 및 writing-plans 작성 뒤에만 시작한다.
