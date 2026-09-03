# 최신성 인식형 홈 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 정적 Market Briefs 홈에서 가장 최근 기준일의 기록과 4개 창구의 상태를 먼저 이해할 수 있게 한다.

**Architecture:** 기존 JSON → verifier → build.py → 정적 HTML 파이프라인을 유지한다. build.py가 최신 슬롯 집합에서 최신 기준일·최신 레코드·상태 카운트를 계산하고, index.html에 현재 읽기 패널과 카드별 freshness 텍스트를 생성한다. 새 API·DB·스토리지·외부 호출 없이 기존 CSS/JS와 semantic HTML만 확장한다.

**Tech Stack:** Python 3 표준 라이브러리, 정적 HTML, CSS, 기존 unittest, gstack 브라우저 QA.

**Spec:** docs/superpowers/specs/2026-09-03-freshness-aware-home-design.md

## Global Constraints

- 작업 브랜치는 feat/freshness-aware-home이며 기존 tarpon·market-briefs 소스 worktree를 수정하지 않는다.
- 자동화, 카카오톡·Slack·기타 외부 공유는 실행하지 않는다. commit·push·PR·merge·production deploy는 fresh QA와 사용자의 명시 승인을 거친 release phase에서만 실행한다.
- 기존 latest_slots()의 4개 고정 순서와 레코드 선택 규칙을 변경하지 않는다.
- 새 입력 JSON 필드, 런타임 의존성, 네트워크 요청, 쿠키, 사용자 식별, analytics를 추가하지 않는다.
- partial, legacy_unverified, not_proven을 published 또는 confirmed로 승격하지 않는다.
- 새 Python 함수와 변경하는 public-like 함수에는 한국어 docstring과 @param/@returns를 작성한다.
- 기존 생성 HTML은 직접 편집하지 않고 build.py 실행으로 재생성한다.
- 커밋·푸시는 release phase에서 사용자 승인이 확인되기 전에는 실행하지 않는다.

---

### Task 1: 최신성·현재 읽기 계약을 테스트로 잠그기

**Files:**
- Modify: tests/test_build.py, TestEvidenceFirstIndex 주변
- Read: docs/superpowers/specs/2026-09-03-freshness-aware-home-design.md

**Interfaces:**
- Consumes: B.build_index_html(records), B.latest_slots(records)
- Produces: HTML 계약 테스트가 다음 구현 동작을 요구한다.
  - 최신 레코드가 고정 슬롯 세 번째에 있어도 현재 읽기 패널 제목 링크가 그 레코드를 가리킨다.
  - 현재 읽기 패널에 최신 기준일과 4개 창구 상태 카운트가 보인다.
  - 카드에 data-freshness="latest|older|missing"과 사람이 읽는 상태 라벨이 보인다.
  - 빈 입력은 현재 읽기 패널의 빈 상태를 안전하게 렌더한다.

- [ ] **Step 1: 최신 레코드를 현재 읽기 패널에서 찾는 failing test를 추가한다**

~~~python
def test_current_focus_foregrounds_latest_record_across_fixed_slots(self):
    records = [
        self._rec("KR", "preopen", "2026-07-17"),
        self._rec("KR", "close", "2026-07-16"),
        self._rec("US", "preopen", "2026-09-03", status="partial"),
        self._rec("US", "close", "2026-07-17"),
    ]
    page = B.build_index_html(records)
    focus = page[page.index('class="latest-focus"'):page.index('class="latest-section"')]
    self.assertIn("미국 preopen 2026-09-03", focus)
    self.assertIn('href="/market-briefs/2026/09/03/US-preopen.html"', focus)
    self.assertIn("부분 공개", focus)
    self.assertIn("기준일 2026-09-03", focus)
~~~

- [ ] **Step 2: coverage와 카드 상태의 failing test를 추가한다**

