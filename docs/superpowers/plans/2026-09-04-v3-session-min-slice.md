# V3 세션 최소 슬라이스 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `schema_version == 3` 레코드가 지수·USD/KRW·변동성 세 슬롯을 침묵하지 않게 하고, 유일한 실데이터 US V3에 cutoff 이하 마지막 공식 종가를 넣는다.

**Architecture:** 닫힌 PublicBriefV3 목록만 쓴다. `verify_brief.py`가 슬롯 커버리지와 `metrics[].as_of ≤ cutoff_at_utc`를 검사한다. 새 최상위 필드·렌더러 분기·네트워크 런타임 호출은 없다. 숫자는 구현 시 공개 FRED CSV에서 옮겨 JSON에 박는다.

**Tech Stack:** Python 3 표준 라이브러리, 기존 unittest, 정적 JSON → `build.py` HTML.

**Spec:** docs/superpowers/specs/2026-09-04-v3-min-slice-design.md

## Global Constraints

- 새 V3 최상위 필드 없음. `equity`/`fx`/`vol` 객체 없음.
- `cutoff_at_utc`를 바꾸지 않는다. 9/2 종가를 넣지 않는다.
- `brief_id`·`out_path` 유지. `status=corrected` 이중 레코드 없음.
- 런타임 의존성·verifier 네트워크 호출 없음. FRED는 구현자가 한 번 읽고 JSON에 복사한다.
- KR V3 JSON을 만들지 않는다. 가설 루프·자동화·카카오/Slack·위생 PR(`AGENTS.md` 등)을 섞지 않는다.
- 한국어 docstring + `@param`/`@returns` (신규 함수).
- 커밋은 테스트·verifier·JSON·build가 초록인 뒤 한 번. 푸시·PR은 finishing-a-development-branch 메뉴에서 사용자 선택 후에만.

---

### Task 1: 세션 슬롯 계약을 테스트로 잠그기

**Files:**
- Modify: `tests/test_verify.py` (`_valid_v3_record`, `TestPublicBriefV3`)

**Interfaces:**
- Consumes: `verify_record(rec) -> list[Finding]`
- Produces: KR 픽스처가 세 정규 missing label을 갖고, 아래 테스트가 새 verifier 규칙을 요구한다.

- [ ] **Step 1: 픽스처에 KR 세션 missing을 넣는다**

`_valid_v3_record()`에 아래를 추가한다. 기존 `metric-kospi`는 그대로 둔다.

```python
"missing_data": [
    {"label": "코스피", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
    {"label": "USD/KRW", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
    {"label": "VKOSPI", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
],
```

`test_v3_accepts_closed_public_support_fields`의 `missing_data`에도 위 세 라벨을 유지한 채 `"수급"`을 추가로 둔다.

- [ ] **Step 2: 네 슬롯 테스트와 as_of 가드 테스트를 추가한다**

`TestPublicBriefV3`에 추가. `_session_metric` 헬퍼:

```python
def _session_metric(metric_id: str, as_of: str = "2026-07-07T07:00:00Z") -> dict:
    return {
        "metric_id": metric_id, "label": metric_id, "value": "1", "unit": "x",
        "delta": "0", "as_of": as_of, "source_ids": ["source-market-close"],
        "evidence_status": "confirmed",
    }
```

```python
def test_v3_silent_session_slots_are_error(self):
    rec = _valid_v3_record()
    rec.pop("missing_data", None)
    errors = self._errors(rec)
    for metric_id in ("metric-session-equity", "metric-session-fx", "metric-session-vol"):
        self.assertTrue(any(metric_id in message for message in errors), metric_id)

def test_v3_session_slots_covered_by_missing_data_pass(self):
    self.assertEqual(self._errors(_valid_v3_record()), [])

def test_v3_session_slots_covered_by_three_metrics_pass(self):
    rec = _valid_v3_record()
    rec["metrics"] = [
        _session_metric("metric-session-equity"),
        _session_metric("metric-session-fx"),
        _session_metric("metric-session-vol"),
    ]
    rec.pop("missing_data", None)
    self.assertEqual(self._errors(rec), [])

def test_v3_two_metrics_and_one_missing_pass(self):
    rec = _valid_v3_record()
    rec["metrics"] = [
        rec["metrics"][0],
        _session_metric("metric-session-equity"),
        _session_metric("metric-session-fx"),
    ]
    rec["missing_data"] = [
        {"label": "VKOSPI", "reason": "테스트", "evidence_status": "not_proven"},
    ]
    self.assertEqual(self._errors(rec), [])

def test_v3_metric_as_of_after_cutoff_is_error(self):
    rec = _valid_v3_record()
    rec["metrics"][0]["as_of"] = "2026-07-07T07:30:00Z"
    self.assertTrue(any("as_of" in message and "cutoff" in message for message in self._errors(rec)))
```

