# Phase 1 실행 절차서 — 2026-09-07 KR 장전

목표: V3 후보 1건의 작성→검증→빌드→사람 승인. commit·push·deploy·전송 없음.

## 0. 고정값 (그대로 사용)

```text
경로: data/2026/09/07/korea-preopen.json
schema_version: 3, market_code: KR, window_code: preopen
market_session_date: 2026-09-07, market_timezone: Asia/Seoul
methodology_version: public-brief-v3
out_path: 2026/09/07/korea-preopen.html
```

세 슬롯 (값이 없어도 라벨 침묵 금지):

| 슬롯 | metric_id | missing_data.label (값 없을 때) |
|---|---|---|
| equity | metric-session-equity | 코스피 |
| fx | metric-session-fx | USD/KRW |
| vol | metric-session-vol | VKOSPI |

## 1. 후보 작성

- 공식 1차 출처 직접 조회만 사용 (KRX·OpenDART 우선, SOURCES.md 게이트).
- 모든 claim/metric에 `source_ids`+`as_of`+`evidence_status`. `cutoff_at_utc` ≥ 모든 `as_of`.
- 확보 안 되면 `partial`/`not_proven` + `missing_data[]`. 메우기 금지.
- 금지 키·값: verifier `V3_PRIVATE_KEY_NAMES`·`V3_PRIVATE_VALUE_PATTERN` + 보유·계좌·credential.

## 2. 검증·빌드 (순서대로, 하나라도 실패하면 중단)

```bash
python3 scripts/verify_brief.py --strict
python3 -m unittest discover -s tests
python3 scripts/build.py
git diff --check
```

결정적 빌드: 작업트리 변경이 있으면 빌드 전후 diff를 별도 파일로 저장해 비교
(README "로컬 실행과 검증" 참조).

## 3. 승인 전 게이트

- [ ] verifier `--strict` 통과
- [ ] 테스트 전부 통과
- [ ] 민감정보 스캔 0건 (verifier + diff 육안 확인)
- [ ] SOURCES.md 체크리스트 (공식 HTTPS·as_of/retrieved_at·최소 인용·권리 불명확≠confirmed)
- [ ] reviewable diff 준비 (생성 HTML 손수정 없음)

## 4. 실패 시

- verifier ERROR → 해당 레코드 제외 사유 기록, 다음 세션으로. 증거 없이 상태 올리기 금지.
- 성공 시 이 결과를 Phase 3 dry run으로 재사용 (중복 작업 없음).
