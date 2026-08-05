# 투자 브리프 재설계 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: (내부 스킬) (권장) 또는 (내부 스킬) 로 task 단위 구현. 스텝은 `- [ ]` 체크박스.

**Goal:** 일일 브리프를 보유종목 비의존 "투자 관점 읽기"(렌즈) + "어제 대비 변화"(changes[]·렌즈 delta) + 장전/마감 프레이밍으로 재구성한다 — 렌더/CSS/계약 문서까지, 새 데이터 수집 0.

**Architecture:** `render_market_brief.py`의 데이터 구동 렌더에 ⓐ `changes[]` 섹션 ⓑ 렌즈(thesis) `delta` ⓒ 섹션 제목 "투자 관점 읽기" ⓓ window_code 기반 watch 제목 자동전환을 추가한다. 기존 thesis 카드 구조를 재사용해 렌더 변경 최소. `brief.css`에 방향 칩·변화 목록 스타일 추가(기존 Lamplight Ledger 톤 토큰 재사용). cron 프롬프트 계약(투자 렌즈·changes·delta·프레이밍)은 `docs/ARCHITECTURE.md`에 정본으로 기술 — 런타임 cron(`<cron 러너 설정>`) 적용은 Noah 몫.

**Tech Stack:** Python stdlib(`unittest`), 의존성 0. 기존 `scripts/render_market_brief.py`·`scripts/build.py`·`assets/brief.css`·`tests/test_build.py`.

## Global Constraints
- 🔴 `noah-market-briefs`는 main 직접 push 금지(push-guard) → 피처브랜치 `feat/investing-brief-lenses` + PR. 작업 worktree = `<worktree>`.
- 백워드 호환 필수: `changes`/`delta`/`window_code` 없는 기존 브리프도 동일하게 렌더(새 요소만 미표시).
- JSDoc 한국어. 커밋 Conventional + 한국어. 커밋 끝 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. PR 끝 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- TDD 비협상: 각 렌더 변경은 RED→GREEN→commit. 테스트 실행 = `python3 -m unittest discover -s tests`(worktree 루트, `python3` 사용).
- cron 프롬프트(`<cron 러너 설정>`) 수정은 classifier 차단 → Noah가 적용(레포엔 계약 문서만).
- 소스 디시플린(미확인·출처·추론 금지)은 렌더/계약 모두 유지.

**스키마 v2 추가 필드(전부 선택, 백워드 호환):**
- 최상위 `changes`: `[{dir: "up"|"down"|"flat", text: str}]` — 어제 대비 변화.
- `theses[]` item: `delta: {dir: "up"|"down"|"flat", text: str}` — 렌즈별 어제 대비 한 줄. (theses 내용 = 투자 렌즈: 위험선호/금리·duration/환율·달러(원화)/변동성·헤지[+섹터].)

---

### Task 1: `changes[]` 섹션 + 방향 칩 헬퍼

**Files:**
- Modify: `scripts/render_market_brief.py` (모듈 레벨 헬퍼 추가 `_NOSIGNAL_TOKENS` 근처 ~line 21 뒤; `render()` 내부 `changes_section()` 추가 + `body_blocks` 맨 앞 삽입 ~line 240)
- Test: `tests/test_build.py` (신규 클래스)

**Interfaces:**
- Produces: 모듈 함수 `_dir_chip(d: str) -> str`(다음 task들도 사용). `render()` 출력에 `<section class="section changes"><h2>어제 대비 변화</h2>...` (changes 있을 때만).

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_build.py`에 추가:
```python
class TestChangesSection(unittest.TestCase):
    """'어제 대비 변화'(changes[]) 섹션 + 방향 칩 렌더 / 없으면 미표시."""

    def test_changes_render_with_dir_chips(self):
        html = render({"changes": [
            {"dir": "up", "text": "위험선호 회복"},
            {"dir": "down", "text": "변동성 진정"},
        ]})
        self.assertIn("어제 대비 변화", html)
        self.assertIn("change-list", html)
        self.assertIn('class="dir up"', html)
        self.assertIn('class="dir down"', html)
        self.assertIn("위험선호 회복", html)

    def test_no_changes_omits_section(self):
        html = render({"metrics": [{"name": "x", "value": "1"}]})
        self.assertNotIn("어제 대비 변화", html)
        self.assertNotIn("change-list", html)
