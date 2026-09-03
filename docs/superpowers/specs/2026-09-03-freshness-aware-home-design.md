# 최신성 인식형 홈 — 설계 문서

**작성일:** 2026-09-03
**제품:** Noah Market Briefs
**Enterprise Feature run:** run_0fc5e730547f
**결정권자:** Noah의 위임에 따른 coordinator 결정
**상태:** Phase 1 설계 확정, 로컬 구현 승인 범위

## 1. 문제와 근거

현재 production 홈은 한국 장전·한국 마감·미국 장전·미국 마감의 4개 고정 슬롯을 유지한다. 이 비교 구조는 유용하지만, 2026-09-03의 부분 공개 V3 기록 하나와 2026-07-16~17의 레거시 미검증 기록 세 개를 같은 시각적 무게로 보여 준다.

2026-09-03 직접 확인 결과:

- 홈·상세·latest.json·rss.xml·CSS 등 주요 경로는 HTTP 200이다.
- latest.json의 4개 슬롯 중 V3 partial/confirmed는 미국 장전 1개이고 나머지 3개는 legacy_unverified다.
- 홈은 최신 4개 세션이라는 제목 아래 고정 순서를 사용하므로 가장 최근 기록이 세 번째 카드에 놓인다.
- 상세 페이지는 근거와 누락 데이터를 정직하게 표시하지만, 사용자는 상세로 들어가기 전까지 해당 기록이 시장 데이터 전체가 아닌 최소 BLS slice라는 사실을 알기 어렵다.
- 독립 UX curl 감사도 최신 기록 찾기, 아카이브 탐색, 최신성 판별을 첫 번째 개선 대상으로 확인했다.
- 기존 production QA receipt는 접근성·SEO·Best Practices·Agentic Browsing 각 100점, 모바일 가로 오버플로 없음, 콘솔·실패 네트워크 0을 기록한다. 이 설계는 그 기준선을 유지해야 한다.

## 2. 목표

첫 화면에서 독자가 다음을 10초 안에 판단할 수 있게 한다.

1. 가장 최근 기준일의 기록이 무엇인가.
2. 그 기록의 공개 상태와 근거 상태는 무엇인가.
3. 4개 시장 창구 중 어떤 기록이 최신 기준이고, 어떤 기록이 이전/레거시인가.
4. 고정 4슬롯 비교를 계속 읽으려면 어디를 클릭해야 하는가.

## 3. 비목표

- 실시간 시세, 자동 새로고침, 다음 발행 예정 시각을 추가하지 않는다.
- 로그인, 사용자 계정, 저장/팔로우, 이메일·Slack·카카오 알림을 추가하지 않는다.
- 기존 4개 슬롯의 시장·윈도 순서와 레코드 선택 규칙을 바꾸지 않는다.
- 현재 부분 공개 레코드를 완전한 시장 브리프로 승격하지 않는다.
- source rights, 원출처 진위, 투자 판단의 타당성을 verifier가 보증한다고 표현하지 않는다.
- 자동화·카카오톡·Slack·기타 외부 공유는 이 수직 슬라이스에 포함하지 않는다.

## 4. 제안 경험

### 4.1 현재 읽기 패널

고정 4슬롯보다 먼저 현재 읽기 영역을 렌더한다. 여기서 현재는 실시간 상태가 아니라 전체 입력 레코드 중 가장 최근 market_session_date를 뜻한다.

표시 계약:

- eyebrow: 가장 최근 기록
- 제목: 최신 레코드의 실제 title 링크
- 날짜: 최신 레코드의 market_session_date를 time[datetime]으로 표시
- 상태: 기존 status_badge()가 생성하는 상태·근거 텍스트를 그대로 사용
- 설명: 부분 공개, 레거시 미검증, 근거 일부, 미검증을 데이터에서 계산해 사람이 읽는 상태 문장으로 표시
- 주 행동: 가장 최근 브리프 읽기 →

패널은 최신·현재 시장·예측 완료 같은 실시간/정확성 주장을 하지 않는다. 최신 레코드가 없으면 아직 읽을 검증 기록 없음과 기존 빈 슬롯 안내만 보여 준다.

### 4.2 4슬롯 상태 요약

현재 읽기 패널 하단에 다음과 같은 데이터 기반 요약을 둔다.

기준일 YYYY-MM-DD · 4개 창구 중 N개 기록 · M개 레거시 미검증 · P개 부분 공개

각 숫자는 최신 슬롯 집합에서 계산한다. 해당 상태가 0이면 그 항목은 생략해 문장을 짧게 유지한다. 문장만으로 상태를 전달하며 색상은 보조 수단이다.

### 4.3 기존 4슬롯 카드

현재 읽기 패널 뒤에 기존 4슬롯을 유지하되 다음을 추가한다.

