#!/usr/bin/env python3
"""브리프 JSON 레코드의 스키마·소스 디시플린·논지 생략 계약을 검증한다.

build.py가 data/ → HTML 파이프라인을 담당하면,
이 스크립트는 data/의 JSON 자체가 브리프 품질 기준을 만족하는지 점검한다.

cron(LLM)이 매일 data/ 에 JSON을 쓰므로, 한 회차의 결함이 조용히 넘어가지 않게 한다.

사용:
  python3 scripts/verify_brief.py                     # data/ 전체 검증
  python3 scripts/verify_brief.py data/2026/07/07/korea-close.json  # 단일 파일
  python3 scripts/verify_brief.py --strict            # WARNING도 exit 1

의존성 없음(표준 라이브러리만).
"""
from __future__ import annotations
import enum
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field

REPO = Path(__file__).resolve().parent.parent

# ── 상수 ──────────────────────────────────────────────────────────────────

VALID_MARKET_CODES = {"KR", "US"}
VALID_WINDOW_CODES = {"preopen", "close"}
VALID_STATUSES = {"live", "sample"}
VALID_TONES = {"up", "down", "flat", "warn"}

# 공개 기본 브리프(v2+)는 보유종목·개별 논지 이름을 어떤 공개 필드에도 넣지 않는다.
# schema_version=1은 이 정책 도입 전의 읽기 전용 아카이브라, 과거 화면을 소급 변조하지
# 않도록 기존 렌더 호환성만 유지한다. 새 cron은 반드시 schema_version=2를 작성한다.
PUBLIC_OMISSION_SCHEMA_VERSION = 2

# 감시할 보유명 목록은 그 자체가 비공개 정보라 저장소에 두지 않는다.
# 아래 파일이 있으면 한 줄에 하나씩 읽어 쓴다(.gitignore 대상, 없으면 검사는 무해하게 비활성).
NAMED_HOLDINGS_FILE = Path(__file__).resolve().parent.parent / "data" / ".named-holdings.local"


