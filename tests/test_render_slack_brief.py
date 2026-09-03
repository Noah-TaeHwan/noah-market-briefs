#!/usr/bin/env python3
"""Slack 최종 출력 계약 — 내부 진단 누출 없이 한국어 브리프만 렌더한다."""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from render_slack_brief import _html_link, main, render_record  # noqa: E402


class TestSlackBriefRenderer(unittest.TestCase):
    def _record(self):
        return {
            "schema_version": 2,
            "date": "2026-07-13",
            "market_code": "KR",
            "window_code": "close",
            "status": "live",
            "out_path": "2026/07/13/korea-close.html",
            "title": "한국 시장 마감 — 2026-07-13",
            "source": "네이버 금융 · 연합뉴스 (2026-07-13)",
            "takeaway": "지수와 원/달러가 함께 움직여 위험회피 경로를 분리해 볼 필요가 있습니다.",
            "metrics": [
                {"name": "KOSPI", "value": "2,900.00 / -1.00%", "tone": "down", "note": "네이버 금융, 2026-07-13"},
                {"name": "USD/KRW", "value": "1,400.0원", "tone": "warn", "note": "서울 외환시장, 2026-07-13"},
            ],
            "drivers": [{"label": "위험회피", "text": "현물과 선물이 동반 약세를 보였습니다."}],
            "hypothesis_review": [{
                "previous_hypothesis": "환율 안정이 지수 하락을 완화하는지 확인",
                "verdict": "미검증",
                "evidence": "공식 종가 확인 중",
                "reason": "수급 데이터가 부족",
                "lesson": "같은 시각의 환율과 현물 종가를 맞춘다.",
            }],
            "today_learning": ["상대성과와 절대수익률을 분리해서 읽습니다."],
            "next_hypotheses": [{
                "hypothesis": "외국인 수급과 환율이 함께 안정되는지 확인",
                "observable": "수급·환율·선물 basis",
                "invalidation": "환율 상승과 선물 약세 동반",
                "horizon": "다음 한국장 마감",
            }],
            "theses": [],
        }

    def test_user_facing_shape_is_korean_and_linked(self):
        output = render_record(self._record())
        for label in ("출처/기준일", "한 줄 결론", "숫자로 보는 시장", "핵심 동인", "이전 가설 검증", "오늘 배운 점", "다음 체크 가설", "HTML 보기"):
            self.assertIn(label, output)
        self.assertIn("<https://noah-market-briefs.vercel.app/market-briefs/2026/07/13/korea-close.html|HTML 보기>", output)

    def test_internal_diagnostics_are_not_in_output(self):
        output = render_record(self._record())
        for forbidden in ("unittest", "tempfile", "git ", "origin/main", "File-mutation", "검증 상태", "/var/"):
            self.assertNotIn(forbidden, output)

    def test_transition_terms_are_localized_before_delivery(self):
        record = self._record()
        record["source"] = "SOURCE: NAVER FINANCE DAILY INDEX TABLES · YONHAP ECONOMY RSS · NAVER/HANA BANK POSTED RATE; SNAPSHOT GENERATED KST (2026-07-13)"
        record["drivers"][0]["text"] = "same-date headline 확인"
        record["next_hypotheses"][0]["horizon"] = "next KR close"
        output = render_record(record)
        for translated in ("네이버 금융 일별 지수표", "연합뉴스 경제 RSS", "네이버 금융/하나은행 고시 환율", "수집 시각 KST", "동일 날짜", "헤드라인", "다음 한국장 마감"):
            self.assertIn(translated, output)
        for legacy in ("SOURCE:", "Naver Finance daily index tables", "Yonhap economy RSS", "NAVER/HANA BANK POSTED RATE", "SNAPSHOT GENERATED", "same-date", "headline", "next KR close"):
            self.assertNotIn(legacy, output)


class TestHtmlLinkGuard(unittest.TestCase):
    """out_path 가 링크로 나가기 전 형태를 강제한다 — Slack 메시지가 임의 URL을 싣지 않게."""

    def test_accepts_canonical_out_path(self):
        link = _html_link("2026/07/13/korea-close.html")
        self.assertIn("https://noah-market-briefs.vercel.app/market-briefs/2026/07/13/korea-close.html", link)

    def test_rejects_traversal_and_malformed_paths(self):
        for bad in ("../../etc/passwd",
                    "2026/7/13/korea-close.html",        # 월이 두 자리가 아님
                    "2026/07/13/korea-close.txt",        # .html 아님
                    "2026/07/13/Korea-Close.html",       # 대문자 불허
                    "https://example.com/evil.html",
                    ""):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _html_link(bad)


class TestSlackCli(unittest.TestCase):
    """CLI는 계약 위반 시 원인을 숨기고 '발행 보류'만 알리며 exit 1 을 낸다."""

    def _run(self, payload) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "brief.json"
            p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main([str(p)])
            return code, buf.getvalue()

    def test_invalid_record_holds_publication(self):
        code, out = self._run({"title": "제목만 있고 나머지가 없음"})
        self.assertEqual(code, 1)
        self.assertIn("발행 보류", out)

    def test_hold_message_does_not_leak_internal_cause(self):
        _, out = self._run({"title": "제목만 있고 나머지가 없음"})
        for forbidden in ("Traceback", "ValueError", "/var/", "tempfile"):
            self.assertNotIn(forbidden, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