```

- [ ] **Step 2: 실패 확인** — `cd <worktree> && python3 -m unittest tests.test_build.TestChangesSection -v`
  Expected: FAIL (`change-list`/`어제 대비 변화` 미존재).

- [ ] **Step 3: 구현** — `render_market_brief.py` 모듈 레벨(`_EM_DASH = "—"` 다음 줄)에 추가:
```python
# 어제 대비 방향 칩: up=▲ / down=▼ / flat== (색은 brief.css --good/--bad/--muted)
_DIRS = {"up": "▲", "down": "▼", "flat": "="}


def _dir_chip(d) -> str:
    """어제 대비 방향 칩 HTML. up/down/flat 외 값은 flat 으로 떨어진다.

    @param d 방향 문자열(up/down/flat)
    @returns ``<span class="dir ...">`` 칩 HTML
    """
    d = str(d or "flat").strip().lower()
    if d not in _DIRS:
        d = "flat"
    return f'<span class="dir {d}" aria-hidden="true">{_DIRS[d]}</span>'
```
그리고 `render()` 내부, `def kicker():` 정의 앞(다른 nested 섹션 함수들과 같은 위치)에 추가:
```python
    def changes_section():
        """'어제 대비 변화' 섹션 — 직전 같은 윈도 브리프 대비 시장 변화. 없으면 빈 문자열."""
        items = payload.get("changes", [])
        if not items:
            return ""
        lis = "".join(
            f'<li>{_dir_chip(c.get("dir"))}<span class="chg-text">{esc(c.get("text",""))}</span></li>'
            for c in items
        )
        return (f'<section class="section changes"><h2>어제 대비 변화</h2>'
                f'<ul class="change-list">{lis}</ul></section>')
```
그리고 `body_blocks` 리스트(현 ~line 240) 맨 앞에 `changes_section(),` 추가:
```python
    body_blocks = "\n".join(b for b in [
        changes_section(),
        market_board(),
        grid_row("split", [drivers_section(), theses_section()]),
        grid_row("even", [watch_section(), risks_section()]),
        quality_section(),
    ] if b)
```

- [ ] **Step 4: 통과 확인** — `... -m unittest tests.test_build.TestChangesSection -v` → PASS 2건. 그리고 전체 `... -m unittest discover -s tests` 회귀 없음.

- [ ] **Step 5: 커밋**
```bash
git add scripts/render_market_brief.py tests/test_build.py
git commit -m "feat(render): 어제 대비 변화(changes[]) 섹션 + 방향 칩

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 렌즈(thesis) `delta` + 섹션 제목 "투자 관점 읽기"

**Files:**
- Modify: `scripts/render_market_brief.py` (`theses_section()` ~line 172-198)
- Test: `tests/test_build.py` (신규 클래스)

**Interfaces:**
- Consumes: `_dir_chip` (Task 1).
- Produces: thesis 카드에 `<div class="thesis-delta">` (delta 있을 때), 섹션 h2 = "투자 관점 읽기".

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_build.py`에 추가:
```python
class TestThesisDeltaAndRename(unittest.TestCase):
    """투자 렌즈(thesis) delta 한 줄 + 섹션 제목 '투자 관점 읽기' / delta 없으면 미표시."""

    def test_delta_renders(self):
        html = render({"theses": [{
            "name": "위험선호", "signal": "회복", "level": 2,
            "delta": {"dir": "up", "text": "어제 약세→오늘 반등"}, "body": "본문",
        }]})
        self.assertIn("thesis-delta", html)
        self.assertIn('class="dir up"', html)
        self.assertIn("어제 약세→오늘 반등", html)

    def test_no_delta_backward_compat(self):
        html = render({"theses": [{"name": "금리·duration", "signal": "x", "body": "b"}]})
        self.assertNotIn("thesis-delta", html)      # delta 없으면 미표시
        self.assertIn('class="thesis-card"', html)  # 카드는 정상 렌더

    def test_section_renamed_to_investing_read(self):
        html = render({"theses": [{"name": "위험선호", "signal": "x", "body": "b"}]})
        self.assertIn("투자 관점 읽기", html)
        self.assertNotIn("Noah 보유논지 민감도", html)