~~~python
def test_latest_context_and_card_freshness_are_textual(self):
    legacy_preopen = self._rec("KR", "preopen", "2026-07-17")
    legacy_preopen["schema_version"] = 2
    legacy_close = self._rec("KR", "close", "2026-07-16")
    legacy_close["schema_version"] = 2
    records = [
        legacy_preopen,
        legacy_close,
        self._rec("US", "preopen", "2026-09-03", status="partial"),
    ]
    page = B.build_index_html(records)
    self.assertIn("4개 창구 중 3개 기록", page)
    self.assertIn("1개 레거시 미검증", page)
    self.assertIn("1개 부분 공개", page)
    self.assertIn('data-freshness="latest"', page)
    self.assertIn('data-freshness="older"', page)
    self.assertIn('data-freshness="missing"', page)
    self.assertIn("가장 최근 기준일", page)
    self.assertIn("이전 기준일", page)
    self.assertIn("기록 없음", page)
~~~

- [ ] **Step 3: 빈 입력의 failing test를 추가한다**

~~~python
def test_current_focus_handles_empty_latest_slots(self):
    page = B.build_index_html([])
    focus = page[page.index('class="latest-focus"'):page.index('class="latest-section"')]
    self.assertIn("아직 읽을 검증 기록 없음", focus)
    self.assertIn("기록 없음", page)
    self.assertIn('data-freshness="missing"', page)
~~~

- [ ] **Step 4: 신규 테스트만 실행해 예상된 RED를 확인한다**

Run: "python3 -m unittest tests.test_build.TestEvidenceFirstIndex.test_current_focus_foregrounds_latest_record_across_fixed_slots tests.test_build.TestEvidenceFirstIndex.test_latest_context_and_card_freshness_are_textual tests.test_build.TestEvidenceFirstIndex.test_current_focus_handles_empty_latest_slots -v"

Expected: FAIL because build_index_html currently has no latest-focus section, coverage summary, or data-freshness attributes.

- [ ] **Step 5: 기존 테스트가 테스트 자체의 오류가 아님을 확인한다**

Run: "python3 -m unittest tests.test_build.TestEvidenceFirstIndex.test_latest_slots_are_fixed_order_and_use_latest_per_slot tests.test_build.TestEvidenceFirstIndex.test_archive_groups_and_filter_accessibility_markup -v"

Expected: PASS on the unchanged baseline tests.

---

### Task 2: build.py에 데이터 기반 현재 읽기와 freshness 마크업 구현

**Files:**
- Modify: scripts/build.py around latest_slots(), _latest_card(), build_index_html()

**Interfaces:**
- Consumes: existing latest_slots(), _record_date(), recency_rank(), _is_legacy(), _evidence_status(), status_badge()
- Produces:
  - _latest_summary(records: list[dict]) -> tuple[dict | None, str | None, int, int, int]
  - _latest_card(market: str, window: str, rec: dict | None, latest_date: str | None) -> str
  - build_index_html(records: list) -> str with latest-focus and card freshness markup.

- [ ] **Step 1: _latest_summary()를 추가한다**

~~~python
def _latest_summary(records: list[dict]) -> tuple[dict | None, str | None, int, int, int]:
    """최신 슬롯 집합의 현재 읽기용 대표 레코드와 상태 카운트를 계산한다.

    @param records 검증을 통과한 브리프 레코드 목록
    @returns (최신 레코드, 최신 기준일, 채워진 슬롯 수, 레거시 슬롯 수, 부분 공개 슬롯 수)
    """
    slots = latest_slots(records)
    filled = [rec for _, _, rec in slots if rec is not None]
    if not filled:
        return None, None, 0, 0, 0
    latest_date = max(_record_date(rec) for rec in filled)
    latest_rec = max(
        (rec for rec in filled if _record_date(rec) == latest_date),
        key=lambda rec: (recency_rank(rec), str(rec.get("out_path", ""))),
    )
    legacy = sum(1 for rec in filled if _is_legacy(rec))
    partial = sum(1 for rec in filled if rec.get("status") == "partial")
    return latest_rec, latest_date, len(filled), legacy, partial
~~~

- [ ] **Step 2: _latest_card()에 latest_date를 받아 freshness 상태를 렌더하도록 바꾼다**

기록 없음은 missing, 최신 기준일과 같은 레코드는 latest, 그 외는 older로 분류한다. article과 날짜 span 모두에 다음 attribute를 포함한다.

