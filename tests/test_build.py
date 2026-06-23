#!/usr/bin/env python3
"""build.py / render_market_brief.py 회귀 테스트 (표준 unittest, 의존성 0).

"Lamplight Ledger"(Nocturne) 디자인 시스템 마크업 계약을 잠근다:
  - thesis level → ``signal lvlN`` 미터 핀 · lead 리드 줄 (선택, 하위호환)
  - metrics[0] → 히어로 feature 카드 + 라이브 와이어(.wire)
  - 값이 '미확인' → 무신호(.mcard.nosignal) 처리
  - index = live/sample 카운트 + 카드별 live/sample 배지 + 필터 속성
  - 실제 data/ 숫자·민감도 핀 보존(소스 디시플린)

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
    """렌더러의 thesis level(민감도 미터 핀)·lead(리드 줄) 보강 + 하위호환."""

    def test_level_and_lead(self):
        html = render({"theses": [
            {"name": "비상장 커머스", "signal": "높음", "level": 3, "lead": "리드줄", "body": "본문"}
        ]})
        self.assertIn('class="signal lvl3"', html)            # ●●● 민감도 핀
        self.assertIn('<span class="meter"', html)            # 도트 미터
        self.assertIn('<span class="thesis-lead">리드줄</span>', html)

    def test_backward_compat_no_level(self):
        html = render({"theses": [{"name": "글로벌 증권사", "signal": "NII", "body": "b"}]})
        self.assertIn('class="signal"', html)                 # lvl 클래스 없음
        self.assertNotIn("thesis-lead", html)
        self.assertNotIn('class="meter"', html)               # 핀 없으면 미터도 없음


class TestRenderMetricBoard(unittest.TestCase):
    """숫자 보드: metrics[0]=히어로 feature + 라이브 와이어, '미확인'=무신호 카드."""

    def test_feature_and_wire(self):
        html = render({"metrics": [
            {"name": "KOSPI", "value": "8,203.84", "tone": "down", "note": "-9.99% · src"},
            {"name": "KOSDAQ", "value": "891.52", "tone": "down", "note": "-7.94% · src"},
        ]})
        self.assertIn('class="idx feature"', html)            # 첫 지표 = 히어로
        self.assertIn('class="wire down', html)               # 톤 반영 라이브 와이어
        self.assertIn("8,203.84", html)

    def test_unknown_value_is_no_signal(self):
        html = render({"metrics": [
            {"name": "KOSPI", "value": "8,203.84", "tone": "down"},
            {"name": "a", "value": "1"}, {"name": "b", "value": "2"}, {"name": "c", "value": "3"},
            {"name": "업종/섹터", "value": "미확인", "tone": "flat", "note": "n/a"},
        ]})
        self.assertIn("mcard nosignal", html)                 # 무신호 슬레이트 카드
        self.assertIn("nosig-chip", html)


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
        self.assertIn("Sample", html)                  # 샘플 카드는 'Sample' 배지로 명시
        self.assertIn('ar-badge sample', html)
        self.assertIn('data-status="sample"', html)
        self.assertIn('ar-badge live', html)           # 라이브 카드는 'Live' 배지

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
            self.assertIn('class="idx feature"', kr)            # 히어로 숫자 = KOSPI
            self.assertIn("mcard nosignal", kr)                 # 미확인 = 무신호 카드

    def test_us_close_renders_with_sample_markers(self):
        """us-close(sample) 는 라이브로 착각되지 않게 샘플 마커가 보존된다."""
        recs = B.load_records(REPO / "data")
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            B.write_brief_pages(recs, site)
            us = (site / "2026/06/23/us-close.html").read_text(encoding="utf-8")
            self.assertIn("샘플 값", us)                         # 메트릭 노트 샘플 명시
            self.assertIn("MVP sample", us)                      # 히어로 배지 샘플 명시
            # us-close 는 thesis level/lead 가 없으므로 핀/리드가 붙지 않아야 한다.
            self.assertNotIn("thesis-lead", us)
            self.assertNotIn('class="meter"', us)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