```

- [ ] **Step 2: 실패 확인** — `... -m unittest tests.test_build.TestThesisDeltaAndRename -v`
  Expected: FAIL (`thesis-delta` 미존재, 제목 "Noah 보유논지 민감도"라 rename 단언 실패).

- [ ] **Step 3: 구현** — `render_market_brief.py`의 `theses_section()` 본문을 아래로 교체(델타 추가 + h2 변경):
```python
    def theses_section():
        """투자 관점 읽기(렌즈) 섹션. signal 태그 + 선택적 level 미터(●●●) +
        선택적 delta(어제 대비 한 줄) + 선택적 lead. 모두 없으면 깔끔 degrade."""
        items = payload.get("theses", [])
        if not items:
            return ""
        out = []
        for t in items:
            lvl = t.get("level")
            has_lvl = lvl in (1, 2, 3)
            sig_cls = "signal lvl%d" % lvl if has_lvl else "signal"
            meter = '<span class="meter" aria-hidden="true"><i></i><i></i><i></i></span>' if has_lvl else ""
            card_cls = {3: "thesis-card s-high", 2: "thesis-card s-mid"}.get(lvl, "thesis-card")
            delta = t.get("delta")
            delta_html = ""
            if isinstance(delta, dict) and (delta.get("text") or delta.get("dir")):
                delta_html = (f'<div class="thesis-delta">{_dir_chip(delta.get("dir"))}'
                              f'<span>{esc(delta.get("text",""))}</span></div>')
            lead = t.get("lead", "")
            lead_html = f'<span class="thesis-lead">{esc(lead)}</span>' if lead else ""
            sig_inner = f'{esc(t.get("signal",""))} {meter}' if meter else esc(t.get("signal", ""))
            out.append(
                f'<article class="{card_cls}"><div class="thesis-head">'
                f'<span class="thesis-name">{esc(t.get("name",""))}</span>'
                f'<span class="{sig_cls}">{sig_inner}</span></div>'
                f'<div class="thesis-body">{delta_html}{lead_html}{esc(t.get("body",""))}</div></article>'
            )
        return (f'<section class="section"><h2>투자 관점 읽기</h2>'
                f'<div class="thesis-stack">{"".join(out)}</div></section>')
```

- [ ] **Step 4: 통과 확인** — `... -m unittest tests.test_build.TestThesisDeltaAndRename -v` → PASS 3건. 전체 회귀 확인(기존 TestRenderTheses 의 level/lead/meter 단언 유지되는지).

- [ ] **Step 5: 커밋**
```bash
git add scripts/render_market_brief.py tests/test_build.py
git commit -m "feat(render): 투자 렌즈 delta(어제 대비) + 섹션명 '투자 관점 읽기'

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: watch 제목 window 자동전환 (장전=오늘 / 마감=내일)

**Files:**
- Modify: `scripts/render_market_brief.py` (`watch_section()` ~line 200-206)
- Test: `tests/test_build.py` (신규 클래스)

**Interfaces:**
- Consumes: `payload["window_code"]` ("preopen"|"close").
- Produces: watch h2 = preopen→"오늘 볼 센서", 그 외→"내일 볼 센서".

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_build.py`에 추가:
```python
class TestWatchHeadingWindowAware(unittest.TestCase):
    """장전(preopen)=오늘 볼 센서 / 마감·기본=내일 볼 센서."""

    def test_preopen_today(self):
        html = render({"window_code": "preopen", "watch": ["x"]})
        self.assertIn("오늘 볼 센서", html)
        self.assertNotIn("내일 볼 센서", html)

    def test_close_tomorrow(self):
        html = render({"window_code": "close", "watch": ["x"]})
        self.assertIn("내일 볼 센서", html)

    def test_default_tomorrow(self):
        html = render({"watch": ["x"]})       # window_code 없으면 기본 '내일'
        self.assertIn("내일 볼 센서", html)
