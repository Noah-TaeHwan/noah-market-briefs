# Market-Brief build.py 하드닝 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use (내부 스킬) (recommended) or (내부 스킬) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Codex 리뷰가 찾은 `scripts/build.py` 결함 2건(out_path 탈출 P2, 같은 날 윈도 정렬 P3)을 TDD로 고친다.

**Architecture:** noah-market-briefs 정적 사이트 빌더 `scripts/build.py`만 손본다. 디자인(brief.css)·데이터(data/*.json)·render 마크업은 불변. 기존 `tests/test_build.py`(stdlib unittest, 10개)에 회귀 테스트를 추가하고 두 결함을 최소 변경으로 고친다.

**Tech Stack:** Python 3 표준 라이브러리만(`json`, `pathlib`). 테스트는 stdlib `unittest`. 추가 의존성 없음.

## Global Constraints
- Python 표준 라이브러리만. 새 의존성 금지.
- 작업은 **cron-안전 git worktree**에서. 이미 생성됨: `<worktree>` (branch `fix/build-hardening`, off `main`). main 체크아웃은 cron이 매일 쓰므로 건드리지 않는다.
- main 직접 push 금지(push-guard 훅) → 피처 브랜치 + PR로 랜딩.
- 데이터(`data/*.json`)·숫자·디자인 레이어(`assets/brief.css`, render 마크업)는 변경하지 않는다.
- 전체 테스트는 worktree 루트에서 `python3 tests/test_build.py` (unittest)로 돌리고 **전부 통과**해야 한다(기존 10 + 신규).
- cron 러너/deploy/cron 런타임은 건드리지 않는다.

> 아래 Run 명령의 `<wt>` = `<worktree>`. 모든 명령은 `cd <wt> &&` 로 시작한다.

---

### Task 1: out_path 컨테인먼트 가드 (Codex P2)

**Files:**
- Modify: `scripts/build.py` — `write_brief_pages` 함수 (현재 main 기준 48–59행)
- Test: `tests/test_build.py` — `TestOutPathGuard` 추가 (파일 상단에 `import json, tempfile, unittest`, `from pathlib import Path`, `import build as B` 이미 존재)

**Interfaces:**
- Consumes: `build.render(payload) -> str`, `build.write_brief_pages(records: list, site_root: Path) -> int`
- Produces: `write_brief_pages` 는 어떤 레코드의 `out_path`가 `site_root` 밖으로 resolve되면 `ValueError`를 던진다(시그니처/반환형 불변).

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_build.py` 에 클래스 추가:
```python
class TestOutPathGuard(unittest.TestCase):
    """out_path(데이터)가 site_root 밖으로 파일을 쓰지 못하게 막는다."""

    def _rec(self, out_path):
        return {"out_path": out_path, "title": "t", "market": "KR", "window": "close",
                "metrics": [], "drivers": [], "theses": [], "watch": [], "risks": []}

    def test_rejects_absolute_out_path(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            outside = Path(d) / "outside.html"          # site_root 밖의 절대경로
            with self.assertRaises(ValueError):
                B.write_brief_pages([self._rec(str(outside))], site)
            self.assertFalse(outside.exists())

    def test_rejects_parent_escape(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"; site.mkdir()
            with self.assertRaises(ValueError):
                B.write_brief_pages([self._rec("../escaped.html")], site)
            self.assertFalse((Path(d) / "escaped.html").exists())

    def test_allows_normal_path(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            n = B.write_brief_pages([self._rec("2026/06/23/korea-close.html")], site)
            self.assertEqual(n, 1)
            self.assertTrue((site / "2026/06/23/korea-close.html").exists())
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd <wt> && python3 tests/test_build.py 2>&1 | tail -6`
Expected: FAIL — 가드가 없어 절대경로/`..` 레코드에서 `ValueError`가 안 나고 `escaped`/`outside` 파일이 써짐 → `test_rejects_*` 2건 실패(`AssertionError: ValueError not raised`).

- [ ] **Step 3: 최소 구현**

`scripts/build.py` 의 `write_brief_pages` 전체를 아래로 교체:
```python
def write_brief_pages(records: list, site_root: Path) -> int:
    """각 레코드를 render() 로 HTML 문서로 만들어 out_path 에 쓴다.

    out_path 는 데이터(cron이 생성)이므로 site_root 밖으로 탈출하지 못하게 가드한다.
    @returns 쓴 페이지 수
    """
    count = 0
    root = site_root.resolve()
    for rec in records:
        out = (site_root / rec["out_path"]).resolve()   # 예: 2026/06/23/korea-close.html
        if not out.is_relative_to(root):                # 절대경로/.. 로 site_root 밖 탈출 차단
            raise ValueError(f"out_path가 site_root를 벗어남: {rec.get('out_path')!r}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render(rec), encoding="utf-8")
        count += 1
    return count
```

- [ ] **Step 4: 테스트 통과 확인 (신규 + 전체 회귀)**

Run: `cd <wt> && python3 tests/test_build.py 2>&1 | tail -4`
Expected: `OK` — 기존 10 + 신규 3 = **13 passed**.

- [ ] **Step 5: 빌드 회귀 없음 확인**

Run: `cd <wt> && python3 scripts/build.py && git status --porcelain`
Expected: `built 2 brief page(s): 1 live · 1 sample` 출력 + 정상 out_path는 그대로 통과 → 생성 HTML 변화 없음(스테이징할 변경은 `scripts/build.py`, `tests/test_build.py` 뿐).

- [ ] **Step 6: 커밋**
```bash
cd <wt> && git add scripts/build.py tests/test_build.py && \
git commit -m "fix(build): out_path가 site_root 벗어나면 거부 (Codex P2)"
```

---

### Task 2: 같은 날 preopen/close 정렬 랭크 (Codex P3)

**Files:**
- Modify: `scripts/build.py` — 모듈 상수에 `WINDOW_RANK` 추가(29행 `WINDOW_LABEL` 아래) + `load_records` 정렬 키(44행)
- Test: `tests/test_build.py` — `TestWindowSort` 추가

**Interfaces:**
- Consumes: `build.load_records(data_dir: Path) -> list`
- Produces: 모듈 상수 `WINDOW_RANK = {"preopen": 0, "close": 1}`; 같은 날짜에서 `close`가 `preopen`보다 앞(최신)에 정렬된다.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_build.py` 에 클래스 추가:
```python
class TestWindowSort(unittest.TestCase):
    """같은 날짜에서 close(장 마감, 늦음)가 preopen(장 시작 전, 이름)보다 위(최신)로 정렬된다."""

    def test_same_date_close_before_preopen(self):
        with tempfile.TemporaryDirectory() as d:
            dd = Path(d) / "data" / "2026" / "06" / "24"
            dd.mkdir(parents=True)
            (dd / "korea-preopen.json").write_text(
                json.dumps({"date": "2026-06-24", "window_code": "preopen"}))
            (dd / "korea-close.json").write_text(
                json.dumps({"date": "2026-06-24", "window_code": "close"}))
            recs = B.load_records(Path(d) / "data")
            self.assertEqual(recs[0]["window_code"], "close")    # close가 먼저(최신)
            self.assertEqual(recs[1]["window_code"], "preopen")
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd <wt> && python3 tests/test_build.py 2>&1 | tail -6`
Expected: FAIL — 현재 `window_code` 문자열 reverse 정렬이라 `"preopen" > "close"` 로 preopen이 먼저 옴 → `recs[0]["window_code"]`가 `"preopen"` → `AssertionError`.

- [ ] **Step 3: 최소 구현**

`scripts/build.py` 상수부(29행 `WINDOW_LABEL` 정의 바로 아래)에 추가:
```python
# 같은 날 내 최신순 랭크: close(장 마감, 늦음) > preopen(장 시작 전, 이름)
WINDOW_RANK = {"preopen": 0, "close": 1}
```
`load_records` 의 정렬(44행)을 아래로 교체:
```python
    # 최신순: 날짜 내림차순. 같은 날이면 close(rank 1)가 preopen(rank 0)보다 위로.
    records.sort(
        key=lambda r: (r.get("date", ""), WINDOW_RANK.get(r.get("window_code", ""), 0)),
        reverse=True,
    )
```

- [ ] **Step 4: 테스트 통과 확인 (신규 + 전체)**

Run: `cd <wt> && python3 tests/test_build.py 2>&1 | tail -4`
Expected: `OK` — 기존 10 + Task1 3 + Task2 1 = **14 passed**.

- [ ] **Step 5: 빌드 회귀 없음 확인**

Run: `cd <wt> && python3 scripts/build.py 2>&1 | tail -1`
Expected: `built 2 brief page(s): 1 live · 1 sample` (현재 `data/`엔 06-23 close 2건뿐이라 가시적 순서 변화 없음 — 회귀 없음).

- [ ] **Step 6: 커밋**
```bash
cd <wt> && git add scripts/build.py tests/test_build.py && \
git commit -m "fix(build): 같은 날 close를 preopen 위로 정렬 (Codex P3)"
```

---

### Landing (두 Task 후, TDD 아님)
- [ ] `cd <wt> && python3 -m py_compile scripts/build.py` → OK
- [ ] `cd <wt> && git push -u origin fix/build-hardening`
- [ ] `cd <wt> && gh pr create --base main --head fix/build-hardening --title "fix(build): Codex 리뷰 2건 — out_path 가드 + 윈도 정렬" --body "<요약 + 검증(14 passed)>"`
- [ ] 워크트리 제거(머지 후): `git -C <repo> worktree remove <wt>`
- [ ] **타이밍:** 첫 Part B cron run 전에 머지하면 첫 실행 파이프라인이 더 안전(특히 P2).

---

## Self-Review (작성자 점검 완료)
- **Spec 커버리지:** Codex 발견 2건(P2 build.py:55 out_path, P3 build.py:44 sort) → Task 1 / Task 2 로 1:1 매핑. 누락 없음.
- **Placeholder 스캔:** "TBD/적절히 처리" 류 없음. 모든 코드 스텝에 완전한 코드 포함.
- **타입 일관성:** `write_brief_pages(records, site_root)->int`, `load_records(data_dir)->list`, `WINDOW_RANK` 명칭이 task 간 일치. 테스트는 기존 import(json/tempfile/unittest/Path/B) 재사용.
- **스코프:** 단일 서브시스템(build.py) — 단일 계획 적절. SKILL.md 미러(A3)·비전 확장(C)은 이 계획 범위 밖(별개).
