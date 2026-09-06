#!/usr/bin/env python3
"""자동 발행 게이트 판정기 (S0 — 판정만, 발행 동작 없음).

PublicBriefV3 후보가 무인 발행 조건을 만족하는지 G1~G9 게이트로 판정한다.
게이트 하나라도 FAIL이면 인간 gate로 돌린다. 이 스크립트는 파일을 쓰지 않고,
commit·push·deploy를 수행하지 않는다. Python 표준 라이브러리만 사용한다.

게이트 (전체 PASS 시에만 AUTO-ELIGIBLE):
  G1 V3_CONTRACT  — verify_brief.py --strict 상당 (ERROR·WARNING 0)
  G2 TIME_WINDOW  — cutoff/generated/as_of/retrieved_at 삼각부등식 + 세션 신선도
  G3 EVIDENCE_FULL — published+confirmed, 3슬롯 실metric, 전 항목 confirmed 연결
  G4 ADVICE_BAN   — 투자조언 금지구문 스캔
  G5 SECRETS_PRIVACY — 페이로드 비공개 패턴 + named-holdings 가드 + tracked 시크릿 스캔
  G6 SOURCE_RIGHTS — allowlist 도메인, FRED confirmed 금지, 애그리게이터 단독 확인 금지
  G7 DIFF_SCOPE   — git dirty가 후보 JSON + 예상 생성물以内 (결정성은 CI가 담당)
  G8 IDEMPOTENCY  — brief_id/out_path/슬롯 중복 금지
  G9 CALENDAR     — --calendar open 필수 (closed/unknown이면 FAIL)

사용: python3 scripts/gate_check.py <candidate.json> --now <UTC-ISO-Z>
         --calendar open|closed|unknown [--repo <root>] [--max-lag-hours 12] [--json]
종료 코드: 0 = AUTO-ELIGIBLE, 1 = FAIL(인간 gate), 2 = 사용법 오류.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_brief import (  # noqa: E402
    NAMED_HOLDINGS_FILE,
    V3_LINKED_EVIDENCE_FIELDS,
    V3_SESSION_MISSING_LABELS,
    Severity,
    _check_v3_private_content,
    _is_utc_timestamp,
    _public_strings,
    _utc_datetime,
    verify_record,
)

GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9")

ALLOWED_SOURCE_DOMAINS = (
    "bls.gov",
    "data.krx.co.kr",
    "opendart.fss.or.kr",
    "sec.gov",
    "fred.stlouisfed.org",
    "nyse.com",
)

FRED_HOST_PART = "fred.stlouisfed.org"
AGGREGATOR_HINTS = ("openbb", "yfinance")
BLS_PUBLISHER_HINT = "bureau of labor statistics"
BLS_DISCLAIMER = "BLS.gov cannot vouch"
MAX_TEXT_LEN = 2000

ADVICE_PATTERNS = (
    r"목표가",
    r"종목\s*추천|추천\s*종목",
    r"매수\s*추천|매도\s*추천|추천\s*매수|추천\s*매도",
    r"비중\s*확대|비중\s*축소",
    r"매매\s*지시|투자\s*권유",
    r"사세요|파세요",
    r"(?<!순)매수(?!세)",
    r"(?<!순)매도(?!세)",
)
_ADVICE_RES = [re.compile(p) for p in ADVICE_PATTERNS]

SECRET_PATTERNS = (
    r"BEGIN (?:EC |RSA |OPENSSH )?PRIVATE KEY",
    r"sk-proj-[A-Za-z0-9_-]{8,}",
    r"sk-live-[A-Za-z0-9_-]{8,}",
    r"ghp_[A-Za-z0-9]{20,}",
    r"AKIA[0-9A-Z]{16}",
    r"xox[bap]-[A-Za-z0-9-]{8,}",
    r"api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}['\"]",
)
_SECRET_RES = [re.compile(p) for p in SECRET_PATTERNS]

# git grep -E는 POSIX ERE라서 (?:…)·\s가 없다. 같은 의미의 ERE 버전을 분리 유지한다.
SECRET_PATTERNS_ERE = (
    r"BEGIN (EC |RSA |OPENSSH )?PRIVATE KEY",
    r"sk-proj-[A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-]*",
    r"sk-live-[A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-][A-Za-z0-9_-]*",
    r"ghp_[A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9][A-Za-z0-9]*",
    r"AKIA[0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z][0-9A-Z]",
    r"xox[bap]-[A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-][A-Za-z0-9-]*",
    r"api[_-]?key[[:space:]]*[:=][[:space:]]*['\"][^'\"]['\"][^'\"]['\"][^'\"]['\"][^'\"]['\"][^'\"]['\"][^'\"]['\"][^'\"]['\"][^'\"]*['\"]",
)

GENERATED_TOP = {"index.html", "latest.json", "rss.xml"}
FUTURE_TOLERANCE = timedelta(minutes=15)


def _result(ok: bool, reason: str) -> tuple[bool, str]:
    """게이트 결과 튜플을 만든다."""
    return (ok, reason)


def g1_contract(rec: dict) -> tuple[bool, str]:
    """G1: verifier strict 상당 — ERROR·WARNING 0건."""
    findings = verify_record(rec)
    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    if errors or warnings:
        return _result(False, f"ERROR {len(errors)}건, WARNING {len(warnings)}건")
    return _result(True, "strict 상당 통과")


def _parse_utc(value: object) -> datetime | None:
    """Z UTC 문자열을 aware datetime으로 바꾸고, 아니면 None."""
    if not _is_utc_timestamp(value):
        return None
    return _utc_datetime(value)


def g2_time(rec: dict, now: datetime, max_lag_hours: float = 12.0) -> tuple[bool, str]:
    """G2: 시각 삼각부등식 + 세션 신선도."""
    generated = _parse_utc(rec.get("generated_at_utc"))
    cutoff = _parse_utc(rec.get("cutoff_at_utc"))
    if generated is None or cutoff is None:
        return _result(False, "generated_at/cutoff_at 파싱 실패")
    if cutoff > generated:
        return _result(False, "cutoff가 generated보다 늦음")
    if generated > now + FUTURE_TOLERANCE:
        return _result(False, "generated가 현재보다 미래")
    if generated - cutoff > timedelta(hours=max_lag_hours):
        return _result(False, f"generated-cutoff가 {max_lag_hours}시간 초과")
    for field in ("metrics", "claims"):
        for item in rec.get(field, []) if isinstance(rec.get(field), list) else []:
            if not isinstance(item, dict):
                continue
            as_of = _parse_utc(item.get("as_of"))
            if as_of is None or as_of > cutoff:
                return _result(False, f"{field} as_of가 cutoff 초과 또는 파싱 실패")
    sources = rec.get("sources") if isinstance(rec.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        as_of = _parse_utc(source.get("as_of"))
        retrieved = _parse_utc(source.get("retrieved_at"))
        if as_of is None or retrieved is None:
            return _result(False, "source 시각 파싱 실패")
        if not (as_of <= retrieved <= generated):
            return _result(False, "as_of ≤ retrieved_at ≤ generated 위반")
    return _result(True, "시각 계약 통과")


def g3_full(rec: dict) -> tuple[bool, str]:
    """G3: published+confirmed, 3슬롯 실metric, 전 항목 confirmed 연결."""
    if rec.get("status") != "published":
        return _result(False, f"status={rec.get('status')} (published만 자동 대상)")
    if rec.get("evidence_status") != "confirmed":
        return _result(False, f"evidence_status={rec.get('evidence_status')}")
    market = rec.get("market_code")
    labels = V3_SESSION_MISSING_LABELS.get(market) if isinstance(market, str) else None
    if not labels:
        return _result(False, "market_code 미상")
    metric_ids = {
        m.get("metric_id") for m in rec.get("metrics", [])
        if isinstance(m, dict)
    }
    for metric_id in labels:
        if metric_id not in metric_ids:
            return _result(False, f"슬롯 {metric_id} 실metric 없음")
    confirmed_sources = {
        s.get("source_id") for s in rec.get("sources", [])
        if isinstance(s, dict) and s.get("status") == "confirmed"
        and isinstance(s.get("source_id"), str)
    }
    for field in V3_LINKED_EVIDENCE_FIELDS:
        for item in rec.get(field, []) if isinstance(rec.get(field), list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("evidence_status") != "confirmed":
                return _result(False, f"{field}에 confirmed 아닌 항목")
            refs = item.get("source_ids")
            if (not isinstance(refs, list) or not refs
                    or any(r not in confirmed_sources for r in refs)):
                return _result(False, f"{field}의 source 연결 불량")
    return _result(True, "전체 confirmed 통과")


def g4_advice(rec: dict) -> tuple[bool, str]:
    """G4: 투자조언 금지구문 스캔."""
    for path, text in _public_strings(rec):
        for pattern in _ADVICE_RES:
            if pattern.search(text):
                return _result(False, f"{path}에서 금지구문 '{pattern.pattern}'")
    return _result(True, "조언구문 없음")


def scan_secret_text(text: str) -> str | None:
    """텍스트에서 시크릿 패턴을 찾아 패턴 문자열로 반환하고, 없으면 None."""
    for pattern in _SECRET_RES:
        if pattern.search(text):
            return pattern.pattern
    return None


def g5_privacy(rec: dict, repo: Path | None = None) -> tuple[bool, str]:
    """G5: 페이로드 비공개 패턴 + holdings 가드 + tracked 시크릿 스캔."""
    findings = _check_v3_private_content(rec)
    if findings:
        return _result(False, f"비공개 패턴 {len(findings)}건")
    for path, text in _public_strings(rec):
        hit = scan_secret_text(text)
        if hit:
            return _result(False, f"{path}에서 시크릿 패턴 '{hit}'")
    holdings = repo / "data" / ".named-holdings.local" if repo else NAMED_HOLDINGS_FILE
    if not holdings.is_file():
        return _result(False, "named-holdings 가드 OFF — 부재 시 발행 차단")
    if repo is None:
        return _result(False, "repo 미지정 — tracked 스캔 불가")
    try:
        proc = subprocess.run(
            ["git", "grep", "-n", "-E", "|".join(SECRET_PATTERNS_ERE), "--", "."],
            cwd=repo, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return _result(False, "시크릿 스캔 실행 실패")
    if proc.returncode == 0 and proc.stdout.strip():
        # 매치 내용은 시크릿 본문일 수 있어 로그에 남기지 않고 파일:행만 보고한다.
        first = proc.stdout.strip().splitlines()[0].split(":")
        location = ":".join(first[:2]) if len(first) >= 2 else first[0][:80]
        return _result(False, f"tracked 시크릿 의심 위치: {location}")
    if proc.returncode not in (0, 1):
        return _result(False, "시크릿 스캔 비정상 종료")
    return _result(True, "유출 패턴 없음")


def _host_allowed(url: object) -> bool:
    """URL 호스트가 공식 1차 도메인 allowlist에 있으면 True."""
    if not isinstance(url, str):
        return False
    host = urlparse(url).hostname or ""
    return any(host == d or host.endswith("." + d) for d in ALLOWED_SOURCE_DOMAINS)


def g6_rights(rec: dict) -> tuple[bool, str]:
    """G6: 출처 권리 기계 게이트."""
    sources = rec.get("sources") if isinstance(rec.get("sources"), list) else []
    need_bls_notice = False
    for source in sources:
        if not isinstance(source, dict):
            continue
        url = source.get("url", "")
        if not _host_allowed(url):
            return _result(False, f"allowlist 밖 도메인: {url}")
        host = urlparse(url).hostname or ""
        if FRED_HOST_PART in host and source.get("status") == "confirmed":
            return _result(False, "FRED confirmed 금지")
        haystack = f"{source.get('publisher', '')} {source.get('title', '')}".lower()
        if any(h in haystack for h in AGGREGATOR_HINTS) and source.get("status") == "confirmed":
            return _result(False, "애그리게이터 단독 confirmed 금지")
        if BLS_PUBLISHER_HINT in str(source.get("publisher", "")).lower():
            need_bls_notice = True
    if need_bls_notice:
        quality = rec.get("quality") if isinstance(rec.get("quality"), list) else []
        if not any(isinstance(q, dict) and BLS_DISCLAIMER in str(q.get("value", ""))
                   for q in quality):
            return _result(False, "BLS 고지문구 없음")
    for path, text in _public_strings(rec):
        if len(text) > MAX_TEXT_LEN:
            return _result(False, f"{path} {MAX_TEXT_LEN}자 초과(원문 복제 의심)")
    return _result(True, "권리 게이트 통과")


def g6_first_seen(rec: dict, data_dir: Path, candidate: Path) -> tuple[bool, str]:
    """G6-2: 첫등장 출처 — data/에 없던 publisher/host는 인간 gate."""
    known_publishers: set[str] = set()
    known_hosts: set[str] = set()
    try:
        files = sorted(data_dir.rglob("*.json"))
    except OSError:
        return _result(False, "data 스캔 실패")
    for path in files:
        if path.resolve() == candidate.resolve():
            continue
        try:
            other = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(other, dict):
            continue
        for source in other.get("sources", []) if isinstance(other.get("sources"), list) else []:
            if not isinstance(source, dict):
                continue
            known_publishers.add(str(source.get("publisher", "")))
            host = urlparse(str(source.get("url", ""))).hostname or ""
            known_hosts.add(host)
    sources = rec.get("sources") if isinstance(rec.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        publisher = str(source.get("publisher", ""))
        host = urlparse(str(source.get("url", ""))).hostname or ""
        if publisher not in known_publishers or host not in known_hosts:
            return _result(False, f"첫등장 출처: {publisher} / {host}")
    return _result(True, "기확인 출처만")


def expected_generated(rec: dict) -> set[str]:
    """레코드의 예상 생성물 상대 경로 집합."""
    out = {str(rec.get("out_path", ""))} if rec.get("out_path") else set()
    return (GENERATED_TOP | out) - {""}


def g7_scope(repo: Path, candidate: Path, rec: dict) -> tuple[bool, str]:
    """G7: git dirty가 후보 JSON + 예상 생성물以内."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return _result(False, "git 상태 조회 실패")
    if proc.returncode != 0:
        return _result(False, "git 상태 조회 실패")
    try:
        rel_candidate = str(candidate.resolve().relative_to(repo.resolve()))
    except ValueError:
        return _result(False, "후보가 repo 밖")
    allowed = expected_generated(rec) | {rel_candidate}
    for line in proc.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if path not in allowed:
            return _result(False, f"범위 밖 변경: {path}")
    return _result(True, "diff 범위 이내")