```

- [ ] **Step 2: 실패 확인** — `... -m unittest tests.test_build.TestWatchHeadingWindowAware -v`
  Expected: FAIL (현재 항상 "내일 볼 센서"라 `test_preopen_today` 실패).

- [ ] **Step 3: 구현** — `watch_section()` 을 아래로 교체:
```python
    def watch_section():
        """볼 센서 섹션. 장전이면 '오늘', 마감이면 '내일'. 없으면 빈 문자열."""
        items = payload.get("watch", [])
        if not items:
            return ""
        heading = "오늘 볼 센서" if payload.get("window_code") == "preopen" else "내일 볼 센서"
        lis = "".join(f'<li>{esc(w)}</li>' for w in items)
        return f'<section class="section"><h2>{esc(heading)}</h2><ul class="watch-list">{lis}</ul></section>'
```

- [ ] **Step 4: 통과 확인** — `... -m unittest tests.test_build.TestWatchHeadingWindowAware -v` → PASS 3건.

- [ ] **Step 5: 커밋**
```bash
git add scripts/render_market_brief.py tests/test_build.py
git commit -m "feat(render): watch 제목을 window별 자동전환(장전=오늘/마감=내일)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: CSS — 방향 칩 · 변화 목록 · 렌즈 delta 스타일

**Files:**
- Modify: `assets/brief.css` (`.idelta.warn{...}` ~line 361 뒤, thesis 스타일 인근에 추가)
- Test: `tests/test_build.py` (CSS 존재 가드)

**Interfaces:**
- Consumes: 기존 토큰 `--good`/`--bad`/`--muted`/`--ink-soft`/`--line-soft` (brief.css `:root`).

- [ ] **Step 1: 실패 테스트 작성(스타일 존재 가드)** — `tests/test_build.py`에 추가:
```python
class TestCssHasNewStyles(unittest.TestCase):
    """새 마크업(.change-list/.dir/.thesis-delta)에 대응하는 CSS가 존재하는지(누락 회귀 방지)."""

    def test_css_defines_change_and_delta(self):
        css = (REPO / "assets" / "brief.css").read_text(encoding="utf-8")
        for sel in (".change-list", ".dir.up", ".dir.down", ".thesis-delta"):
            self.assertIn(sel, css)
```

- [ ] **Step 2: 실패 확인** — `... -m unittest tests.test_build.TestCssHasNewStyles -v`
  Expected: FAIL (셀렉터 미존재).

- [ ] **Step 3: 구현** — `assets/brief.css`의 `.idelta.warn{color:var(--warn)}` 줄(~361) 다음에 추가:
```css

/* ── 어제 대비 변화: 방향 칩 + 변화 목록 ── */
.dir{font-weight:700;font-size:12px;margin-right:8px;line-height:1;font-feature-settings:"tnum"}
.dir.up{color:var(--good)}
.dir.down{color:var(--bad)}
.dir.flat{color:var(--muted)}
.change-list{list-style:none;margin:0;padding:0}
.change-list li{display:flex;align-items:baseline;padding:9px 0;border-top:1px solid var(--line-soft);color:var(--ink-soft);font-size:15.5px;line-height:1.62}
.change-list li:first-child{border-top:none;padding-top:2px}
.chg-text{flex:1}
/* 투자 렌즈 카드의 어제 대비 한 줄 */
.thesis-delta{display:flex;align-items:baseline;gap:6px;margin-bottom:8px;font-size:13.5px;color:var(--muted)}
.thesis-delta>span{color:var(--ink-soft)}
```

