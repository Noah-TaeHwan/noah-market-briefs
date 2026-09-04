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
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import build as B                       # noqa: E402
from render_market_brief import _source_anchor, render  # noqa: E402


class TestRenderTheses(unittest.TestCase):
    """렌더러의 thesis level(민감도 미터 핀)·lead(리드 줄) 보강 + 하위호환."""

    def test_level_and_lead(self):
        html = render({"theses": [
            {"name": "위험선호", "signal": "높음", "level": 3, "lead": "리드줄", "body": "본문"}
        ]})
        self.assertIn('class="signal lvl3"', html)            # ●●● 민감도 핀
        self.assertIn('<span class="meter"', html)            # 도트 미터
        self.assertIn('<span class="thesis-lead">리드줄</span>', html)

    def test_backward_compat_no_level(self):
        html = render({"theses": [{"name": "금리·duration", "signal": "NII", "body": "b"}]})
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

    def test_composite_values_render_as_readable_segments(self):
        """슬래시로 묶인 여러 시장 숫자는 라벨|숫자 행으로 쪼개져 렌더된다."""
        html = render({"metrics": [
            {"name": "미국 전일 종가", "value": "Dow +0.14% / S&P 500 -0.01% / Nasdaq -0.46%", "tone": "flat"},
            {"name": "미국 지수선물", "value": "S&P 500 선물 +0.32% / Nasdaq 100 선물 +0.38%", "tone": "up"},
        ]})
        self.assertIn('class="ival flat tnum has-segs"', html)
        self.assertIn('class="metric-segs"', html)
        self.assertIn('<span class="seg-label">Dow</span><span class="seg-num up tnum">+0.14%</span>', html)
        self.assertIn('<span class="seg-label">S&amp;P 500</span><span class="seg-num down tnum">-0.01%</span>', html)

    def test_source_only_index_note_renders_as_source_not_colored_delta(self):
        """출처뿐인 note는 숫자 아래 컬러 delta가 아니라 작은 출처 줄로 렌더된다."""
        html = render({"metrics": [
            {"name": "미국 지수선물", "value": "S&P 500 선물 +0.32% / Nasdaq 100 선물 +0.38%", "tone": "up", "note": "CNBC quote-cache, 2026-06-25 19:19 EDT; futures, not close"},
        ]})
        self.assertIn('<div class="isrc">CNBC quote-cache, 2026-06-25 19:19 EDT; futures, not close</div>', html)
        self.assertNotIn('class="idelta up tnum">CNBC quote-cache', html)

    def test_six_macro_cards_use_three_columns_to_avoid_empty_grid_holes(self):
        """6개 매크로 카드는 4열+빈칸 대신 3열×2행으로 렌더한다."""
        metrics = [
            {"name": "h", "value": "1"}, {"name": "i1", "value": "1"},
            {"name": "i2", "value": "1"}, {"name": "i3", "value": "1"},
        ] + [{"name": f"m{i}", "value": str(i)} for i in range(6)]
        html = render({"metrics": metrics})
        self.assertIn('class="macros mcols-3"', html)


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
        self.assertIn("공개 1개 · 샘플 1개", html)

    def test_sample_is_marked_not_live(self):
        html = B.build_index_html(self._records())
        self.assertIn("샘플", html)                    # 샘플 카드는 '샘플' 배지로 명시
        self.assertNotIn('ar-badge live">샘플', html)
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
            (dd / "old.json").write_text(json.dumps({"schema_version": 2, "date": "2026-06-20",
                "market_code": "KR", "window_code": "close", "status": "live",
                "out_path": "2026/06/20/old.html", "title": "old"}))
            (dd / "new.json").write_text(json.dumps({"schema_version": 2, "date": "2026-06-23",
                "market_code": "KR", "window_code": "close", "status": "live",
                "out_path": "2026/06/23/new.html", "title": "new"}))
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
            self.assertIn("lvl3", kr)                           # 렌즈 민감도 핀
            self.assertIn('class="idx feature"', kr)            # 히어로 숫자 = KOSPI
            self.assertIn("mcard nosignal", kr)                 # 미확인 = 무신호 카드

    def test_sample_markers_render_and_no_false_pins(self):
        """샘플 성격 레코드의 노트가 렌더에 그대로 나와 라이브로 오인되지 않고,
        level/lead 없는 thesis엔 민감도 핀/리드가 붙지 않는다.

        실제 data/ 파일을 읽지 않는 합성 픽스처 — cron이 매일 data/ 를 갱신해도
        깨지지 않는다(이전 버전은 us-close 가 'sample'이라 가정해 cron이 live로
        승격하자 깨졌다). 샘플 마커 렌더 로직만 검증한다.
        """
        html = render({
            "title": "샘플 마감", "market": "United States", "window": "U.S. Close",
            "note": "MVP sample · source pipeline not connected",
            "metrics": [
                {"name": "S&P 500", "value": "+0.4%", "tone": "up", "note": "샘플 값 · 실제 데이터 아님"},
            ],
            "theses": [{"name": "금리·duration", "signal": "NII vs activity", "body": "본문"}],  # level/lead 없음
        })
        self.assertIn("샘플 값", html)            # 메트릭 노트 그대로 렌더
        self.assertIn("MVP sample", html)          # 히어로 노트 그대로 렌더
        self.assertNotIn("thesis-lead", html)      # level/lead 없으면 리드 줄 없음
        self.assertNotIn('class="meter"', html)    # 핀 미터도 없음


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


