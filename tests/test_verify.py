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


def _valid_v3_record():
    """통과해야 하는 PublicBriefV3 최소 공개 레코드."""
    return {
        "schema_version": 3,
        "brief_id": "brief-2026-07-07-kr-close",
        "market_code": "KR",
        "window_code": "close",
        "market_session_date": "2026-07-07",
        "generated_at_utc": "2026-07-07T07:30:00Z",
        "cutoff_at_utc": "2026-07-07T07:20:00Z",
        "market_timezone": "Asia/Seoul",
        "status": "published",
        "evidence_status": "confirmed",
        "methodology_version": "public-brief-v3",
        "public_receipt_sha256": "a" * 64,
        "out_path": "2026/07/07/korea-close.html",
        "title": "한국 시장 마감 — 2026-07-07",
        "sources": [{
            "source_id": "source-market-close",
            "publisher": "Synthetic Public Source",
            "title": "Market close",
            "url": "https://example.test/market-close",
            "as_of": "2026-07-07T07:00:00Z",
            "retrieved_at": "2026-07-07T07:20:00Z",
            "source_type": "market_data",
            "status": "confirmed",
        }],
        "metrics": [{
            "metric_id": "metric-kospi", "label": "KOSPI", "name": "KOSPI",
            "value": "7,656.31", "unit": "points", "delta": "-4.91%",
            "as_of": "2026-07-07T07:00:00Z", "tone": "down", "note": "공개 출처",
            "source_ids": ["source-market-close"], "evidence_status": "confirmed",
        }],
        "claims": [{
            "claim_id": "claim-market-close", "kind": "fact", "text": "공개 시장 종가 관측",
            "as_of": "2026-07-07T07:00:00Z", "source_ids": ["source-market-close"],
            "evidence_status": "confirmed",
        }],
        "missing_data": [
            {"label": "코스피", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
            {"label": "USD/KRW", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
            {"label": "VKOSPI", "reason": "픽스처 세션 슬롯 커버", "evidence_status": "not_proven"},
        ],
    }


def _session_metric(metric_id: str, as_of: str = "2026-07-07T07:00:00Z") -> dict:
    """세션 슬롯 커버용 최소 메트릭."""
    return {
        "metric_id": metric_id, "label": metric_id, "value": "1", "unit": "x",
        "delta": "0", "as_of": as_of, "source_ids": ["source-market-close"],
        "evidence_status": "confirmed",
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

    def test_unsupported_schema_version_is_error(self):
        rec = _valid_record()
        rec["schema_version"] = 4
        self.assertTrue(any(f.severity == Severity.ERROR and "schema_version" in f.message
                            for f in verify_record(rec)))

    def test_out_path_must_be_canonical_public_brief_path(self):
        for out_path in (
            "/tmp/brief.html", "../brief.html", "https://example.test/brief.html",
            "2026/07/brief.html", "2026/07/07/brief.htm", "2026/07/07/Brief.html",
            "2026/07/07/link.html/..",
        ):
            rec = _valid_record()
            rec["out_path"] = out_path
            self.assertTrue(any(f.severity == Severity.ERROR and "out_path" in f.message
                                for f in verify_record(rec)), out_path)

    def test_out_path_date_must_match_legacy_and_v3_session_date(self):
        legacy = _valid_record()
        legacy["out_path"] = "2026/07/08/korea-close.html"
        v3 = _valid_v3_record()
        v3["out_path"] = "2026/07/08/korea-close.html"
        for rec in (legacy, v3):
            self.assertTrue(any(f.severity == Severity.ERROR and "out_path" in f.message
                                for f in verify_record(rec)))


class TestPublicBriefV3(unittest.TestCase):
    """PublicBriefV3 공개 메타데이터·출처·개인정보 차단 계약."""

    def _errors(self, rec):
        return [f.message for f in verify_record(rec) if f.severity == Severity.ERROR]

    def test_valid_v3_record_has_no_errors(self):
        self.assertEqual(self._errors(_valid_v3_record()), [])

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

    def test_v3_rejects_unknown_top_level_field(self):
        rec = _valid_v3_record()
        rec["operator_note"] = "synthetic internal memo"
        self.assertTrue(any("operator_note" in message for message in self._errors(rec)))

    def test_v3_requires_public_metadata_and_valid_enums(self):
        rec = _valid_v3_record()
        del rec["public_receipt_sha256"]
        rec["status"] = "live"
        rec["evidence_status"] = "unverified"
        errors = self._errors(rec)
        self.assertTrue(any("public_receipt_sha256" in message for message in errors))
        self.assertTrue(any("status" in message for message in errors))
        self.assertTrue(any("evidence_status" in message for message in errors))

    def test_v3_validates_sources_and_metric_claim_references(self):
        rec = _valid_v3_record()
        rec["sources"][0]["url"] = "http://example.test/not-https"
        rec["metrics"][0]["source_ids"] = ["missing-source"]
        rec["claims"][0]["kind"] = "unsupported"
        rec["claims"][0]["source_ids"] = "source-market-close"
        errors = self._errors(rec)
        self.assertTrue(any("https" in message for message in errors))
        self.assertTrue(any("missing-source" in message for message in errors))
        self.assertTrue(any("claims[0].kind" in message for message in errors))
        self.assertTrue(any("claims[0].source_ids" in message for message in errors))

    def test_v3_corrected_requires_correction_receipt_fields(self):
        rec = _valid_v3_record()
        rec["status"] = "corrected"
        errors = self._errors(rec)
        for field in ("correction_note", "corrected_at", "supersedes"):
            self.assertTrue(any(field in message for message in errors))

    def test_v3_rejects_private_identifiers_or_paths_recursively(self):
        rec = _valid_v3_record()
        rec["drivers"] = [
            {"label": "a", "text": "/Users/synthetic/note.txt"},
            {"label": "b", "text": ".tradingcodex/cache"},
            {"label": "c", "text": "trading/research/synthetic"},
            {"label": "d", "text": "workflow_synthetic_123"},
        ]
        errors = self._errors(rec)
        self.assertEqual(sum("비공개" in message for message in errors), 4)

    def test_v3_rejects_unknown_nested_fields_and_wrong_types(self):
        rec = _valid_v3_record()
        rec["sources"][0]["internal_path"] = "safe-looking"
        rec["claims"][0]["as_of"] = "2026-07-07 07:00:00"
        rec["claims"][0]["extra"] = "no"
        rec["metrics"][0]["unit"] = 1
        rec["metrics"][0]["extra"] = "no"
        errors = self._errors(rec)
        for field in ("sources[0].internal_path", "claims[0].as_of", "claims[0].extra", "metrics[0].unit", "metrics[0].extra"):
            self.assertTrue(any(field in message for message in errors))

    def test_v3_validates_canonical_dates_timezone_and_cutoff(self):
        rec = _valid_v3_record()
        rec["market_session_date"] = "2026/07/07"
        rec["generated_at_utc"] = "2026-07-07T07:20:00Z"
        rec["cutoff_at_utc"] = "2026-07-07T07:30:00Z"
        rec["market_timezone"] = "Not/AZone"
        rec["sources"][0]["retrieved_at"] = "2026-07-07"
        rec["corrected_at"] = "2026-07-07T07:20:00+00:00"
        errors = self._errors(rec)
        for field in ("market_session_date", "cutoff_at_utc", "market_timezone", "sources[0].retrieved_at", "corrected_at"):
            self.assertTrue(any(field in message for message in errors))
        rec["generated_at_utc"] = "2026-07-07T07:20:00+00:00"
        self.assertTrue(any("generated_at_utc" in message for message in self._errors(rec)))

    def test_v3_allows_benign_private_sector_phrase(self):
        rec = _valid_v3_record()
        rec["sources"][0]["title"] = "Private Sector Employment Report"
        self.assertEqual(self._errors(rec), [])

    def test_v3_accepts_closed_public_support_fields(self):
        rec = _valid_v3_record()
        rec.update({
            "summary": "공개 요약", "next_handoff": "다음 공개 점검",
            "changes": [{"dir": "down", "text": "지수 하락", "source_ids": ["source-market-close"],
                         "evidence_status": "confirmed"}],
            "drivers": [{"label": "금리", "text": "공개 관측", "source_ids": ["source-market-close"],
                         "evidence_status": "confirmed"}],
            "counterevidence": [{"text": "반대 공개 관측", "source_ids": ["source-market-close"],
                                   "evidence_status": "partial"}],
            "hypotheses": [{"hypothesis_id": "hyp-1", "text": "가설", "observable": "관측값",
                              "invalidation": "반증값", "horizon": "다음 장", "source_ids": ["source-market-close"],
                              "evidence_status": "partial"}],
            "reviews": [{"review_id": "review-1", "hypothesis_id": "hyp-1", "verdict": "부분 적중",
                         "evidence": "근거", "reason": "이유", "lesson": "교훈",
                         "source_ids": ["source-market-close"], "evidence_status": "confirmed"}],
            "missing_data": [
                {"label": "코스피", "reason": "공개 시차", "evidence_status": "not_proven"},
                {"label": "USD/KRW", "reason": "공개 시차", "evidence_status": "not_proven"},
                {"label": "VKOSPI", "reason": "공개 시차", "evidence_status": "not_proven"},
                {"label": "수급", "reason": "공개 시차", "evidence_status": "not_proven"},
            ],
            "quality": [{"label": "source/date", "value": "same-date"}],
            "risks": ["변동성 확대"], "today_learning": ["공개 근거를 재확인"],
        })
        self.assertEqual(self._errors(rec), [])

    def test_v3_rejects_open_or_legacy_renderer_fields(self):
        rec = _valid_v3_record()
        rec.update({
            "changes": [{"dir": "sideways", "text": "x", "source_ids": ["source-market-close"],
                         "evidence_status": "confirmed", "extra": "x"}],
            "drivers": [{"label": "d", "text": "x", "source_ids": [], "evidence_status": "confirmed"}],
            "counterevidence": [{"text": "x", "source_ids": ["missing"], "evidence_status": "confirmed"}],
            "hypotheses": [{"hypothesis_id": "h", "text": "x", "observable": "o", "invalidation": "i",
                              "horizon": "next", "source_ids": "source-market-close", "evidence_status": "confirmed"}],
            "reviews": [{"review_id": "r", "hypothesis_id": "h", "verdict": "v", "evidence": "e",
                         "reason": "r", "lesson": "l", "source_ids": ["source-market-close"],
                         "evidence_status": "unknown"}],
            "missing_data": [{"label": "x", "reason": "x", "evidence_status": "partial", "extra": "x"}],
            "quality": [{"label": "x", "value": "y", "extra": "x"}],
            "risks": [{"text": "x"}], "today_learning": ["ok", 1], "theses": [],
        })
        errors = self._errors(rec)
        for field in ("changes[0].dir", "changes[0].extra", "drivers[0].source_ids",
                      "counterevidence[0].source_ids", "hypotheses[0].source_ids",
                      "reviews[0].evidence_status", "missing_data[0].extra", "quality[0].extra",
                      "risks[0]", "today_learning[1]", "theses"):
            self.assertTrue(any(field in message for message in errors))

    def test_v3_privacy_uses_bounded_paths_and_explicit_keys(self):
        rec = _valid_v3_record()
        rec["drivers"] = [{"label": "x", "text": "/home/synthetic/file"}]
        rec["sources"][0]["account_id"] = "public-looking"
        errors = self._errors(rec)
        self.assertGreaterEqual(sum("비공개" in message for message in errors), 2)

    def test_v3_metadata_wrong_types_return_errors_without_crashing(self):
        rec = _valid_v3_record()
        rec.update({
            "brief_id": {}, "market_code": [], "window_code": True, "market_session_date": {},
            "generated_at_utc": [], "cutoff_at_utc": {}, "market_timezone": [], "status": {},
            "evidence_status": [], "methodology_version": True, "public_receipt_sha256": {},
            "out_path": [], "title": {}, "date": [], "correction_note": {}, "corrected_at": [],
            "supersedes": {}, "summary": [], "next_handoff": {},
        })
        errors = self._errors(rec)
        for field in ("brief_id", "market_code", "window_code", "market_session_date", "generated_at_utc",
                      "cutoff_at_utc", "market_timezone", "status", "evidence_status", "methodology_version",
                      "public_receipt_sha256", "out_path", "title", "date", "correction_note", "corrected_at",
                      "supersedes", "summary", "next_handoff"):
            self.assertTrue(any(field in message for message in errors))

    def test_v3_schema_version_must_be_exact_int_three(self):
        for version in (True, 3.0):
            rec = _valid_v3_record()
            rec["schema_version"] = version
            self.assertTrue(any("schema_version" in message for message in self._errors(rec)))

    def test_v3_zero_metric_and_optional_omission_are_strict_clean(self):
        rec = _valid_v3_record()
        metric = rec["metrics"][0]
        metric["value"] = 0
        for key in ("tone", "note", "name"):
            metric.pop(key, None)
        findings = verify_record(rec)
        self.assertEqual([f for f in findings if f.severity == Severity.ERROR], [])
        self.assertEqual([f for f in findings if f.severity == Severity.WARNING], [])
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(rec, f)
            f.flush()
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--strict", f.name]), 0)

    def test_confirmed_v3_requires_sources_and_linked_public_evidence(self):
        empty = _valid_v3_record()
        empty.update({"summary": "근거 없는 요약", "sources": [], "metrics": [], "claims": []})
        source_only = _valid_v3_record()
        source_only.update({"summary": "연결 없는 요약", "metrics": [], "claims": []})
        for rec, token in ((empty, "sources"), (source_only, "source_ids")):
            self.assertTrue(any(token in message for message in self._errors(rec)))

    def test_not_proven_v3_allows_empty_evidence(self):
        rec = _valid_v3_record()
        rec.update({"evidence_status": "not_proven", "sources": [], "metrics": [], "claims": []})
        self.assertEqual(self._errors(rec), [])

    def test_confirmed_v3_requires_confirmed_source_and_confirmed_item(self):
        rec = _valid_v3_record()
        rec["sources"][0]["status"] = "not_proven"
        rec["metrics"][0]["evidence_status"] = "partial"
        rec["claims"][0]["evidence_status"] = "partial"
        self.assertTrue(any("confirmed" in message for message in self._errors(rec)))


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

    def test_legacy_unhashable_enums_and_tone_are_errors_not_exceptions(self):
        rec = _valid_record()
        rec["market_code"] = ["KR"]
        rec["window_code"] = {"close": True}
        rec["status"] = ["live"]
        rec["metrics"] = [{"name": "X", "value": "1", "tone": {"flat": True}}]
        errors = [f.message for f in verify_record(rec) if f.severity == Severity.ERROR]
        for field in ("market_code", "window_code", "status", "tone"):
            self.assertTrue(any(field in message for message in errors))


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

    def test_named_holding_in_v1_record_is_error(self):
        """schema_version=1 이어도 실명은 잡아야 한다.

        2026-08-16 발견: 이전 구현은 `schema_version < 2` 면 검사를 통째로
        건너뛰었다. 실측 65 레코드 중 47건이 v1 이라 그 경로가 전량 무검사였고,
        v1 형식으로 실명이 들어오면 `0 ERROR` 초록불이 뜨면서 통과했을 상태다.
        """
        rec = _valid_record()
        rec["schema_version"] = 1
        rec["theses"] = [{"name": "테스트보유A", "signal": "높음", "body": "본문"}]
        findings = verify_record(rec, _TEST_HOLDINGS)
        self.assertTrue(
            any(f.severity == Severity.WARNING and "논지" in f.message for f in findings),
            "v1 레코드의 실명이 검출되지 않았다 — 버전 게이트가 되살아났다",
        )
        self.assertFalse(
            any(f.severity == Severity.ERROR and "논지" in f.message for f in findings),
            "v1 은 소급 거부하지 않는다 — ERROR 가 아니라 WARNING 이어야 한다",
        )

    def test_named_holding_in_v1_risks_is_error(self):
        """v1 의 risks 필드도 같은 계약을 받는다."""
        rec = _valid_record()
        rec["schema_version"] = 1
        rec["risks"] = ["테스트보유B 익스포저 점검"]
        findings = verify_record(rec, _TEST_HOLDINGS)
        self.assertTrue(
            any(f.severity == Severity.WARNING and "risks[0]" in f.message for f in findings),
            "v1 risks 의 실명이 검출되지 않았다",
        )

    def test_clean_v1_record_still_passes(self):
        """v1 이어도 실명이 없으면 통과한다 — 레거시 아카이브를 깨지 않는다."""
        rec = _valid_record()
        rec["schema_version"] = 1
        rec["theses"] = [{"name": "위험선호", "signal": "회복", "body": "본문"}]
        findings = verify_record(rec, _TEST_HOLDINGS)
        holdings_errors = [f for f in findings if "논지" in f.message]
        self.assertEqual(holdings_errors, [])

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