def g8_idempotency(rec: dict, data_dir: Path, candidate: Path) -> tuple[bool, str]:
    """G8: brief_id/out_path/슬롯 중복 금지."""
    brief_id = rec.get("brief_id")
    out_path = rec.get("out_path")
    slot = (rec.get("market_code"), rec.get("window_code"), rec.get("market_session_date"))
    try:
        files = sorted(data_dir.rglob("*.json"))
    except OSError:
        return _result(False, "data 스캔 실패")
    for path in files:
        if path.resolve() == candidate.resolve():
            continue
        try:
            other = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        if not isinstance(other, dict):
            continue
        if brief_id and other.get("brief_id") == brief_id:
            return _result(False, f"brief_id 중복: {path}")
        if out_path and other.get("out_path") == out_path:
            return _result(False, f"out_path 중복: {path}")
        other_slot = (other.get("market_code"), other.get("window_code"),
                      other.get("market_session_date", other.get("date")))
        if slot == other_slot and other.get("status") in ("published", "corrected"):
            return _result(False, f"슬롯 중복 발행: {path}")
    return _result(True, "중복 없음")


def g9_calendar(flag: str) -> tuple[bool, str]:
    """G9: 휴장 캘린더 확인 — open만 통과."""
    if flag == "open":
        return _result(True, "거래일 확인")
    return _result(False, f"calendar={flag} — 자동 대상 아님")


