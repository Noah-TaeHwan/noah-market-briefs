# 작업 로드맵

확정일: **2026-09-06**. 전체 순서를 고정한다. 페이즈를 건너뛰지 않는다.
2026-09-06 개정: TradingCodex 의존 제거 (Phase 0 삭제, 구 §6 Stop hook blocker 소멸).
2026-09-06 개정2: Phase 2 정정 — clean-room 이전은 9/3~4 완료済み. 남은 공개 검증은 카카오 unfurl 실측. 현재 트리 시크릿 스캔 0건.
에이전트 라우팅은 [AGENTS.md](../AGENTS.md), 공개 계약은 [ARCHITECTURE.md](ARCHITECTURE.md),
스케줄러 계약은 [AUTOMATION.md](AUTOMATION.md), 출처 게이트는 [SOURCES.md](SOURCES.md).

## 현재 상태

- 브리프 66건 중 65건은 v1/v2 레거시, 1건(2026-09-03 미국 장전)은 `status: corrected` + `evidence_status: partial` V3.
- `latest.json`은 슬롯 placeholder, RSS는 빈 channel이 정상.
- 자동화 `NOT_PROVEN`, 스케줄러 OFF. 카카오 unfurl 미검증. 구 원격(현 archived) 이어쓰기 경로만 BLOCKED(종결). 현 clean-room 원격은 스캔 0건.

## 페이즈

| 순서 | 작업 | 선행 조건 | 성공 기준 |
|---|---|---|---|
| 1 | V3 수동 발행 E2E 1건 | 다음 시장 세션 | verifier 통과 + 결정적 빌드 + 사람 승인 |
| 2 | 공개 검증 (카카오 unfurl 실측) | Phase 1 | production URL·unfurl 실측 |
| 3 | 자동화 활성화 (Orca 택1) | Phase 1·2 | 4작업 enabled + 반대편 disabled 증거 |
| 4 | 렌더러·UI 개선 | Phase 1·2 | V3 본문 기준 시각 검증 |

Phase 1의 수동 발행 결과물을 Phase 3 dry run으로 그대로 쓴다 (중복 작업 없음).

## 페이즈별 투입 (DAILY만)

- Phase 1: minimal-change, code-reviewer, research-synthesist, appsec, privacy, legal-compliance.
- Phase 2: appsec (스캔 0건), code-reviewer (diff 승인).
- Phase 3: backend-architect (스케줄 계약 대조), test-automation (회귀).
- Phase 4: technical-writer, accessibility-auditor, seo-specialist는 이때만 LIBRARY에서 호출.

## 공통 금지선

- 페이즈를 이유로 투자 권유·목표가·종목 추천을 출력하지 않는다.
- Phase 3까지 commit·push·deploy·전송 자동화 없음. 전부 사람 승인.
- 근거 없는 항목은 `partial`/`not_proven` + `missing_data[]`로 남기고 메우지 않는다.
