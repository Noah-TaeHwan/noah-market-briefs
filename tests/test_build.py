#!/usr/bin/env python3
"""build.py / render_market_brief.py 회귀 테스트 (표준 unittest, 의존성 0).

실행: python3 tests/test_build.py   (또는 python3 -m unittest discover -s tests)
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build as B                       # noqa: E402
from render_market_brief import render  # noqa: E402


class TestRenderTheses(unittest.TestCase):
    """렌더러의 thesis level(민감도 핀)·lead(리드 줄) 보강 + 하위호환."""

    def test_level_and_lead(self):
        html = render({"theses": [
            {"name": "비상장 커머스", "signal": "높음", "level": 3, "lead": "리드줄", "body": "본문"}
        ]})
        self.assertIn('class="signal lvl3"', html)            # ●●● 민감도 핀
        self.assertIn('<span class="thesis-lead">리드줄</span>', html)

    def test_backward_compat_no_level(self):
        html = render({"theses": [{"name": "글로벌 증권사", "signal": "NII", "body": "b"}]})
        self.assertIn('class="signal"', html)                 # lvl 클래스 없음
        self.assertNotIn("thesis-lead", html)


class TestIndex(unittest.TestCase):
    """정직한 아카이브 index: live/sample 카운트 + 샘플 표기 + 필터 속성."""

    def _records(self):
        return [
            {"status": "live", "market_code": "KR", "window_code": "close",
             "date": "2026-06-23", "title": "한국 마감", "out_path": "2026/06/23/korea-close.html"},
            {"status": "sample", "market_code": "US", "window_code": "close",
             "date": "2026-06-23", "title": "미국 마감 샘플", "out_path": "2026/06/23/us-close.html"},
        ]

    def test_live_sample_count(self):
        html = B.build_index_html(self._records())
        self.assertIn("1 live · 1 sample", html)

    def test_sample_is_marked_not_live(self):
        html = B.build_index_html(self._records())
        self.assertIn("Sample", html)                  # 샘플 카드는 'Sample' 명시
        self.assertIn('data-status="sample"', html)

    def test_filter_attributes_present(self):
        html = B.build_index_html(self._records())
        self.assertIn('data-market="KR"', html)
        self.assertIn('data-market="US"', html)
        self.assertIn('data-window="close"', html)


class TestLoadAndIntegration(unittest.TestCase):
    """load_records 정렬 + 실제 data/ 로 렌더 시 숫자·디자인 보존."""

    def test_load_records_latest_first(self):
        with tempfile.TemporaryDirectory() as d:
            dd = Path(d) / "data" / "x"
            dd.mkdir(parents=True)
            (dd / "old.json").write_text(json.dumps({"date": "2026-06-20", "window_code": "close"}))
            (dd / "new.json").write_text(json.dumps({"date": "2026-06-23", "window_code": "close"}))
            recs = B.load_records(Path(d) / "data")
            self.assertEqual(recs[0]["date"], "2026-06-23")    # 최신이 맨 앞

    def test_real_data_numbers_and_pins_preserved(self):
        """실제 data/ 레코드를 렌더하면 핵심 숫자·민감도 핀이 그대로 나온다(소스 디시플린)."""
        recs = B.load_records(REPO / "data")
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            B.write_brief_pages(recs, site)
            kr = (site / "2026/06/23/korea-close.html").read_text(encoding="utf-8")
            for token in ("8,203.84", "-9.99%", "1,539.1원", "국고 3년 3.770%", "4조 순매도"):
                self.assertIn(token, kr)
            self.assertIn("lvl3", kr)                           # 비상장 커머스 민감도 핀
            us = (site / "2026/06/23/us-close.html").read_text(encoding="utf-8")
            self.assertIn("샘플 값", us)                         # 샘플 명시 유지


if __name__ == "__main__":
    unittest.main(verbosity=2)