def load_named_holdings(path: Path = NAMED_HOLDINGS_FILE) -> tuple[str, ...]:
    """감시할 보유명 목록을 로컬 파일에서 읽는다.

    목록을 코드에 상수로 박으면 숨기려는 이름이 저장소에 그대로 남는다. 그래서
    목록은 버전관리 밖 파일에만 두고, 없으면 빈 튜플을 돌려 검사를 건너뛴다.

    @param path 보유명 목록 파일 경로. 한 줄에 하나, `#` 로 시작하는 줄과 빈 줄은 무시한다.
    @returns 보유명 튜플. 파일이 없거나 읽을 수 없으면 빈 튜플.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ()
    return tuple(s.strip() for s in lines if s.strip() and not s.lstrip().startswith("#"))

# hypothesis_review / next_hypotheses 필수 하위 필드
HYPOTHESIS_REVIEW_REQUIRED = {"previous_hypothesis", "verdict", "evidence", "reason", "lesson"}
NEXT_HYPOTHESES_REQUIRED = {"hypothesis", "observable", "invalidation", "horizon"}

# index-meta 필수 필드
INDEX_META_REQUIRED = {
    "schema_version": "스키마 버전",
    "date": "날짜",
    "market_code": "시장 코드",
    "window_code": "윈도 코드",
    "status": "상태",
    "out_path": "출력 경로",
}


# ── 자료구조 ───────────────────────────────────────────────────────────────

class Severity(enum.Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class Finding:
    severity: Severity
    message: str


# ── 헬퍼 ────────────────────────────────────────────────────────────────

def _looks_numeric(value: str) -> bool:
    """값이 숫자(지수·환율·금리 등)처럼 보이는지 — 쉼표·%·원·마이너스 허용."""
    import re
    cleaned = re.sub(r'[,\.\d\-+%원]', '', str(value)).strip()
    return len(cleaned) == 0 and bool(re.search(r'\d', str(value)))


def _is_unknown(value: str) -> bool:
    v = str(value).strip()
    return v in ("미확인", "n/a", "N/A", "") or "미확" in v


# ── 검증 규칙 ───────────────────────────────────────────────────────────────

def _check_index_meta(rec: dict) -> list[Finding]:
    findings: list[Finding] = []

    # 필수 필드 존재
    for key, label in INDEX_META_REQUIRED.items():
        if key not in rec or not rec.get(key):
            findings.append(Finding(Severity.ERROR, f"index-meta '{key}'({label}) 누락"))

    # enum 검증
    mc = rec.get("market_code")
    if mc and mc not in VALID_MARKET_CODES:
        findings.append(Finding(Severity.ERROR,
                                f"market_code '{mc}' 무효 (허용: {VALID_MARKET_CODES})"))

    wc = rec.get("window_code")
    if wc and wc not in VALID_WINDOW_CODES:
        findings.append(Finding(Severity.ERROR,
                                f"window_code '{wc}' 무효 (허용: {VALID_WINDOW_CODES})"))

    st = rec.get("status")
    if st and st not in VALID_STATUSES:
        findings.append(Finding(Severity.ERROR,
                                f"status '{st}' 무효 (허용: {VALID_STATUSES})"))

    version = rec.get("schema_version")
    if version is not None and (isinstance(version, bool) or not isinstance(version, int) or version < 1):
        findings.append(Finding(Severity.ERROR,
                                f"schema_version '{version}' 무효 (1 이상의 정수 필요)"))

    # out_path → date 일관성 (경고 수준)
    op = rec.get("out_path", "")
    dt = rec.get("date", "")
    if op and dt:
        date_slash = dt.replace("-", "/")
        if date_slash not in op:
            findings.append(Finding(Severity.WARNING,
                                    f"out_path('{op}')가 date('{dt}')와 불일치"))

    return findings


def _check_metrics(rec: dict) -> list[Finding]:
    findings: list[Finding] = []
    metrics = rec.get("metrics", [])
    if not isinstance(metrics, list):
        findings.append(Finding(Severity.ERROR, "metrics가 list가 아님"))
        return findings

    for i, m in enumerate(metrics):
        prefix = f"metrics[{i}]"
        if not isinstance(m, dict):
            findings.append(Finding(Severity.ERROR, f"{prefix}: dict가 아님"))
            continue

        # value 필수
        if not m.get("value"):
            findings.append(Finding(Severity.ERROR, f"{prefix}: value 누락"))

        # tone — 없으면 WARNING, 잘못된 값이면 ERROR
        tone = m.get("tone")
        if not tone:
            findings.append(Finding(Severity.WARNING, f"{prefix} '{m.get('name','?')}': tone 누락 (기본 flat 가정)"))
        elif tone not in VALID_TONES:
            findings.append(Finding(Severity.ERROR,
                                    f"{prefix}: tone '{tone}' 무효 (허용: {VALID_TONES})"))

        # 소스 디시플린 — 숫자 metric은 note에 출처가 있어야
        value = str(m.get("value", ""))
        note = str(m.get("note", ""))
        if _looks_numeric(value) and not _is_unknown(value):
            if not note.strip():
                findings.append(Finding(Severity.WARNING,
                                        f"{prefix} '{m.get('name','?')}': 숫자 값에 출처(note) 없음 — 소스 디시플린 위반"))

    return findings


def _check_hypothesis_fields(rec: dict) -> list[Finding]:
    findings: list[Finding] = []

    hr = rec.get("hypothesis_review")
    if hr is not None:
        if not isinstance(hr, list):
            findings.append(Finding(Severity.ERROR, "hypothesis_review가 list가 아님"))
        else:
            for i, item in enumerate(hr):
                if isinstance(item, dict):
                    missing = HYPOTHESIS_REVIEW_REQUIRED - set(item.keys())
                    if missing:
                        findings.append(Finding(Severity.ERROR,
                                                f"hypothesis_review[{i}]: 필수 필드 누락 — {sorted(missing)}"))
                else:
                    findings.append(Finding(Severity.ERROR,
                                            f"hypothesis_review[{i}]: dict가 아님"))

    nh = rec.get("next_hypotheses")
    if nh is not None:
        if not isinstance(nh, list):
            findings.append(Finding(Severity.ERROR, "next_hypotheses가 list가 아님"))
        else:
            for i, item in enumerate(nh):
                if isinstance(item, dict):
                    missing = NEXT_HYPOTHESES_REQUIRED - set(item.keys())
                    if missing:
                        findings.append(Finding(Severity.ERROR,
                                                f"next_hypotheses[{i}]: 필수 필드 누락 — {sorted(missing)}"))
                else:
                    findings.append(Finding(Severity.ERROR,
                                            f"next_hypotheses[{i}]: dict가 아님"))

    return findings


def _public_strings(value: object, path: str = "$") -> list[tuple[str, str]]:
    """JSON의 공개 문자열과 경로를 순회한다(내부 메타 필드는 문자열이 아님)."""
    if isinstance(value, dict):
        rows: list[tuple[str, str]] = []
        for key, child in value.items():
            rows.extend(_public_strings(child, f"{path}.{key}"))
        return rows
    if isinstance(value, list):
        rows = []
        for index, child in enumerate(value):
            rows.extend(_public_strings(child, f"{path}[{index}]"))
        return rows
    if isinstance(value, str):
        return [(path, value)]
    return []


def _check_named_holdings(rec: dict, named_holdings: tuple[str, ...] | None = None) -> list[Finding]:
    """v2+ 공개 브리프의 어느 필드에도 named holdings가 없어야 한다.

    schema_version=1은 정책 도입 전 아카이브다. 이를 새 계약 위반으로 오판해
    전체 회귀 테스트를 막지 않되, 새 cron이 쓰는 v2 레코드부터는 risks·drivers·theses
    같은 우회 경로까지 모두 검사한다.

    @param rec 검증할 브리프 레코드
    @param named_holdings 감시할 보유명 튜플. None이면 로컬 목록 파일에서 읽는다.
    @returns 계약 위반 Finding 리스트. 목록이 비면 항상 빈 리스트.
    """
    version = rec.get("schema_version", 1)
    if not isinstance(version, int) or version < PUBLIC_OMISSION_SCHEMA_VERSION:
        return []

    holdings = load_named_holdings() if named_holdings is None else named_holdings
    if not holdings:
        return []

    findings: list[Finding] = []
    for path, text in _public_strings(rec):
        for holding in holdings:
            if holding.casefold() in text.casefold():
                findings.append(Finding(
                    Severity.ERROR,
                    f"{path}: named holding '{holding}' 감지 — 공개 브리프 논지 생략 계약 위반",
                ))
    return findings


def _check_drivers(rec: dict) -> list[Finding]:
    """drivers[] 각 항목에 label·text가 있어야 한다."""
    findings: list[Finding] = []
    drivers = rec.get("drivers")
    if drivers is None:
        return findings  # optional
    if not isinstance(drivers, list):
        findings.append(Finding(Severity.ERROR, "drivers가 list가 아님"))
        return findings
    for i, d in enumerate(drivers):
        if not isinstance(d, dict):
            findings.append(Finding(Severity.ERROR, f"drivers[{i}]: dict가 아님"))
            continue
        if not d.get("label"):
            findings.append(Finding(Severity.WARNING, f"drivers[{i}]: label 누락"))
        if not d.get("text"):
            findings.append(Finding(Severity.WARNING, f"drivers[{i}]: text 누락"))
    return findings


# ── 공개 API ────────────────────────────────────────────────────────────────

def verify_record(rec: dict, named_holdings: tuple[str, ...] | None = None) -> list[Finding]:
    """브리프 JSON 레코드 1건을 검증하고 Finding 리스트를 반환한다.

    @param rec 검증할 브리프 레코드
    @param named_holdings 보유명 생략 계약을 검사할 이름 튜플. None이면 로컬 목록 파일을 쓴다.
    @returns Finding 리스트. 비어 있으면 위반 없음.
    """
    findings: list[Finding] = []
    findings += _check_index_meta(rec)
    findings += _check_metrics(rec)
    findings += _check_hypothesis_fields(rec)
    findings += _check_named_holdings(rec, named_holdings)
    findings += _check_drivers(rec)
    return findings


def verify_file(path: Path) -> list[Finding]:
    """JSON 파일 1개를 읽어 검증한다. JSON 파싱 실패도 Finding으로 반환한다."""
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [Finding(Severity.ERROR, f"JSON 파싱 실패: {e}")]
    except OSError as e:
        return [Finding(Severity.ERROR, f"파일 읽기 실패: {e}")]

    if not isinstance(rec, dict):
        return [Finding(Severity.ERROR, f"최상위가 dict가 아님: {type(rec).__name__}")]

    findings = verify_record(rec)
    # 소스 파일명 추가 (보고용)
    for f in findings:
        f.message = f"[{path.name}] {f.message}"
    return findings


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. exit 0 = ERROR 없음, exit 1 = ERROR 또는 --strict 시 WARNING 포함."""
    args = argv if argv is not None else sys.argv[1:]
    strict = "--strict" in args
    targets = [a for a in args if a != "--strict"]

    if not targets:
        # data/ 전체
        data_dir = REPO / "data"
        if not data_dir.exists():
            print("⚠️  data/ 디렉토리를 찾을 수 없음")
            return 1
        targets_files = sorted(data_dir.rglob("*.json"))
    else:
        targets_files = [Path(t) for t in targets]

    if not targets_files:
        print("검증할 JSON 파일이 없음")
        return 0

    total_errors = 0
    total_warnings = 0
    total_ok = 0

    for jf in targets_files:
        findings = verify_file(jf)
        errors = [f for f in findings if f.severity == Severity.ERROR]
        warnings = [f for f in findings if f.severity == Severity.WARNING]

        if errors:
            total_errors += len(errors)
            for f in errors:
                print(f"  ❌ [{f.severity.value}] {f.message}")
        if warnings:
            total_warnings += len(warnings)
            for f in warnings:
                print(f"  ⚠️  [{f.severity.value}] {f.message}")
        if not errors:
            total_ok += 1

    # 요약
    print(f"\n{'='*60}")
    print(f"검증 완료: {total_ok} ok / {total_errors} ERROR / {total_warnings} WARNING "
          f"(총 {len(targets_files)} 파일)")

    if total_errors > 0:
        return 1
    if strict and total_warnings > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