class TestWindowSort(unittest.TestCase):
    """같은 날짜에서 close(장 마감, 늦음)가 preopen(장 시작 전, 이름)보다 위(최신)로 정렬된다."""

    def test_same_date_close_before_preopen(self):
        with tempfile.TemporaryDirectory() as d:
            dd = Path(d) / "data" / "2026" / "06" / "24"
            dd.mkdir(parents=True)
            (dd / "korea-preopen.json").write_text(
                json.dumps({"schema_version": 2, "date": "2026-06-24", "market_code": "KR",
                            "window_code": "preopen", "status": "live",
                            "out_path": "2026/06/24/korea-preopen.html", "title": "장전"}))
            (dd / "korea-close.json").write_text(
                json.dumps({"schema_version": 2, "date": "2026-06-24", "market_code": "KR",
                            "window_code": "close", "status": "live",
                            "out_path": "2026/06/24/korea-close.html", "title": "마감"}))
            recs = B.load_records(Path(d) / "data")
            self.assertEqual(recs[0]["window_code"], "close")    # close가 먼저(최신)
            self.assertEqual(recs[1]["window_code"], "preopen")


class TestGenerationTimeOrder(unittest.TestCase):
    """같은 세션 날짜 안에서 '리포트가 실제 생성되는 시각'(KST cron) 순으로 최신이 위로 정렬.

    생성 순서(이른→늦은): KR 장전(08:30) → KR 마감(16:30) → US 장전(22:00) → US 마감(익일 06:00).
    날짜만으로는 같은 날 KR/US 마감이 묶여 가장 오래된 KR 마감이 위로 오던 문제를 (시장·윈도)
    복합 랭크로 교정한다.
    """

    def _write(self, root, market, window, date="2026-06-23"):
        ymd = date.replace("-", "/")
        dd = root / "data" / ymd
        dd.mkdir(parents=True, exist_ok=True)
        (dd / f"{market}-{window}.json").write_text(json.dumps({
            "schema_version": 2, "date": date, "market_code": market, "window_code": window,
            "status": "live", "out_path": f"{ymd}/{market.lower()}-{window}.html",
            "title": f"{market} {window}"}), encoding="utf-8")

    def test_same_date_recency_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # 입력 순서를 일부러 섞어 둠 — 정렬이 입력 순서와 무관함을 보이기 위해
            self._write(root, "KR", "close")
            self._write(root, "US", "preopen")
            self._write(root, "KR", "preopen")
            self._write(root, "US", "close")
            recs = B.load_records(root / "data")
        order = [(r["market_code"], r["window_code"]) for r in recs]
        self.assertEqual(order, [
            ("US", "close"),     # 익일 06:00 — 가장 최신
            ("US", "preopen"),   # 22:00
            ("KR", "close"),     # 16:30
            ("KR", "preopen"),   # 08:30 — 가장 오래됨
        ])

    def test_next_day_preopen_above_prev_day_us_close(self):
        # D+1 KR 장전(생성 D+1 08:30)이 D US 마감(생성 D+1 06:00)보다 최신 → 위로
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self._write(root, "US", "close", date="2026-06-23")
            self._write(root, "KR", "preopen", date="2026-06-24")
            recs = B.load_records(root / "data")
        self.assertEqual(recs[0]["date"], "2026-06-24")
        self.assertEqual((recs[0]["market_code"], recs[0]["window_code"]), ("KR", "preopen"))

    def test_rank_comment_does_not_claim_obsolete_cron_times(self):
        source = (REPO / "scripts" / "build.py").read_text(encoding="utf-8")
        self.assertNotIn("KR 장전 08:30", source)
        self.assertNotIn("US 마감 익일 06:00", source)