~~~python
freshness = "missing" if rec is None else (
    "latest" if _record_date(rec) == latest_date else "older"
)
freshness_label = {
    "latest": "가장 최근 기준일",
    "older": "이전 기준일",
    "missing": "기록 없음",
}[freshness]
~~~

기존 4슬롯의 시장·윈도·metric·status badge·링크는 유지하고, 카드에는 data-freshness="{freshness}", 날짜 줄에는 {freshness_label} · {date}를 넣는다. 빈 카드도 data-freshness="missing"을 포함한다.

- [ ] **Step 3: build_index_html()에 현재 읽기 패널을 추가한다**

~~~python
latest_rec, latest_date, filled, legacy, partial = _latest_summary(records)
latest = "".join(
    _latest_card(market, window, rec, latest_date)
    for market, window, rec in latest_slots(records)
)
~~~

최신 레코드가 있으면 latest-focus section을 생성한다. section은 aria-labelledby="latest-focus-title"를 사용하고, 실제 제목 링크·날짜·기존 status_badge()·가장 최근 브리프 읽기 → 링크를 포함한다. 상태 요약은 0인 항목을 생략한다.

표시 예시는 다음 계약을 따른다.

~~~html
<section class="latest-focus" aria-labelledby="latest-focus-title">
  <div class="focus-kicker">가장 최근 기록</div>
  <h2 id="latest-focus-title"><a href="...">...</a></h2>
  <div class="focus-meta"><time datetime="...">기준일 ...</time> ...status badge... </div>
  <p class="coverage-summary">기준일 ... · 4개 창구 중 ... · ...</p>
  <a class="focus-action" href="...">가장 최근 브리프 읽기 →</a>
</section>
~~~

레코드가 없으면 같은 section id 아래 아직 읽을 검증 기록 없음을 렌더하고, 기존 4개 빈 카드도 유지한다.

- [ ] **Step 4: 기존 날짜 JavaScript를 freshness attribute 기반으로 단순화한다**

현재 시스템 날짜와 비교하는 new Date() 로직을 제거한다. data-freshness를 읽어 가장 최근 기준일, 이전 기준일, 기록 없음 텍스트를 보강하되, HTML에 이미 같은 텍스트가 있어 JavaScript가 꺼져도 의미가 남아 있어야 한다. 필터 동작과 aria-live archive count는 변경하지 않는다.

- [ ] **Step 5: 신규 테스트를 GREEN으로 확인한다**

Run: "python3 -m unittest tests.test_build.TestEvidenceFirstIndex.test_current_focus_foregrounds_latest_record_across_fixed_slots tests.test_build.TestEvidenceFirstIndex.test_latest_context_and_card_freshness_are_textual tests.test_build.TestEvidenceFirstIndex.test_current_focus_handles_empty_latest_slots -v"

Expected: PASS.

- [ ] **Step 6: 기존 index/detail regression을 실행한다**

Run: "python3 -m unittest tests.test_build -v"

Expected: PASS with no changed behavior outside the new home markup.

---

### Task 3: 기존 디자인 시스템 안에서 패널과 상태 계층 스타일링

**Files:**
- Modify: assets/brief.css around .latest-section/.latest-card and responsive media queries

**Interfaces:**
- Consumes: latest-focus, focus-kicker, focus-meta, coverage-summary, focus-action, data-freshness
- Produces: desktop and mobile layout without overflow, with existing colors/type scale/focus-visible rules.

- [ ] **Step 1: 현재 surface variables와 existing card rules를 재사용한다**

새 색상·폰트·의존성을 추가하지 않고 var(--surface-2), var(--line), var(--brass-bright), var(--ink), var(--muted)를 사용한다.

- [ ] **Step 2: latest-focus 스타일을 추가한다**

패널은 홈의 첫 번째 읽기 대상이 되며 2열 카드보다 넓은 단일 surface를 사용한다. 제목은 기존 display font scale을 유지하고, 상태 요약은 12–14px readable text로 표시한다. focus-action과 모든 링크는 기존 44px interactive target 규칙을 지킨다.

- [ ] **Step 3: 카드 freshness 상태를 텍스트·보조 border로 표현한다**