- [ ] **Step 3: 테스트가 실패하는지 확인한다**

Run: `python3 -m unittest tests.TestPublicBriefV3.test_v3_silent_session_slots_are_error tests.TestPublicBriefV3.test_v3_metric_as_of_after_cutoff_is_error -v`

Expected: FAIL (아직 슬롯 가드 없음). `test_valid_v3_record_has_no_errors`는 픽스처만으로 통과해야 한다.

---

### Task 2: verifier에 슬롯 커버리지와 as_of 가드

**Files:**
- Modify: `scripts/verify_brief.py` (`_check_v3_record` 근처)

**Interfaces:**
- Consumes: `rec["market_code"]`, `rec["metrics"]`, `rec["missing_data"]`, `rec["cutoff_at_utc"]`
- Produces:
  - `V3_SESSION_MISSING_LABELS: dict[str, dict[str, str]]`
  - `_check_v3_session_slots(rec: dict) -> list[Finding]`
  - 메트릭 루프에서 parse된 `as_of` > `cutoff_at_utc` 이면 ERROR

- [ ] **Step 1: 상수와 슬롯 검사 함수를 추가한다**

상수 위치: `V3_MISSING_DATA_REQUIRED` 아래.

```python
V3_SESSION_METRIC_IDS = (
    "metric-session-equity",
    "metric-session-fx",
    "metric-session-vol",
)
V3_SESSION_MISSING_LABELS = {
    "US": {
        "metric-session-equity": "S&P 500",
        "metric-session-fx": "USD/KRW",
        "metric-session-vol": "VIX",
    },
    "KR": {
        "metric-session-equity": "코스피",
        "metric-session-fx": "USD/KRW",
        "metric-session-vol": "VKOSPI",
    },
}
```

```python
def _utc_datetime(value: str) -> datetime:
    """검증된 Z UTC 문자열을 aware datetime으로 바꾼다."""
    return datetime.fromisoformat(f"{value[:-1]}+00:00")


def _check_v3_session_slots(rec: dict) -> list[Finding]:
    """V3 세션 세 슬롯이 메트릭 또는 정규 missing label로 커버되는지 검사한다.

    @param rec PublicBriefV3 레코드
    @returns 침묵 슬롯 Finding 목록
    """
    labels = V3_SESSION_MISSING_LABELS.get(rec.get("market_code"))
    if not labels:
        return []
    metric_ids = {
        metric.get("metric_id")
        for metric in rec.get("metrics") or []
        if isinstance(metric, dict)
    }
    missing_labels = {
        item.get("label")
        for item in rec.get("missing_data") or []
        if isinstance(item, dict)
    }
    findings = []
    for metric_id, label in labels.items():
        if metric_id not in metric_ids and label not in missing_labels:
            findings.append(Finding(
                Severity.ERROR,
                f"v3 세션 슬롯 '{metric_id}' 침묵 (메트릭 또는 missing_data '{label}' 필요)",
            ))
    return findings
```

- [ ] **Step 2: 메트릭 `as_of` 가드와 슬롯 호출을 연결한다**

기존 메트릭 `as_of` 형식 검사 직후:

```python
if (_is_utc_timestamp(metric.get("as_of"))
        and _is_utc_timestamp(rec.get("cutoff_at_utc"))
        and _utc_datetime(metric["as_of"]) > _utc_datetime(rec["cutoff_at_utc"])):
    findings.append(Finding(Severity.ERROR, f"{prefix}.as_of는 cutoff_at_utc보다 늦을 수 없음"))
```

