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
            "theses": [{"name": "글로벌 증권사", "signal": "NII vs activity", "body": "본문"}],  # level/lead 없음
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
                json.dumps({"date": "2026-06-24", "window_code": "preopen"}))
            (dd / "korea-close.json").write_text(
                json.dumps({"date": "2026-06-24", "window_code": "close"}))
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
            "date": date, "market_code": market, "window_code": window,
            "out_path": f"{ymd}/{market}-{window}.html"}), encoding="utf-8")

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
                "date": "2026-06-23", "window_code": "close",
                "out_path": "2026/06/23/ok.html", "title": "ok"}), encoding="utf-8")
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
        html = render({"theses": [{"name": "글로벌 증권사", "signal": "x", "body": "b"}]})
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