[data-freshness="latest"]와 [data-freshness="older"]는 색상만 바꾸지 않고 visible label과 기존 배지를 유지한다. missing card는 기존 empty 스타일과 동일한 정보 구조를 갖는다.

- [ ] **Step 4: mobile breakpoint를 보강한다**

390px 및 320px에서 panel, cards, status badges, action link가 한 열로 흐르고 viewport 밖으로 나가지 않게 한다. 기존 @media (max-width:390px) 규칙을 재사용한다.

- [ ] **Step 5: CSS-focused tests and static inspection**

Run: "python3 -m unittest tests.test_build -v" and then "rg -n 'latest-focus|data-freshness|focus-action' assets/brief.css scripts/build.py".

Expected: PASS and exactly the intended new selectors.

---

### Task 4: 문서 정합성 및 생성물 갱신

**Files:**
- Modify: docs/ARCHITECTURE.md section 5, public UI and feeds
- Regenerate: index.html via scripts/build.py
- Do not modify: data/*.json, detailed brief HTML, latest.json, rss.xml

**Interfaces:**
- Consumes: build.py output and design contract
- Produces: generated index.html that matches build_index_html() and documents the home contract.

- [ ] **Step 1: architecture contract를 현재 홈 동작에 맞게 최소 보강한다**

docs/ARCHITECTURE.md의 공개 UI 항목에 index.html이 최신 기준일의 현재 읽기 패널을 먼저 보여 주고, 그 뒤 고정 4슬롯을 상태 라벨과 함께 보여 준다는 한 문장을 추가한다. 자동화·공개 승인 경계 문장은 그대로 보존한다.

- [ ] **Step 2: build.py로 생성물을 갱신한다**

Run: "python3 scripts/build.py"

Expected: generated index.html updates; detailed pages and machine feeds remain unchanged.

- [ ] **Step 3: generated diff scope를 확인한다**

Run: "git status --short; git diff --stat; git diff --name-only"

Expected changed files are only the design/plan docs, scripts/build.py, assets/brief.css, tests/test_build.py, docs/ARCHITECTURE.md, and generated index.html.

---

### Task 5: 전체 자동·브라우저·보안 검증

**Files:**
- Read: all changed files and generated index.html
- Evidence: local test output and screenshots under /tmp/noah-market-briefs-freshness-qa

- [ ] **Step 1: deterministic build check**

Save a pre-build copy of generated artifacts, run "python3 scripts/build.py" twice in a clean copy or compare the second run diff, and verify the second run produces no additional diff.

- [ ] **Step 2: repository quality gates**

Run in this order:

~~~bash
python3 -m unittest discover -s tests -v
python3 scripts/verify_brief.py --strict
python3 -m py_compile scripts/*.py
git diff --check
~~~

Expected: all commands exit 0; no secrets, new dependencies, or forbidden mutation endpoints are introduced.

- [ ] **Step 3: local browser smoke**

Serve only the feature worktree with "python3 -m http.server 8765 --directory ." and inspect "http://127.0.0.1:8765/index.html" with the existing gstack browser at 1440×940 and 390×844. Do not navigate production for mutation and do not share the local URL.

- [ ] **Step 4: interaction and accessibility checks**

Verify the current-focus title link and action link reach the 2026/09/03 detail route, the fixed slots remain in KR-preopen → KR-close → US-preopen → US-close order, Tab reaches navigation/filter/current-focus controls, visible labels remain when JavaScript is disabled or unavailable, and no horizontal overflow, console error, or failed request occurs.

- [ ] **Step 5: evidence review**

Inspect desktop and mobile screenshots with view_image. Record PASS/NEEDS WORK/NOT_PROVEN per evidence plane: static contract, browser behavior, runtime, deployment, and production E2E. Production deployment and public sharing remain NOT_PROVEN by policy because they are intentionally not executed.

- [ ] **Step 6: release handoff boundary**

After fresh QA and the explicit release authorization, commit, push, PR, merge, and production deploy may proceed as a separate release phase. Do not activate automation or send any KakaoTalk, Slack, or other external message. Report the exact changed-file list, commands and outcomes, screenshots, remaining blockers, and the production readback boundary.