- 섹션 제목을 창구별 최신 기록으로 변경한다.
- 설명에 한국 장전 → 한국 마감 → 미국 장전 → 미국 마감 고정 순서를 명시한다.
- 카드에 데이터 속성 data-freshness="latest|older|missing"을 부여한다.
- 카드의 날짜 줄을 다음 중 하나로 렌더한다.
  - 최신 기준일과 같은 카드: 가장 최근 기준일 · YYYY-MM-DD
  - 그보다 이전 카드: 이전 기준일 · YYYY-MM-DD
  - 기록 없음: 기록 없음
- 상태 텍스트는 기존 배지를 유지한다. 색상이나 테두리만으로 최신성을 전달하지 않는다.

latest_slots()의 4개 고정 순서와 레코드 선택 알고리즘은 변경하지 않는다. 최신성 표시는 그 결과를 설명하는 계층이다.

## 5. 데이터·렌더링 계약

새로운 입력 JSON 필드는 만들지 않는다. build.py가 다음 값을 계산한다.

- latest_slots(records): 기존 함수 결과 재사용
- latest_date: 슬롯에 존재하는 레코드 중 가장 큰 _record_date()
- latest_record: latest_date와 recency_rank()가 가장 최신인 레코드
- filled_slots: 비어 있지 않은 슬롯 수
- legacy_slots: _is_legacy()인 슬롯 수
- partial_slots: status == "partial"인 슬롯 수

동일 날짜에 여러 레코드가 있으면 latest_record는 기존 recency_rank()로 결정한다. 날짜 비교가 불가능한 잘못된 레코드는 verifier/build 경계 밖에서 새로 추론하지 않으며, 빈/유효하지 않은 입력은 기존 skip-not-crash 동작을 따른다.

생성물은 기존과 같다.

- index.html: 현재 읽기 패널과 상태 라벨이 포함된 정적 홈
- assets/brief.css: 패널·상태 요약의 반응형 스타일
- scripts/build.py: 생성 규칙의 단일 출처

상세 HTML, latest.json, RSS, 데이터 JSON은 이 수직 슬라이스에서 변경하지 않는다.

## 6. 접근성·보안·컴플라이언스

- section과 h2에 aria-labelledby를 사용해 현재 읽기 영역의 랜드마크를 만든다.
- 제목 링크와 행동 링크는 문맥 없이도 목적을 알 수 있는 visible text와 accessible name을 갖는다.
- 날짜는 time datetime="YYYY-MM-DD"로 표현한다.
- 최신성·상태·근거는 텍스트로도 표시하고 색상에 의존하지 않는다.
- 기존 skip link, 44px 이상 interactive target, :focus-visible, aria-live archive count를 보존한다.
- 새 입력·쿠키·스토리지·외부 API·분석 전송을 추가하지 않는다.
- 기존 status, evidence_status, legacy_unverified 의미를 바꾸지 않는다.
- partial을 published로 표시하거나 미확인 데이터를 확인된 것으로 표현하지 않는다.
- 투자 권유 아님, source caveat, public payload 경계를 그대로 유지한다.

## 7. 품질 기준과 증거

구현 완료는 다음을 모두 만족해야 한다.

### 자동 검증

- 신규 build 테스트가 먼저 실패한 뒤 구현으로 통과한다.
- python3 -m unittest discover -s tests -v 전체 통과
- python3 scripts/verify_brief.py --strict 통과
- python3 scripts/build.py 실행 후 생성물 확인
- 같은 입력으로 두 번 빌드한 결과가 동일함
- python3 -m py_compile scripts/*.py 통과
- git diff --check 통과
- 신규 코드에 외부 의존성·비밀·네트워크 호출이 없음

### 브라우저 검증

로컬 정적 서버에서 1440×940 및 390×844로 다음을 확인한다.

- 현재 읽기 패널이 4슬롯보다 먼저 보인다.
- 2026-09-03 레코드가 고정 슬롯 위치와 무관하게 현재 읽기 패널에 노출된다.
- 3개 레거시 카드는 이전 기준일과 레거시 미검증을 함께 표시한다.
- 제목 링크와 가장 최근 브리프 읽기가 올바른 상세 경로로 이동한다.
- 수평 오버플로·콘솔 오류·실패 네트워크 요청이 없다.
- 키보드 Tab/Enter로 현재 읽기 링크와 필터에 접근할 수 있다.

### 출시 경계

이번 구현의 품질 판정은 로컬 QA receipt와 production readback을 각각 별도 증거로 남긴다. Noah의 2026-09-03 명시 승인으로 commit, push, PR, merge, Vercel production deploy를 진행할 수 있지만, 자동화 활성화와 카카오톡/Slack/기타 외부 공유는 이 run에서 실행하지 않는다.

## 8. 결정

이 설계는 Freshness-aware latest command center를 첫 site-level feature로 채택한다. Evidence Explorer와 알림/팔로우는 이 수직 슬라이스의 후속 후보로 기록만 하며, 현재 구현 범위에 섞지 않는다.
