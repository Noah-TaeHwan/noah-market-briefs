#!/usr/bin/env python3
"""verify_brief.py 회귀 테스트 (표준 unittest, 의존성 0).

검증 스크립트의 스키마·소스 디시플린·논지 생략 계약 규칙을 잠근다.
build.py 테스트(test_build.py)는 렌더 파이프라인을 테스트하고,
이 파일은 브리프 JSON 데이터 품질 자체를 테스트한다.

실행: python3 tests/test_verify.py  (또는 python3 -m unittest discover -s tests)
"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from verify_brief import (  # noqa: E402
    Severity, load_named_holdings, main, verify_file, verify_record,
)


def _valid_record():
    """통과해야 하는 최소 완전 브리프 레코드."""
    return {
        "schema_version": 2,
        "date": "2026-07-07",
        "market_code": "KR",
        "window_code": "close",
        "status": "live",
        "out_path": "2026/07/07/korea-close.html",
        "title": "한국 시장 마감 — 2026-07-07",
        "metrics": [
            {"name": "KOSPI", "value": "7,656.31", "tone": "down",
             "note": "-4.91% · Naver Finance, 2026.07.07"},
        ],
        "drivers": [{"label": "테스트", "text": "내용"}],
    }


class TestIndexMetaValidation(unittest.TestCase):
    """필수 index-meta 필드 검증."""

    def test_valid_record_no_errors(self):
        findings = verify_record(_valid_record())
        errors = [f for f in findings if f.severity == Severity.ERROR]
        self.assertEqual(errors, [])

    def test_missing_date_is_error(self):
        rec = _valid_record()
        del rec["date"]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "date" in f.message
                            for f in findings))

    def test_missing_market_code_is_error(self):
        rec = _valid_record()
        del rec["market_code"]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "market_code" in f.message
                            for f in findings))

    def test_invalid_market_code_is_error(self):
        rec = _valid_record()
        rec["market_code"] = "JP"
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "market_code" in f.message
                            for f in findings))

    def test_invalid_window_code_is_error(self):
        rec = _valid_record()
        rec["window_code"] = "intraday"
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "window_code" in f.message
                            for f in findings))

    def test_invalid_status_is_error(self):
        rec = _valid_record()
        rec["status"] = "draft"
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "status" in f.message
                            for f in findings))

    def test_missing_out_path_is_error(self):
        rec = _valid_record()
        del rec["out_path"]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "out_path" in f.message
                            for f in findings))


class TestMetricsValidation(unittest.TestCase):
    """metrics[] 톤·필드 검증."""

    def test_valid_tones_pass(self):
        rec = _valid_record()
        rec["metrics"] = [
            {"name": "A", "value": "1", "tone": t} for t in ("up", "down", "flat", "warn")
        ]
        findings = verify_record(rec)
        errors = [f for f in findings if f.severity == Severity.ERROR]
        self.assertEqual(errors, [])

    def test_invalid_tone_is_error(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "X", "value": "1", "tone": "bullish"}]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "tone" in f.message
                            for f in findings))

    def test_missing_tone_is_warning(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "X", "value": "1"}]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.WARNING and "tone" in f.message
                            for f in findings))

    def test_metric_missing_value_is_error(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "X", "tone": "up"}]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "value" in f.message
                            for f in findings))


class TestSourceDiscipline(unittest.TestCase):
    """소스 디시플린 — 숫자 metric은 note에 출처가 있어야 한다."""

    def test_numeric_metric_without_source_is_warning(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "KOSPI", "value": "7,656.31", "tone": "down"}]
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.WARNING and "출처" in f.message
                            for f in findings))

    def test_unknown_value_does_not_require_source(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "채권", "value": "미확인", "tone": "flat"}]
        findings = verify_record(rec)
        source_warnings = [f for f in findings if f.severity == Severity.WARNING
                           and "출처" in f.message]
        self.assertEqual(source_warnings, [])

    def test_metric_with_source_passes(self):
        rec = _valid_record()
        rec["metrics"] = [{"name": "KOSPI", "value": "7,656.31", "tone": "down",
                           "note": "-4.91% · Naver Finance, 2026.07.07"}]
        findings = verify_record(rec)
        source_warnings = [f for f in findings if f.severity == Severity.WARNING
                           and "출처" in f.message]
        self.assertEqual(source_warnings, [])


class TestHypothesisFieldCompleteness(unittest.TestCase):
    """hypothesis_review / next_hypotheses 필드 완전성."""

    def test_complete_hypothesis_review_passes(self):
        rec = _valid_record()
        rec["hypothesis_review"] = [{
            "previous_hypothesis": "테스트", "verdict": "적중",
            "evidence": "근거", "reason": "이유", "lesson": "교훈",
        }]
        findings = verify_record(rec)
        errors = [f for f in findings if f.severity == Severity.ERROR
                  and "hypothesis_review" in f.message]
        self.assertEqual(errors, [])

    def test_incomplete_hypothesis_review_is_error(self):
        rec = _valid_record()
        rec["hypothesis_review"] = [{"verdict": "적중"}]  # 필드 누락
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "hypothesis_review" in f.message
                            for f in findings))

    def test_complete_next_hypotheses_passes(self):
        rec = _valid_record()
        rec["next_hypotheses"] = [{
            "hypothesis": "가설", "observable": "관측",
            "invalidation": "반증", "horizon": "next KR close",
        }]
        findings = verify_record(rec)
        errors = [f for f in findings if f.severity == Severity.ERROR
                  and "next_hypotheses" in f.message]
        self.assertEqual(errors, [])

    def test_incomplete_next_hypotheses_is_error(self):
        rec = _valid_record()
        rec["next_hypotheses"] = [{"hypothesis": "가설"}]  # 필드 누락
        findings = verify_record(rec)
        self.assertTrue(any(f.severity == Severity.ERROR and "next_hypotheses" in f.message
                            for f in findings))


# 감시 목록은 저장소에 두지 않으므로(verify_brief.load_named_holdings 참고)
# 테스트는 실제 이름 대신 합성 이름을 주입해 검사 로직만 검증한다.
_TEST_HOLDINGS = ("테스트보유A", "테스트보유B")


class TestNamedHoldingsExclusion(unittest.TestCase):
    """v2 공개 계약 — named holdings는 어느 공개 필드에도 없어야 한다."""

    def test_clean_theses_pass(self):
        rec = _valid_record()
        rec["theses"] = [{"name": "위험선호", "signal": "회복", "body": "본문"}]
        findings = verify_record(rec, _TEST_HOLDINGS)
        holdings_errors = [f for f in findings if "holdings" in f.message.lower()
                           or "논지" in f.message]
        self.assertEqual(holdings_errors, [])

    def test_named_holdings_in_theses_is_error(self):
        rec = _valid_record()
        rec["theses"] = [{"name": "테스트보유A", "signal": "높음", "body": "본문"}]
        findings = verify_record(rec, _TEST_HOLDINGS)
        self.assertTrue(any(f.severity == Severity.ERROR and "논지" in f.message
                            for f in findings))

    def test_second_named_holding_in_theses_is_error(self):
        rec = _valid_record()
        rec["theses"] = [{"name": "테스트보유B", "signal": "NII", "body": "본문"}]
        findings = verify_record(rec, _TEST_HOLDINGS)
        self.assertTrue(any(f.severity == Severity.ERROR and "논지" in f.message
                            for f in findings))

    def test_named_holding_in_risk_is_error_for_v2(self):
        rec = _valid_record()
        rec["risks"] = ["테스트보유A 할인율을 따로 점검"]
        findings = verify_record(rec, _TEST_HOLDINGS)
        self.assertTrue(any(f.severity == Severity.ERROR and "risks[0]" in f.message
                            for f in findings))

    def test_schema_v1_legacy_archive_is_not_retroactively_rejected(self):
        rec = _valid_record()
        rec["schema_version"] = 1
        rec["theses"] = [{"name": "테스트보유A", "signal": "legacy", "body": "과거 기록"}]
        errors = [f for f in verify_record(rec, _TEST_HOLDINGS) if f.severity == Severity.ERROR]
        self.assertEqual(errors, [])

    def test_empty_holdings_list_disables_the_check(self):
        """목록이 비면(로컬 파일 없음) 어떤 이름도 위반으로 보지 않는다."""
        rec = _valid_record()
        rec["theses"] = [{"name": "테스트보유A", "signal": "높음", "body": "본문"}]
        errors = [f for f in verify_record(rec, ()) if f.severity == Severity.ERROR]
        self.assertEqual(errors, [])


class TestVerifyFile(unittest.TestCase):
    """verify_file() 파일 단위 검증 + exit code."""

    def test_valid_file_returns_zero_errors(self):
        rec = _valid_record()
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump(rec, f)
            f.flush()
            findings = verify_file(Path(f.name))
        errors = [x for x in findings if x.severity == Severity.ERROR]
        self.assertEqual(errors, [])

    def test_broken_json_returns_error(self):
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            f.write('{"date": "2026-07-07",')  # 깨진 JSON
            f.flush()
            findings = verify_file(Path(f.name))
        self.assertTrue(any(x.severity == Severity.ERROR for x in findings))


class TestRealData(unittest.TestCase):
    """실제 data/ 레코드 전체 검증 — 모두 ERROR 0이어야 한다."""

    def test_all_live_records_have_no_errors(self):
        data_dir = REPO / "data"
        if not data_dir.exists():
            self.skipTest("data/ 디렉토리 없음")
        jsons = sorted(data_dir.rglob("*.json"))
        self.assertGreater(len(jsons), 0, "data/에 JSON이 없음")
        for jf in jsons:
            findings = verify_file(jf)
            errors = [f for f in findings if f.severity == Severity.ERROR]
            self.assertEqual(errors, [], f"{jf.name}에 ERROR가 있음:\n"
                             + "\n".join(f"  [{f.severity.value}] {f.message}" for f in errors))


class TestNamedHoldingsFile(unittest.TestCase):
    """감시 목록은 저장소 밖 파일에서만 온다 — 없으면 검사가 조용히 비활성된다."""

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_named_holdings(Path(d) / "none.local"), ())

    def test_reads_lines_and_skips_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "holdings.local"
            p.write_text("# 주석\n\n  이름A  \n이름B\n", encoding="utf-8")
            self.assertEqual(load_named_holdings(p), ("이름A", "이름B"))


class TestVerifyCli(unittest.TestCase):
    """CLI exit code 계약 — 0=ERROR 없음, 1=ERROR 있음."""

    def _run(self, payload) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "brief.json"
            p.write_text(payload if isinstance(payload, str)
                         else json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = main([str(p)])
            return code, buf.getvalue()

    def test_valid_record_exits_zero(self):
        code, out = self._run(_valid_record())
        self.assertEqual(code, 0)
        self.assertIn("0 ERROR", out)

    def test_missing_index_meta_exits_one(self):
        """index 메타(INDEX_META_REQUIRED)가 빠지면 ERROR — 인덱스에 실을 수 없는 레코드다."""
        for field in ("date", "market_code", "window_code", "status", "out_path"):
            rec = _valid_record()
            del rec[field]
            with self.subTest(missing=field):
                code, out = self._run(rec)
                self.assertEqual(code, 1)
                self.assertIn("ERROR", out)

    def test_malformed_json_exits_one_without_raising(self):
        code, out = self._run("{ this is not json }")
        self.assertEqual(code, 1)
        self.assertIn("JSON 파싱 실패", out)

    def test_missing_file_exits_one(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(REPO / "data" / "does-not-exist.json")])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