기존 cutoff vs generated 비교도 `_utc_datetime`을 쓰도록 한 줄 치환한다. `_check_v3_record` return 직전에 `findings += _check_v3_session_slots(rec)`.

- [ ] **Step 3: Task 1 테스트를 통과시킨다**

Run: `python3 -m unittest tests.test_verify.TestPublicBriefV3 -v`

Expected: PASS

---

### Task 3: US V3 JSON·계약 문서·정적 산출물

**Files:**
- Modify: `data/2026/09/03/us-preopen.json`
- Modify: `docs/ARCHITECTURE.md` (HEAD 기준. 위생 diff와 섞지 않음)
- Modify: `docs/superpowers/specs/2026-09-04-v3-min-slice-design.md` 상태 줄을 승인됨으로
- Regenerate: `python3 scripts/build.py` → `2026/09/03/us-preopen.html`, `index.html`, `latest.json`, `rss.xml`

**Interfaces:**
- Consumes: FRED 일별 종가, cutoff `2026-09-01T14:00:00Z`
- Produces: 세 세션 메트릭 + 세 FRED SourceRef. 묶음 missing 삭제. `status=published`. cutoff 불변.

실측 복사값 (2026-09-04 FRED CSV, 관측일 ≤ 2026-08-31):

| series | 관측일 | value | 전 관측 대비 |
|---|---|---|---|
| SP500 | 2026-08-31 | 7686.14 | -0.33% |
| DEXKOUS | 2026-08-28 | 1379.41 | -0.13% |
| VIXCLS | 2026-08-31 | 14.92 | +3.40% |

- [ ] **Step 1: JSON 패치**

유지: `brief_id`, `out_path`, `cutoff_at_utc`, JOLTS 소스·메트릭·claims, `public_receipt_sha256`.

추가 SourceRef 세 개 (`source-fred-sp500`, `source-fred-dexkous`, `source-fred-vixcls`). URL:

- `https://fred.stlouisfed.org/series/SP500`
- `https://fred.stlouisfed.org/series/DEXKOUS`
- `https://fred.stlouisfed.org/series/VIXCLS`

세션 메트릭은 JOLTS 뒤에 append. `as_of`는 equity/vol `2026-08-31T20:00:00Z`, fx `2026-08-28T00:00:00Z`. `note`에 관측일과 “cutoff 이하 마지막 공식 일별 값이며 2026-09-03 세션 전일 종가가 아님”을 쓴다. 묶음 `missing_data` 삭제. `status`를 `published`로. `summary`/`next_handoff`를 위 경계에 맞게 고친다.

- [ ] **Step 2: ARCHITECTURE**

`docs/ARCHITECTURE.md` §3.4 다음에 세션 슬롯 표·커버리지 OR 규칙 한 소절. §4 목록에 “V3 세션 세 슬롯 침묵 금지, 메트릭 as_of ≤ cutoff” 한 줄. 위생용 §7 문장 변경은 이 커밋에 넣지 않는다. 작업 트리에 위생 hunk가 있으면 `git checkout -- docs/ARCHITECTURE.md` 후 소절만 다시 넣는다.

- [ ] **Step 3: build 재생성**

HEAD의 `scripts/build.py`로 생성한다. 작업 트리의 VERIFY_URL 위생 변경이 있으면 커밋에 넣지 않는다.

Run:

```
python3 -m unittest discover -s tests -v
python3 scripts/verify_brief.py --strict
python3 scripts/build.py
python3 -m py_compile scripts/*.py
```

Expected: 테스트 전부 통과, verifier 66/0/0, us-preopen 상세에 S&P 500·USD/KRW·VIX가 매크로 티어로 보인다. 홈 카드는 기존대로 metrics[:3](JOLTS)만 보여 준다. 렌더러 분기를 추가하지 않는다.

---

## Spec coverage

- 세 슬롯 침묵 ERROR → Task 1+2
- missing 세 라벨 / 세 메트릭 / 혼합 통과 → Task 1+2
- as_of ≤ cutoff → Task 1+2
- US JSON cutoff 불변, 9/2 미사용, FRED 복사 → Task 3
- ARCHITECTURE 계약, build 재생 → Task 3
- 비목표(새 스키마, KR JSON, 자동화, 위생 PR) → Global Constraints