class TestLoadRecordsRobustness(unittest.TestCase):
    """깨진 JSON·out_path 누락 레코드 1건이 빌드 전체를 죽이지 않고 skip되는지.

    cron(LLM)이 매일 data/ 에 JSON을 쓰므로, 한 회차의 malformed/불완전 레코드가
    아카이브 전체 빌드를 막으면 안 된다(fail-closed → 한 회차만 skip).
    """

    def test_malformed_json_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            dd = Path(d) / "data" / "2026" / "06" / "23"
            dd.mkdir(parents=True)
            (dd / "ok.json").write_text(json.dumps({
                "schema_version": 2, "date": "2026-06-23", "market_code": "KR", "window_code": "close",
                "status": "live", "out_path": "2026/06/23/ok.html", "title": "ok"}), encoding="utf-8")
            (dd / "bad.json").write_text('{"date": "2026-06-23",', encoding="utf-8")  # 깨짐
            recs = B.load_records(Path(d) / "data")
            self.assertEqual(len(recs), 1)                       # 깨진 건 skip, 정상만
            self.assertEqual(recs[0]["out_path"], "2026/06/23/ok.html")

    def test_write_pages_skips_missing_out_path(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            recs = [
                {"title": "no out_path", "metrics": [], "theses": []},   # out_path 없음 → skip
                {"out_path": "2026/06/23/ok.html", "title": "ok", "metrics": [],
                 "theses": [], "drivers": [], "watch": [], "risks": []},
            ]
            n = B.write_brief_pages(recs, site)                  # KeyError 없이 정상만 쓴다
            self.assertEqual(n, 1)
            self.assertTrue((site / "2026/06/23/ok.html").exists())


# ─────────────────────────────────────────────────────────────────────────────
# 템플릿 v2: 투자 렌즈 + 어제 대비 변화 (Phase 1)
# ─────────────────────────────────────────────────────────────────────────────

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
        self.assertNotIn("thesis-delta", html)       # delta 없으면 미표시
        self.assertIn('class="thesis-card"', html)   # 카드는 정상 렌더

    def test_section_renamed_to_investing_read(self):
        html = render({"theses": [{"name": "위험선호", "signal": "x", "body": "b"}]})
        self.assertIn("투자 관점 읽기", html)
        self.assertNotIn("Noah 보유논지 민감도", html)


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
        html = render({"watch": ["x"]})              # window_code 없으면 기본 '내일'
        self.assertIn("내일 볼 센서", html)


    def test_hypothesis_loop_suppresses_legacy_watch_heading(self):
        html = render({"window_code": "close", "watch": ["legacy"], "next_hypotheses": [{"hypothesis": "next"}]})
        self.assertIn("다음 체크 가설", html)
        self.assertNotIn("내일 볼 센서", html)
        self.assertNotIn("legacy", html)


class TestHypothesisLoopSections(unittest.TestCase):
    """이전 가설 검증 + 다음 체크 가설 루프 렌더링."""

    def test_hypothesis_review_and_next_hypotheses_render(self):
        html = render({
            "hypothesis_review": [{
                "previous_hypothesis": "원화 약세가 외국인 매도 압력을 키운다",
                "verdict": "부분 적중",
                "evidence": "USD/KRW 1,555.8원, 외국인 순매도 headline",
                "reason": "환율 레벨은 맞았지만 순매도 금액은 미확인",
                "lesson": "다음부터 현물/선물 순매도 금액을 같이 확인",
            }],
            "today_learning": "환율 레벨만으로 수급 강도를 말하지 말고 공식 종가·수급 금액·선물 basis를 같이 본다.",
            "next_hypotheses": [{
                "hypothesis": "KOSPI200 선물 급락이 basis 악화로 이어지는지 확인",
                "observable": "KOSPI200 선물 basis, 외국인 선물 순매도",
                "invalidation": "basis 안정·외국인 선물 순매수",
                "horizon": "next KR session",
            }],
        })
        self.assertIn("이전 가설 검증", html)
        self.assertIn("부분 적중", html)
        self.assertIn("오늘 배운 점", html)
        self.assertIn("공식 종가", html)
        self.assertIn("다음 체크 가설", html)
        self.assertIn("반증 조건", html)

    def test_invalid_hypothesis_items_omit_sections(self):
        html = render({"hypothesis_review": [{"verdict": "부분"}], "next_hypotheses": [{"foo": "bar"}]})
        self.assertNotIn("이전 가설 검증", html)
        self.assertNotIn("다음 체크 가설", html)


class TestCssHasNewStyles(unittest.TestCase):
    """새 마크업(.change-list/.dir/.thesis-delta/.hypothesis-stack)에 대응하는 CSS 존재."""

    def test_css_defines_change_delta_and_hypothesis(self):
        css = (REPO / "assets" / "brief.css").read_text(encoding="utf-8")
        for sel in (".change-list", ".dir.up", ".dir.down", ".thesis-delta", ".hypothesis-stack", ".verdict", ".learning-list"):
            self.assertIn(sel, css)

    def test_filter_focus_keeps_explicit_two_pixel_outline(self):
        css = (REPO / "assets" / "brief.css").read_text(encoding="utf-8")
        self.assertNotIn(".filterbar select:focus-visible{outline:none", css)
        self.assertIn(".filterbar select:focus-visible{outline:2px solid", css)

    def test_metadata_specificity_floor_is_twelve_pixels(self):
        css = (REPO / "assets" / "brief.css").read_text(encoding="utf-8")
        override = ".badge,.idx.feature .iname,.idx .seg-label,.idx.feature .seg-label,.mcard .seg-label{font-size:12px}"
        single_override = ".metric-seg.single .seg-label{font-size:clamp(16px,1.45vw,20px)}"
        self.assertIn(override, css)
        self.assertGreater(css.rfind(override), css.find(".idx.feature .iname{font-size:11.5px"))
        self.assertGreater(css.rfind(single_override), css.rfind(override))

    def test_latest_focus_and_freshness_styles_exist(self):
        css = (REPO / "assets" / "brief.css").read_text(encoding="utf-8")
        for selector in (".latest-focus", ".focus-kicker", ".focus-meta", ".coverage-summary", ".focus-action"):
            self.assertIn(selector, css)
        self.assertIn('[data-freshness="latest"]', css)
        self.assertIn('[data-freshness="older"]', css)


class TestTemplateV2Robustness(unittest.TestCase):
    """v2 새 필드의 잘못된 모양이 빌드를 죽이지 않고 관대/안전하게 처리되는지(adversarial)."""

    def test_changes_string_items_render_lenient(self):
        # changes 가 문자열 리스트(LLM이 '줄'로 오해)여도 크래시 없이 텍스트로 렌더
        html = render({"changes": ["어제 risk-off→오늘 반등", "VIX 진정"]})
        self.assertIn("change-list", html)
        self.assertIn("어제 risk-off→오늘 반등", html)

    def test_changes_dict_without_text_skipped(self):
        html = render({"changes": [{"dir": "up"}, {"dir": "down", "text": "유효"}]})
        self.assertIn("유효", html)
        self.assertEqual(html.count("chg-text"), 1)    # 텍스트 없는 dict는 스킵

    def test_changes_all_invalid_omits_section(self):
        html = render({"changes": [{"dir": "up"}, ""]})  # 텍스트 있는 항목 0
        self.assertNotIn("어제 대비 변화", html)

    def test_delta_string_no_crash_and_omitted(self):
        html = render({"theses": [{"name": "위험선호", "signal": "x",
                                   "delta": "잘못된 모양", "body": "b"}]})
        self.assertNotIn("thesis-delta", html)         # 문자열 delta 무시(크래시 없음)

    def test_delta_dict_without_text_omitted(self):
        html = render({"theses": [{"name": "위험선호", "signal": "x",
                                   "delta": {"dir": "up"}, "body": "b"}]})
        self.assertNotIn("thesis-delta", html)         # 외로운 화살표 방지

    def test_dir_flat_and_unknown_fall_to_flat(self):
        html = render({"changes": [{"dir": "flat", "text": "유지"},
                                   {"dir": "sideways", "text": "미지"}]})
        self.assertEqual(html.count('class="dir flat"'), 2)  # flat + 알수없음→flat

    def test_index_landing_no_holdings_copy(self):
        html = B.build_index_html([])
        self.assertNotIn("보유논지", html)              # 랜딩 카피도 리네임 반영
        self.assertNotIn("투자 관점 읽기", html)
        self.assertIn("가설 기반 시장 읽기", html)
        self.assertIn("YYYY / MM / DD / 시점", html)
        self.assertNotIn("YYYY / MM / DD / window", html)


class TestKoreanPublicLabels(unittest.TestCase):
    """고정 UI와 전환일 파이프라인 용어는 HTML에서 한국어로 보여야 한다."""

    def test_fixed_labels_and_transition_terms_are_localized(self):
        html = render({
            "market": "Korea", "window": "Close", "generated": "Generated KST 2026-07-13",
            "title": "한국 시장 마감 — 2026-07-13", "takeaway": "요약",
            "source": "Naver Finance daily index tables · Yonhap economy RSS",
            "note": "SOURCE: NAVER FINANCE DAILY INDEX TABLES · YONHAP ECONOMY RSS · NAVER/HANA BANK POSTED RATE; SNAPSHOT GENERATED KST",
            "quality": [{"label": "Source/date", "value": "same-date"}],
            "drivers": [{"label": "headline", "text": "same-date headline"}],
            "next_hypotheses": [{"hypothesis": "가설", "horizon": "next KR close"}],
        })
        for translated in ("생성 시각", "출처", "데이터 품질", "용도", "핵심 동인", "브리프 목록", "투자 권유 아님", "다음 한국장 마감", "헤드라인", "동일 날짜", "수집 시각 KST", "네이버 금융/하나은행 고시 환율"):
            self.assertIn(translated, html)
        for legacy in (">Generated<", ">Source<", "SOURCE:", "SNAPSHOT GENERATED", "Data quality", "오늘의 핵심 driver", "Archive index", "Not investment advice", "next KR close"):
            self.assertNotIn(legacy, html)


class TestBuildSummary(unittest.TestCase):
    """build() 요약 dict — cron 로그와 CI가 이 숫자로 회차 누락을 알아챈다."""

    def _write(self, data_dir: Path, name: str, status: str, date: str):
        p = data_dir / "2026" / "06" / "23"
        p.mkdir(parents=True, exist_ok=True)
        (p / f"{name}.json").write_text(json.dumps({
            "schema_version": 2, "date": date, "market_code": "KR", "window_code": "close",
            "status": status, "out_path": f"2026/06/23/{name}.html",
            "title": f"테스트 브리프 {name}", "takeaway": "요약",
        }, ensure_ascii=False), encoding="utf-8")

    def test_counts_live_sample_and_pages(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data"
            self._write(data, "korea-close", "live", "2026-06-23")
            self._write(data, "us-close", "sample", "2026-06-23")
            summary = B.build(root)
            self.assertEqual(summary, {"live": 1, "sample": 1, "pages": 2})
            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "2026/06/23/korea-close.html").exists())

    def test_empty_data_dir_builds_index_with_zero_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            summary = B.build(root)
            self.assertEqual(summary, {"live": 0, "sample": 0, "pages": 0})
            self.assertTrue((root / "index.html").exists())