- [ ] **Step 4: 통과 + 시각 스모크** — `... -m unittest tests.test_build.TestCssHasNewStyles -v` → PASS. 시각 검증(렌즈+changes 샘플 렌더 → playwright file:// 스크린샷):
```bash
python3 -c "
import sys; sys.path.insert(0,'scripts')
from render_market_brief import render
html = render({'title':'미국 시장 마감 — 2026-06-23','market':'United States','window':'U.S. Close','window_code':'close','takeaway':'테스트','changes':[{'dir':'up','text':'위험선호 회복'},{'dir':'down','text':'변동성 진정'}],'theses':[{'name':'위험선호','signal':'회복','level':2,'delta':{'dir':'up','text':'어제 약세→오늘 반등'},'body':'본문'}],'watch':['x'],'metrics':[{'name':'S&P 500','value':'7,365','tone':'down'}]}, css_rel='assets/brief.css', index_rel='index.html')
open('<worktree>/lens_preview.html','w',encoding='utf-8').write(html)
print('wrote preview')
"
```
그 후 playwright `browser_run_code_unsafe`로 `file://<worktree>/lens_preview.html` 풀페이지 캡처 → "어제 대비 변화" 섹션·방향 칩(▲▼ 색)·렌즈 delta 줄이 Lamplight Ledger 톤으로 보이는지 확인.

- [ ] **Step 5: 커밋**
```bash
git add assets/brief.css tests/test_build.py
git commit -m "feat(design): 방향 칩·어제 대비 변화 목록·렌즈 delta 스타일(Lamplight 톤 재사용)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: docs/ARCHITECTURE.md — 템플릿 v2 계약 + cron 프롬프트 애드덤

**Files:**
- Modify: `docs/ARCHITECTURE.md` (Part B 계약 섹션 끝에 "Part B v2" 추가)

**Interfaces:** 문서만. 런타임 cron 적용은 Noah(아래 애드덤을 4개 프롬프트에 추가).

- [ ] **Step 1: ARCHITECTURE.md 끝에 섹션 추가** — 아래 블록을 그대로 append:
```markdown

## Part B v2 — 투자 렌즈 + 어제 대비 변화 (template v2)

브리프를 보유종목 비의존 "투자 관점 읽기" + "어제 대비 변화"로 재구성. **render는 신·구 스키마 모두 렌더(백워드 호환)**.

### 스키마 추가(전부 선택)
- 최상위 `changes`: `[{ "dir": "up"|"down"|"flat", "text": "..." }]` — 직전 같은 (market,window) 브리프 대비 시장 변화 2~3개.
- `theses[]` item에 `delta`: `{ "dir": "up"|"down"|"flat", "text": "어제 대비 한 줄" }`.
- `theses[]` 내용 = **투자 렌즈**(보유종목 아님): `위험선호` / `금리·duration` / `환율·달러(원화)` / `변동성·헤지` (+필요시 `섹터·브레드스`). 각 = `{name(렌즈), signal(오늘 읽기), level 1-3, delta, body}`.

### 렌더 동작
- `changes[]` → 히어로 다음 "어제 대비 변화" 섹션(방향 칩 ▲▼=).
- `theses` → "투자 관점 읽기" 섹션, 각 카드에 delta 한 줄.
- watch 제목은 `window_code`로 자동: `preopen`→"오늘 볼 센서", 그 외→"내일 볼 센서".

### cron 프롬프트 애드덤(4개 잡에 추가 — Noah가 `<cron 러너 설정>` 적용)
> 투자 렌즈 + 어제 대비 변화 (template v2):
> - `theses[]` 를 **투자 관점 렌즈**로 채운다(보유종목 아님): 위험선호 / 금리·duration / 환율·달러(원화) / 변동성·헤지 (+필요시 섹터·브레드스). 각 렌즈 = `{name, signal(오늘 읽기), level 1-3, delta:{dir:up|down|flat, text:"어제 대비 한 줄"}, body}`. 데이터 근거 없으면 `미확인`.
> - `changes[]` (2-3개): **직전 같은 (market,window) 브리프**(data/ 에서 가장 최근 같은 윈도 JSON)를 읽어 시장이 뭐가 바뀌었나. 각 = `{dir, text}`. 직전 브리프 없으면 changes 생략.
> - 윈도 프레이밍: **장전 = 오늘 닥칠 환경(예측)**, **마감 = 오늘 받은 결과(회고)**. (watch 제목은 렌더가 자동 전환.)
> - 소스 디시플린(미확인·출처·날짜·추론 금지) 그대로.
```

- [ ] **Step 2: 검증** — `grep -c "Part B v2" docs/ARCHITECTURE.md` → 1. `python3 -c "import pathlib; assert '투자 관점 렌즈' in pathlib.Path('docs/ARCHITECTURE.md').read_text()"`.

- [ ] **Step 3: 커밋**
```bash
git add docs/ARCHITECTURE.md
git commit -m "docs(architecture): Part B v2 계약 — 투자 렌즈 + 어제 대비 변화 + cron 애드덤

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 통합 — 재빌드 + 전체 검증 + 회귀 HTML 커밋 + PR

**Files:**
- Modify: `index.html`, `2026/**/*.html`(기존 3 브리프 재생성: 제목 "투자 관점 읽기"·preopen watch "오늘 볼 센서")

- [ ] **Step 1: 재빌드** — `cd <worktree> && python3 scripts/build.py`
  Expected: `built N brief page(s): ...`. 기존 브리프 HTML이 새 제목으로 재생성됨(theses 내용은 과거 보유종목 그대로 — 역사 브리프라 허용).
- [ ] **Step 2: 전체 테스트** — `... -m unittest discover -s tests` → 기존 18 + 신규(2+3+3+1=9) = **27 OK**.
- [ ] **Step 3: 변경 HTML 확인 + 커밋** — `git status --short`로 재생성된 index.html·브리프 HTML 확인:
```bash
git add index.html 2026
git commit -m "build: 템플릿 v2 반영해 아카이브 재생성(투자 관점 읽기·window watch 제목)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
- [ ] **Step 4: PR** — `git push -u origin feat/investing-brief-lenses` → `gh pr create`(base main, 본문: 스펙·Phase1 변경 요약 + "27 tests pass" + Noah 후속=cron 프롬프트 애드덤 적용). PR 끝에 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## Self-Review (writing-plans)

**Spec 커버리지:**
- 투자 렌즈(theses 재활용·섹션명) → Task 2 ✅
- 어제 대비 변화(changes[] + delta) → Task 1·2 ✅
- 장전/마감 프레이밍 → Task 3(watch 제목) + Task 5(프롬프트 프레이밍 계약) ✅
- CSS → Task 4 ✅
- 계약 문서(ARCHITECTURE.md) + cron 애드덤 → Task 5 ✅
- 백워드 호환 → Task 1/2/3 의 "없으면 미표시" 테스트로 보장 ✅
- Phase 2(build.py 히스토리 집계) → **이 계획 밖**(다음 증분, 스펙에 명시) ✅
- 새 데이터 수집 0 → 스냅샷·build.py 로직 불변(Task 6은 재생성만) ✅

**플레이스홀더 스캔:** 모든 step에 실제 코드/명령/기대값 포함. TODO/TBD 없음. ✅

**타입 일관성:** `_dir_chip(d)` Task 1 정의 → Task 2 사용(동일 시그니처). `changes` item `{dir,text}`·`delta` `{dir,text}`·`theses` 필드명 전 task 일치. 섹션명 "투자 관점 읽기"·watch "오늘/내일 볼 센서" 일관. ✅

**메모:** 기존 역사 브리프(보유종목 theses)는 새 제목 "투자 관점 읽기" 아래 그대로 표시됨(과거 자료라 허용, cron이 이후 렌즈로 채움). cron 프롬프트 애드덤 적용(`<cron 러너 설정>`)은 Noah 수동 — 적용 전엔 렌더만 v2 대비 완료 상태.