def evaluate(rec: dict, *, now: datetime, calendar: str, repo: Path | None,
             candidate: Path | None, max_lag_hours: float = 12.0) -> dict[str, tuple[bool, str]]:
    """G1~G9를 순서대로 평가한다. fail-fast 없음 — 전 게이트 결과를 반환."""
    results: dict[str, tuple[bool, str]] = {}
    results["G1"] = g1_contract(rec)
    results["G2"] = g2_time(rec, now, max_lag_hours)
    results["G3"] = g3_full(rec)
    results["G4"] = g4_advice(rec)
    results["G5"] = g5_privacy(rec, repo)
    rights = g6_rights(rec)
    if rights[0] and repo is not None and candidate is not None:
        rights = g6_first_seen(rec, repo / "data", candidate)
    elif rights[0]:
        rights = _result(False, "repo/candidate 미지정 — 첫등장 검사 불가")
    results["G6"] = rights
    if repo is not None and candidate is not None:
        results["G7"] = g7_scope(repo, candidate, rec)
        results["G8"] = g8_idempotency(rec, repo / "data", candidate)
    else:
        results["G7"] = _result(False, "repo/candidate 미지정")
        results["G8"] = _result(False, "repo/candidate 미지정")
    results["G9"] = g9_calendar(calendar)
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI 진입점. 0 = AUTO-ELIGIBLE, 1 = FAIL, 2 = 사용법 오류."""
    parser = argparse.ArgumentParser(description="자동 발행 게이트 판정기 (S0)")
    parser.add_argument("candidate", help="V3 후보 JSON 경로")
    parser.add_argument("--now", required=True, help="현재 시각 (Z UTC ISO-8601)")
    parser.add_argument("--calendar", required=True, choices=("open", "closed", "unknown"))
    parser.add_argument("--repo", default=None, help="저장소 루트 (기본: 스크립트 기준 추론)")
    parser.add_argument("--max-lag-hours", type=float, default=12.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    candidate = Path(args.candidate)
    try:
        rec = json.loads(candidate.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"후보 읽기 실패: {exc}")
        return 2
    if not isinstance(rec, dict):
        print("후보 최상위가 dict가 아님")
        return 2
    now = _parse_utc(args.now)
    if now is None:
        print("--now: Z 접미사 UTC ISO-8601 필요")
        return 2
    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parent.parent

    results = evaluate(rec, now=now, calendar=args.calendar, repo=repo,
                       candidate=candidate, max_lag_hours=args.max_lag_hours)
    eligible = all(ok for ok, _ in results.values())
    if args.as_json:
        print(json.dumps({k: {"pass": ok, "reason": reason}
                          for k, (ok, reason) in results.items()},
                         ensure_ascii=False, indent=2))
    else:
        for gate in GATE_IDS:
            ok, reason = results[gate]
            print(f"{gate} {'PASS' if ok else 'FAIL'} — {reason}")
        print("AUTO-ELIGIBLE" if eligible else "HUMAN-GATE")
    return 0 if eligible else 1


if __name__ == "__main__":
    sys.exit(main())