class TestPublicBriefV3BuildGate(unittest.TestCase):
    """v3 검증 ERROR는 정적 공개 페이지와 index에서 모두 제외한다."""

    def _v3_record(self, title: str, out_path: str) -> dict:
        return {
            "schema_version": 3, "brief_id": f"brief-{title}", "market_code": "KR",
            "window_code": "close", "market_session_date": "2026-07-07",
            "generated_at_utc": "2026-07-07T07:30:00Z", "cutoff_at_utc": "2026-07-07T07:20:00Z",
            "market_timezone": "Asia/Seoul", "status": "published", "evidence_status": "confirmed",
            "methodology_version": "public-brief-v3", "public_receipt_sha256": "b" * 64,
            "out_path": out_path, "title": title,
            "sources": [{"source_id": "source-public", "publisher": "Synthetic Public Source",
                         "title": "Market close", "url": "https://example.test/close",
                         "as_of": "2026-07-07T07:00:00Z", "retrieved_at": "2026-07-07T07:20:00Z",
                         "source_type": "market_data", "status": "confirmed"}],
            "metrics": [{"name": "KOSPI", "value": "7,656.31", "tone": "down",
                         "metric_id": "metric-kospi", "label": "KOSPI", "unit": "points",
                         "delta": "-4.91%", "as_of": "2026-07-07T07:00:00Z",
                         "source_ids": ["source-public"], "evidence_status": "confirmed"}],
            "missing_data": [
                {"label": "코스피", "reason": "빌드 픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
                {"label": "USD/KRW", "reason": "빌드 픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
                {"label": "VKOSPI", "reason": "빌드 픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
            ],
        }

    def test_invalid_v3_is_rejected_and_valid_v3_uses_session_date(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            accepted = self._v3_record("공개 브리프", "2026/07/07/accepted.html")
            rejected = self._v3_record("거부 브리프", "2026/07/07/rejected.html")
            rejected["operator_note"] = "synthetic internal note"
            (data / "accepted.json").write_text(json.dumps(accepted, ensure_ascii=False), encoding="utf-8")
            (data / "rejected.json").write_text(json.dumps(rejected, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                summary = B.build(root)
            index = (root / "index.html").read_text(encoding="utf-8")
            self.assertEqual(summary, {"live": 1, "sample": 0, "pages": 1})
            self.assertTrue((root / "2026/07/07/accepted.html").exists())
            self.assertFalse((root / "2026/07/07/rejected.html").exists())
            self.assertIn("2026-07-07", index)
            self.assertIn("공개 1개 · 샘플 0개", index)
            self.assertNotIn("거부 브리프", index)
            self.assertIn("rejected 1", stderr.getvalue())
            self.assertNotIn("v3 verification", stderr.getvalue())

    def test_object_metadata_is_rejected_without_blocking_valid_v3(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            accepted = self._v3_record("정상 브리프", "2026/07/07/accepted.html")
            rejected = self._v3_record("오류 브리프", "2026/07/07/rejected.html")
            rejected["status"] = {"invalid": "published"}
            (data / "accepted.json").write_text(json.dumps(accepted, ensure_ascii=False), encoding="utf-8")
            (data / "rejected.json").write_text(json.dumps(rejected, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                summary = B.build(root)
            self.assertEqual(summary, {"live": 1, "sample": 0, "pages": 1})
            self.assertTrue((root / "2026/07/07/accepted.html").exists())
            self.assertFalse((root / "2026/07/07/rejected.html").exists())
            self.assertIn("rejected 1", stderr.getvalue())


class TestLegacyBuildGate(unittest.TestCase):
    """v1/v2도 검증 ERROR가 있으면 공개 빌드에서 제외한다."""

    def test_invalid_v1_and_v2_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            for version in (1, 2):
                (data / f"invalid-v{version}.json").write_text(json.dumps({
                    "schema_version": version, "date": "2026-07-07", "market_code": "KR",
                    "window_code": "close", "status": "live",
                }), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                summary = B.build(root)
            self.assertEqual(summary, {"live": 0, "sample": 0, "pages": 0})
            self.assertNotIn("invalid-v1", (root / "index.html").read_text(encoding="utf-8"))
            self.assertIn("rejected 2", stderr.getvalue())

    def test_invalid_out_path_is_rejected_without_blocking_other_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            valid = {
                "schema_version": 2, "date": "2026-07-07", "market_code": "KR", "window_code": "close",
                "status": "live", "out_path": "2026/07/07/accepted.html", "title": "정상 브리프",
            }
            invalid = {**valid, "out_path": "../escape.html", "title": "거부 브리프"}
            (data / "accepted.json").write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
            (data / "rejected.json").write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                summary = B.build(root)
            self.assertEqual(summary, {"live": 1, "sample": 0, "pages": 1})
            self.assertTrue((root / "2026/07/07/accepted.html").exists())
            self.assertFalse((root.parent / "escape.html").exists())
            self.assertTrue((root / "index.html").exists())
            self.assertTrue((root / "latest.json").exists())
            self.assertTrue((root / "rss.xml").exists())
            self.assertIn("rejected 1", stderr.getvalue())

    def test_unhashable_legacy_enum_and_tone_are_isolated(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            valid = {
                "schema_version": 2, "date": "2026-07-07", "market_code": "KR", "window_code": "close",
                "status": "live", "out_path": "2026/07/07/accepted.html", "title": "정상 브리프",
            }
            invalid = {**valid, "market_code": ["KR"], "metrics": [{"name": "X", "value": "1", "tone": {"flat": True}}]}
            (data / "accepted.json").write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
            (data / "rejected.json").write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                summary = B.build(root)
            self.assertEqual(summary, {"live": 1, "sample": 0, "pages": 1})
            self.assertTrue((root / "2026/07/07/accepted.html").exists())
            self.assertIn("rejected 1", stderr.getvalue())


class TestStaleBriefCleanup(unittest.TestCase):
    """빌드는 데이터에 없는 날짜형 브리프 페이지만 제거한다."""

    def test_removes_orphan_pages_without_touching_other_html_or_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "site"
            data = root / "data" / "2026" / "07" / "07"
            data.mkdir(parents=True)
            (data / "accepted.json").write_text(json.dumps({
                "schema_version": 2, "date": "2026-07-07", "market_code": "KR", "window_code": "close",
                "status": "live", "out_path": "2026/07/07/accepted.html", "title": "정상 브리프",
            }), encoding="utf-8")
            stale = root / "2026" / "07" / "07" / "rejected.html"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text("old rejected", encoding="utf-8")
            for path in (root / "assets" / "keep.html", root / "docs" / "keep.html"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("keep", encoding="utf-8")
            outside = Path(d) / "outside"
            outside.mkdir()
            (outside / "orphan.html").write_text("outside", encoding="utf-8")
            linked_parent = root / "2027" / "07"
            linked_parent.mkdir(parents=True)
            os.symlink(outside, linked_parent / "09")

            summary = B.build(root)

            self.assertEqual(summary, {"live": 1, "sample": 0, "pages": 1})
            self.assertTrue((root / "2026/07/07/accepted.html").exists())
            self.assertFalse(stale.exists())
            self.assertEqual((root / "assets/keep.html").read_text(encoding="utf-8"), "keep")
            self.assertEqual((root / "docs/keep.html").read_text(encoding="utf-8"), "keep")
            self.assertTrue((outside / "orphan.html").exists())


class TestEvidenceFirstIndex(unittest.TestCase):
    """첫 화면 최신 슬롯, 날짜 그룹, 필터 접근성 계약."""

    def _rec(self, market, window, date, status="published", **extra):
        rec = {
            "schema_version": 3, "market_code": market, "window_code": window,
            "market_session_date": date, "status": status,
            "evidence_status": "confirmed", "title": f"{market} {window} {date}",
            "out_path": f"{date.replace('-', '/')}/{market}-{window}.html",
            "metrics": [{"label": "지수", "value": date[-2:]}],
        }
        rec.update(extra)
        return rec

    def test_latest_slots_are_fixed_order_and_use_latest_per_slot(self):
        records = [
            self._rec("US", "close", "2026-07-16"),
            self._rec("KR", "preopen", "2026-07-15"),
            self._rec("KR", "preopen", "2026-07-17"),
            self._rec("US", "preopen", "2026-07-14"),
        ]
        slots = B.latest_slots(records)
        self.assertEqual([(m, w) for m, w, _ in slots], [
            ("KR", "preopen"), ("KR", "close"), ("US", "preopen"), ("US", "close"),
        ])
        self.assertEqual(slots[0][2]["market_session_date"], "2026-07-17")
        self.assertIsNone(slots[1][2])
        page = B.build_index_html(records)
        self.assertLess(page.index('data-slot="KR-preopen"'), page.index('data-slot="KR-close"'))
        self.assertIn("아직 기록 없음", page)
        self.assertIn('data-stale-date="2026-07-17"', page)
        self.assertIn("이전 기준일", page)
        self.assertNotIn("live-dot", page)

    def test_archive_groups_and_filter_accessibility_markup(self):
        records = [
            self._rec("KR", "close", "2026-07-17"),
            self._rec("US", "preopen", "2026-07-16", status="partial"),
        ]
        page = B.build_index_html(records)
        self.assertIn('<nav class="site-nav" aria-label="주요 탐색">', page)
        self.assertIn('class="skip-link" href="#latest-focus"', page)
        self.assertIn('id="archive-result-count" role="status" aria-live="polite"', page)
        self.assertIn('class="archive-group" data-date="2026-07-17"', page)
        self.assertIn("group.hidden=visible===0", page)
        self.assertIn("방법론·검증 코드", page)

    def test_current_focus_foregrounds_latest_record_across_fixed_slots(self):
        records = [
            self._rec("KR", "preopen", "2026-07-17"),
            self._rec("KR", "close", "2026-07-16"),
            self._rec("US", "preopen", "2026-09-03", status="partial"),
            self._rec("US", "close", "2026-07-17"),
        ]
        page = B.build_index_html(records)
        focus = page[page.index('class="latest-focus'):page.index('class="latest-section"')]
        self.assertIn("US preopen 2026-09-03", focus)
        self.assertIn('href="/market-briefs/2026/09/03/US-preopen.html"', focus)
        self.assertIn("부분 공개", focus)
        self.assertIn("기준일 2026-09-03", focus)

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
        self.assertIn("2개 과거 기록 · 원문 링크 없음", page)
        self.assertIn("1개 부분 공개", page)
        self.assertIn('data-freshness="latest"', page)
        self.assertIn('data-freshness="older"', page)
        self.assertIn('data-freshness="missing"', page)
        self.assertIn("가장 최근 기준일", page)
        self.assertIn("이전 기준일", page)
        self.assertIn("기록 없음", page)

    def test_current_focus_handles_empty_latest_slots(self):
        page = B.build_index_html([])
        focus = page[page.index('class="latest-focus'):page.index('class="latest-section"')]
        self.assertIn("아직 읽을 검증 기록 없음", focus)
        self.assertIn("기록 없음", page)
        self.assertIn('data-freshness="missing"', page)

    def test_latest_card_accessible_name_contains_visible_label(self):
        """최신 카드 링크의 accessible name이 화면 라벨을 포함한다."""
        page = B.build_index_html([self._rec("KR", "close", "2026-07-17")])
        self.assertIn(
            'aria-label="KR close 2026-07-17 브리프 읽기 →">브리프 읽기 →',
            page,
        )

    def test_index_internal_links_keep_public_prefix(self):
        """/market-briefs 랜딩 페이지의 내부 링크가 공개 prefix를 유지한다."""
        page = B.build_index_html([self._rec("KR", "close", "2026-07-17")])
        for href in (
            '/market-briefs/index.html',
            '/market-briefs/assets/brief.css',
            '/market-briefs/assets/favicon.svg',
            '/market-briefs/rss.xml',
            '/market-briefs/2026/07/17/KR-close.html',
        ):
            self.assertIn(f'href="{href}"', page)

    def test_public_href_rejects_parent_traversal(self):
        """공개 URL helper가 prefix 밖으로 탈출하는 경로를 거부한다."""
        for path in ("../escape.html", "2026/../escape.html", r"..\escape.html"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                B._public_href(path)


class TestEvidenceFirstDetail(unittest.TestCase):
    """상세 페이지의 점진적 공개 순서와 공개 근거 링크 계약."""

    def test_legacy_unfurl_description_is_warned_without_changing_v3(self):
        legacy = render({"schema_version": 2, "title": "레거시", "takeaway": "과거 요약"})
        v3 = render({"schema_version": 3, "title": "V3", "summary": "검증 요약"})
        for attribute in ('name="description"', 'property="og:description"'):
            self.assertIn(f'<meta {attribute} content="과거 기록 · 원문 링크 없음 · 과거 요약"', legacy)
            self.assertIn(f'<meta {attribute} content="검증 요약"', v3)
        self.assertNotIn("레거시 미검증 · 검증 요약", v3)

    def test_legacy_warning_and_section_order(self):
        page = render({
            "schema_version": 2, "date": "2026-07-17", "status": "live",
            "title": "레거시", "takeaway": "요약", "metrics": [{"name": "지수", "value": "1"}],
            "changes": [{"dir": "up", "text": "변화"}], "drivers": [{"label": "동인", "text": "본문"}],
            "risks": ["위험"], "watch": ["다음"], "quality": [{"label": "Status", "value": "ok"}],
        })
        self.assertIn("레거시 · 원문 출처 링크 미제공", page)
        self.assertNotIn("출처 확인 데이터만 사용", page)
        order = ["한 줄 결론", "숫자로 보는 시장", "어제 대비 변화", "오늘의 핵심 동인",
                 "리스크 / 무효화 기준", "내일 볼 센서", "근거와 생성 정보"]
        self.assertEqual(sorted(page.index(text) for text in order), [page.index(text) for text in order])

    def test_v3_sources_claims_and_field_fallbacks_are_linked(self):
        page = render({
            "schema_version": 3, "status": "published", "evidence_status": "confirmed",
            "market_session_date": "2026-07-17", "title": "V3", "summary": "검증 요약",
            "metrics": [{"label": "KOSPI", "value": "3000", "source_ids": ["s1"],
                         "evidence_status": "confirmed"}],
            "claims": [
                {"kind": "fact", "text": "사실 문장", "source_ids": ["s1"], "evidence_status": "confirmed"},
                {"kind": "analysis", "text": "분석 문장", "source_ids": ["s1"], "evidence_status": "partial"},
                {"kind": "hypothesis", "text": "가설 문장", "source_ids": [], "evidence_status": "not_proven"},
            ],
            "drivers": [{"label": "드라이버", "text": "설명", "source_ids": ["s1"]}],
            "sources": [{"source_id": "s1", "publisher": "거래소", "title": "마감 데이터",
                         "url": "https://example.test/source", "as_of": "2026-07-17T07:00:00Z",
                         "retrieved_at": "2026-07-17T07:10:00Z", "status": "confirmed"}],
        })
        anchor = _source_anchor("s1")
        self.assertIn(f'id="{anchor}"', page)
        self.assertIn('href="https://example.test/source"', page)
        self.assertGreaterEqual(page.count(f'href="#{anchor}"'), 3)
        for label in ("사실", "분석", "가설"):
            self.assertIn(f'<span class="claim-kind">{label}</span>', page)
        self.assertIn("KOSPI", page)
        self.assertIn("드라이버", page)

    def test_counterevidence_follows_claims_with_item_evidence_and_sources(self):
        page = render({
            "schema_version": 3, "status": "published", "evidence_status": "confirmed",
            "claims": [
                {"kind": "fact", "text": "확인 주장", "source_ids": ["s1"],
                 "evidence_status": "confirmed"},
                {"kind": "analysis", "text": "부분 주장", "source_ids": ["s1"],
                 "evidence_status": "partial"},
            ],
            "counterevidence": [{"text": "반대 데이터", "source_ids": ["s1"],
                                  "evidence_status": "not_proven"}],
            "sources": [{"source_id": "s1", "publisher": "거래소", "title": "원문",
                         "url": "https://example.test/source", "as_of": "2026-07-17",
                         "status": "confirmed"}],
        })
        self.assertLess(page.index("주장과 해석"), page.index("반대 근거"))
        self.assertIn('<span class="item-evidence confirmed">근거 확인</span>', page)
        self.assertIn('<span class="item-evidence partial">근거 일부</span>', page)
        self.assertIn('<span class="item-evidence not_proven">미검증</span>', page)
        self.assertIn("반대 데이터", page)
        anchor = _source_anchor("s1")
        self.assertIn(f'href="#{anchor}"', page)

    def test_source_anchor_hash_prevents_slug_and_empty_collisions(self):
        source_ids = ["a b", "a-b", "!!!"]
        anchors = [_source_anchor(source_id) for source_id in source_ids]
        self.assertEqual(len(set(anchors)), len(anchors))
        page = render({
            "schema_version": 3,
            "claims": [{"kind": "fact", "text": source_id, "source_ids": [source_id],
                        "evidence_status": "confirmed"} for source_id in source_ids],
            "sources": [{"source_id": source_id, "publisher": "p", "title": source_id,
                         "url": "https://example.test", "as_of": "2026-07-17", "status": "confirmed"}
                        for source_id in source_ids],
        })
        for anchor in anchors:
            self.assertIn(f'id="{anchor}"', page)
            self.assertIn(f'href="#{anchor}"', page)

    def test_canonical_og_share_rss_and_adjacent_nav(self):
        context = {
            "canonical_url": "https://noah-market-briefs.vercel.app/market-briefs/2026/07/17/x.html",
            "older": {"title": "이전", "href": "older.html"},
            "newer": {"title": "다음", "href": "newer.html"},
        }
        page = render({"schema_version": 3, "title": "V3", "summary": "요약",
                       "generated_at_utc": "2026-07-17T07:30:00Z"}, page_context=context)
        self.assertIn('<link rel="canonical" href="https://noah-market-briefs.vercel.app/market-briefs/2026/07/17/x.html"', page)
        self.assertIn('<meta property="og:url" content="https://noah-market-briefs.vercel.app/market-briefs/2026/07/17/x.html"', page)
        self.assertIn('content="https://noah-market-briefs.vercel.app/market-briefs/docs/images/index.png"', page)
        self.assertIn('name="twitter:card" content="summary_large_image"', page)
        self.assertIn('type="application/rss+xml"', page)
        self.assertIn('id="share-button"', page)
        self.assertIn("navigator.share", page)
        self.assertIn('id="share-status" role="status" aria-live="polite"', page)
        self.assertIn('aria-label="인접 브리프"', page)
        self.assertIn('href="older.html"', page)
        self.assertIn('href="newer.html"', page)
        self.assertIn("then(copied,manualCopy)", page)
        self.assertIn("if(ok) copied();else copyFailed();", page)
        self.assertIn("자동 복사에 실패했습니다. 주소창의 링크를 직접 복사해 주세요.", page)

    def test_write_pages_computes_relative_assets_index_and_rss_for_deep_path(self):
        record = {
            "schema_version": 3, "title": "깊은 경로", "status": "published",
            "out_path": "archive/2026/07/17/deep/brief.html",
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            B.write_brief_pages([record], root)
            page = (root / record["out_path"]).read_text(encoding="utf-8")
        self.assertIn('href="../../../../../assets/brief.css"', page)
        self.assertIn('href="../../../../../assets/favicon.svg"', page)
        self.assertIn('href="../../../../../index.html"', page)
        self.assertIn('href="../../../../../rss.xml"', page)


class TestEvidenceFeedsAndStatuses(unittest.TestCase):
    """동일 검증 레코드로 만드는 latest.json/RSS와 상태 표시 계약."""

    def _rec(self, market, window, status, version=3, **extra):
        rec = {
            "schema_version": version, "market_code": market, "window_code": window,
            "market_session_date": "2026-07-17", "date": "2026-07-17", "status": status,
            "evidence_status": "confirmed", "title": f"{market}-{window}-{status}",
            "out_path": f"2026/07/17/{market}-{window}-{status}.html",
            "sources": [{"source_id": "source-public", "status": "confirmed"}],
            "metrics": [{"source_ids": ["source-public"], "evidence_status": "confirmed"}],
        }
        rec.update(extra)
        return rec

    def test_status_badges_are_explicit_and_failed_is_not_live(self):
        labels = {
            "live": "공개", "published": "공개", "sample": "샘플", "partial": "부분 공개",
            "skipped_market_closed": "휴장으로 건너뜀", "failed": "생성 실패", "corrected": "정정됨",
        }
        for status, label in labels.items():
            badge = B.status_badge({"schema_version": 3, "status": status})
            self.assertIn(label, badge)
            if status in {"failed", "skipped_market_closed"}:
                self.assertNotIn('status-badge live', badge)
        self.assertIn("과거 기록 · 원문 링크 없음", B.status_badge({"schema_version": 2, "status": "live"}))

    def test_latest_json_and_rss_are_deterministic_and_legacy_safe(self):
        legacy_v1 = self._rec("KR", "preopen", "live", version=1,
                              title="SECRET_HOLDING_TITLE", out_path="secret/holding-v1.html")
        legacy_v2 = self._rec("KR", "close", "live", version=2,
                              title="SECRET_V2_TITLE", out_path="secret/holding-v2.html")
        v3 = self._rec("US", "close", "published", summary="검증된 요약")
        records = [v3, legacy_v1, legacy_v2]
        latest_a = B.build_latest_json(records)
        latest_b = B.build_latest_json(list(reversed(records)))
        rss = B.build_rss_xml(records)
        self.assertEqual(latest_a, latest_b)
        self.assertIn('"evidence_status": "legacy_unverified"', latest_a)
        for secret in ("SECRET_HOLDING_TITLE", "SECRET_V2_TITLE", "secret/holding-v1.html", "secret/holding-v2.html"):
            self.assertNotIn(secret, latest_a)
            self.assertNotIn(secret, rss)
        self.assertIn("검증된 요약", latest_a)
        self.assertIn("검증된 요약", rss)
        self.assertNotIn("legacy_unverified", rss)

    def test_summary_requires_public_or_corrected_confirmed_v3(self):
        records = [
            self._rec("KR", "preopen", "published", summary="ALLOW_PUBLISHED"),
            self._rec("KR", "close", "corrected", summary="ALLOW_CORRECTED"),
            self._rec("US", "preopen", "failed", summary="BLOCK_FAILED"),
            self._rec("US", "close", "partial", summary="BLOCK_PARTIAL"),
            self._rec("KR", "preopen", "published", evidence_status="partial",
                      summary="BLOCK_EVIDENCE_PARTIAL", out_path="2026/07/17/partial-evidence.html"),
            self._rec("KR", "close", "published", evidence_status="not_proven",
                      summary="BLOCK_NOT_PROVEN", out_path="2026/07/17/not-proven.html"),
        ]
        rss = B.build_rss_xml(records)
        latest_status = B.build_latest_json(records[:4])
        latest_evidence = B.build_latest_json(records[4:])
        self.assertIn("ALLOW_PUBLISHED", rss)
        self.assertIn("ALLOW_CORRECTED", rss)
        self.assertIn("ALLOW_PUBLISHED", latest_status)
        self.assertIn("ALLOW_CORRECTED", latest_status)
        for blocked in ("BLOCK_FAILED", "BLOCK_PARTIAL", "BLOCK_EVIDENCE_PARTIAL", "BLOCK_NOT_PROVEN"):
            self.assertNotIn(blocked, rss)
            self.assertNotIn(blocked, latest_status + latest_evidence)

    def test_confirmed_summary_without_linked_evidence_never_enters_feed(self):
        rec = self._rec("KR", "close", "published", summary="BLOCK_EMPTY_EVIDENCE",
                        sources=[], metrics=[])
        self.assertNotIn("BLOCK_EMPTY_EVIDENCE", B.build_latest_json([rec]))
        self.assertNotIn("BLOCK_EMPTY_EVIDENCE", B.build_rss_xml([rec]))

    def test_confirmed_summary_requires_confirmed_source_and_item(self):
        rec = self._rec("KR", "close", "published", summary="BLOCK_PARTIAL_EVIDENCE",
                        sources=[{"source_id": "source-public", "status": "not_proven"}],
                        metrics=[{"source_ids": ["source-public"], "evidence_status": "partial"}])
        self.assertNotIn("BLOCK_PARTIAL_EVIDENCE", B.build_latest_json([rec]))
        self.assertNotIn("BLOCK_PARTIAL_EVIDENCE", B.build_rss_xml([rec]))

    def test_build_writes_both_feed_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            B.build(root)
            self.assertTrue((root / "latest.json").exists())
            self.assertTrue((root / "rss.xml").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
