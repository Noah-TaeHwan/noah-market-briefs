#!/usr/bin/env python3
"""브리프 JSON을 Slack용 한국어 요약으로 결정적으로 렌더링한다.

이 스크립트는 cron의 사용자용 마지막 메시지 전용이다. 검증·빌드·git·임시파일
진단은 여기서 절대 출력하지 않는다.

사용:
  python3 scripts/render_slack_brief.py data/2026/07/13/korea-close.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from verify_brief import Severity, verify_file

PUBLIC_BASE_URL = "https://noah-market-briefs.vercel.app/market-briefs"
# 새 cron은 처음부터 한국어 값을 쓰지만, v2 전환일의 현재 레코드도 같은 화면 품질을
# 갖도록 반복되는 공개 파이프라인 표현만 표시 시점에 번역한다.
_DISPLAY_REPLACEMENTS = (
    ("Naver Finance daily index tables", "네이버 금융 일별 지수표"),
    ("Naver Finance market index", "네이버 금융 시장지수"),
    ("Yonhap economy RSS", "연합뉴스 경제 RSS"),
    ("Hana Bank posted rate", "하나은행 고시 환율"),
    ("next KR close", "다음 한국장 마감"),
    ("next Korea pre-open / next Korea session", "다음 한국장 개장 전 / 정규장"),
    ("same-date", "동일 날짜"),
    ("headline", "헤드라인"),
)
_MAX_METRICS = 5
_MAX_DRIVERS = 2
_MAX_HYPOTHESES = 2


def _clean(value: object) -> str:
    """한 줄 Slack 텍스트로 정규화하고, 반복되는 UI 용어를 국문화한다."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    for before, after in _DISPLAY_REPLACEMENTS:
        text = text.replace(before, after)
    return text


def _clip(value: object, limit: int) -> str:
    text = _clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _join_metrics(metrics: object) -> str:
    if not isinstance(metrics, list):
        return "미확인"
    rows: list[str] = []
    for metric in metrics[:_MAX_METRICS]:
        if not isinstance(metric, dict):
            continue
        name = _clean(metric.get("name"))
        value = _clean(metric.get("value"))
        if name and value:
            rows.append(f"{name} {value}")
    return " · ".join(rows) or "미확인"


def _join_drivers(drivers: object) -> str:
    if not isinstance(drivers, list):
        return "미확인"
    rows: list[str] = []
    for driver in drivers[:_MAX_DRIVERS]:
        if not isinstance(driver, dict):
            continue
        label = _clean(driver.get("label"))
        text = _clip(driver.get("text"), 120)
        if label and text:
            rows.append(f"{label}: {text}")
        elif label:
            rows.append(label)
        elif text:
            rows.append(text)
    return " / ".join(rows) or "미확인"


def _review_line(review: object) -> str | None:
    if not isinstance(review, list) or not review:
        return None
    item = next((x for x in review if isinstance(x, dict)), None)
    if item is None:
        return None
    hypothesis = _clip(item.get("previous_hypothesis") or item.get("hypothesis"), 90)
    verdict = _clean(item.get("verdict"))
    lesson = _clip(item.get("lesson"), 120)
    if not hypothesis:
        return None
    detail = f"{hypothesis} — {verdict}" if verdict else hypothesis
    return f"{detail}; {lesson}" if lesson else detail


def _learning_line(value: object, review: object) -> str:
    if isinstance(value, list):
        value = next((item for item in value if _clean(item)), "")
    learning = _clip(value, 170)
    if learning:
        return learning
    if isinstance(review, list):
        for item in review:
            if isinstance(item, dict) and _clean(item.get("lesson")):
                return _clip(item["lesson"], 170)
    return "데이터 공백과 반증 조건을 다음 회차에서 다시 확인합니다."


def _next_hypotheses_line(hypotheses: object) -> str:
    if not isinstance(hypotheses, list):
        return "미확인"
    rows: list[str] = []
    for item in hypotheses[:_MAX_HYPOTHESES]:
        if not isinstance(item, dict):
            continue
        hypothesis = _clip(item.get("hypothesis"), 115)
        horizon = _clean(item.get("horizon"))
        if hypothesis:
            rows.append(f"{hypothesis} ({horizon})" if horizon else hypothesis)
    return " / ".join(rows) or "미확인"


def _html_link(out_path: object) -> str:
    rel = _clean(out_path).lstrip("/")
    if not re.fullmatch(r"\d{4}/\d{2}/\d{2}/[a-z0-9-]+\.html", rel):
        raise ValueError("invalid out_path")
    return f"<{PUBLIC_BASE_URL}/{rel}|HTML 보기> ({rel})"


def render_record(record: dict) -> str:
    """검증된 JSON 레코드를 허용된 Slack 블록만으로 렌더링한다."""
    title = _clean(record.get("title"))
    source = _clip(record.get("source"), 300)
    takeaway = _clip(record.get("takeaway"), 260)
    if not title or not source or not takeaway:
        raise ValueError("missing public brief fields")

    lines = [
        f"*{title}*",
        f"출처/기준일: {source}",
        f"- 한 줄 결론: {takeaway}",
        f"- 숫자로 보는 시장: {_join_metrics(record.get('metrics'))}",
        f"- 핵심 동인: {_join_drivers(record.get('drivers'))}",
    ]
    review = _review_line(record.get("hypothesis_review"))
    if review:
        lines.append(f"- 이전 가설 검증: {review}")
    lines.append(f"- 오늘 배운 점: {_learning_line(record.get('today_learning'), record.get('hypothesis_review'))}")
    lines.append(f"- 다음 체크 가설: {_next_hypotheses_line(record.get('next_hypotheses'))}")
    lines.append(f"- HTML: {_html_link(record.get('out_path'))}")
    return "\n".join(lines)


def render_file(path: Path) -> str:
    """파일 검증 후 사용자용 Slack 메시지를 만든다."""
    findings = verify_file(path)
    if any(f.severity == Severity.ERROR for f in findings):
        raise ValueError("brief validation failed")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("brief file unreadable") from exc
    if not isinstance(record, dict):
        raise ValueError("brief record is not an object")
    return render_record(record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a validated market-brief JSON record for Slack")
    parser.add_argument("path", type=Path, help="brief JSON path")
    args = parser.parse_args(argv)
    try:
        print(render_file(args.path))
    except ValueError:
        # 실패 원인은 내부 로그에만 남기고, Slack에는 사용자용 상태만 전달한다.
        print("발행 보류: 브리프 데이터가 출력 계약을 통과하지 못했습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
