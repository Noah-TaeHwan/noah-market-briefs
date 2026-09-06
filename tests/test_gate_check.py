#!/usr/bin/env python3
"""gate_check.py 회귀 테스트 (표준 unittest, 의존성 0).

자동 발행 게이트 G1~G9의 판정을 잠근다. S0 단계이므로 판정만 테스트하고,
실제 발행 동작은 없다.

실행: python3 -m unittest discover -s tests
"""
import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from gate_check import (  # noqa: E402
    evaluate,
    g2_time,
    g3_full,
    g4_advice,
    g5_privacy,
    g6_rights,
    g8_idempotency,
    g9_calendar,
    scan_secret_text,
)

NOW = datetime(2026, 9, 7, 0, 30, tzinfo=timezone.utc)


def _slot_metric(metric_id: str, label: str) -> dict:
    """세션 슬롯용 confirmed 메트릭."""
    return {
        "metric_id": metric_id, "label": label, "value": "1", "unit": "x",
        "delta": "0", "as_of": "2026-09-06T06:00:00Z",
        "source_ids": ["source-official"], "evidence_status": "confirmed",
    }


def _passing_record() -> dict:
    """전 게이트 통과용 V3 픽스처 (KR preopen, published+confirmed)."""
    return {
        "schema_version": 3,
        "brief_id": "brief-kr-2026-09-07-preopen",
        "market_code": "KR",
        "window_code": "preopen",
        "market_session_date": "2026-09-07",
        "generated_at_utc": "2026-09-07T00:00:00Z",
        "cutoff_at_utc": "2026-09-06T23:00:00Z",
        "market_timezone": "Asia/Seoul",
        "status": "published",
        "evidence_status": "confirmed",
        "methodology_version": "public-brief-v3",
        "public_receipt_sha256": "b" * 64,
        "out_path": "2026/09/07/korea-preopen.html",
        "title": "한국 장전 브리프 — 2026-09-07",
        "summary": "장 시작 전 공개 수치 정리",
        "sources": [{
            "source_id": "source-official",
            "publisher": "U.S. Bureau of Labor Statistics",
            "title": "Official release",
            "url": "https://www.bls.gov/news.release/example.htm",
            "as_of": "2026-09-06T06:00:00Z",
            "retrieved_at": "2026-09-06T23:30:00Z",
            "source_type": "economic_release",
            "status": "confirmed",
        }],
        "metrics": [
            _slot_metric("metric-session-equity", "코스피"),
            _slot_metric("metric-session-fx", "USD/KRW"),
            _slot_metric("metric-session-vol", "VKOSPI"),
        ],
        "claims": [{
            "claim_id": "claim-1", "kind": "fact", "text": "공개 수치 관측",
            "as_of": "2026-09-06T06:00:00Z", "source_ids": ["source-official"],
            "evidence_status": "confirmed",
        }],
        "quality": [
            {"label": "BLS 공개 고지",
             "value": "BLS.gov cannot vouch for the data after retrieval."},
        ],
    }


class TestGateAllPass(unittest.TestCase):
    """통과 픽스처는 G1~G4·G6·G9를 통과한다 (G5·G7·G8은 repo 필요로 분리 테스트)."""

    def test_passing_record(self):
        rec = _passing_record()
        from gate_check import g1_contract
        self.assertTrue(g1_contract(rec)[0], g1_contract(rec)[1])
        self.assertTrue(g2_time(rec, NOW)[0])
        self.assertTrue(g3_full(rec)[0])
        self.assertTrue(g4_advice(rec)[0])
        self.assertTrue(g6_rights(rec)[0])
        self.assertTrue(g9_calendar("open")[0])


class TestGateG1(unittest.TestCase):
    """G1 verifier strict 상당."""

    def test_broken_schema_fails(self):
        from gate_check import g1_contract
        rec = _passing_record()
        del rec["brief_id"]
        ok, _ = g1_contract(rec)
        self.assertFalse(ok)


class TestGateG2(unittest.TestCase):
    """G2 시각 계약."""

    def test_cutoff_after_generated_fails(self):
        rec = _passing_record()
        rec["cutoff_at_utc"] = "2026-09-07T01:00:00Z"
        ok, reason = g2_time(rec, NOW)
        self.assertFalse(ok)
        self.assertIn("cutoff", reason)

    def test_future_generated_fails(self):
        rec = _passing_record()
        rec["generated_at_utc"] = "2026-09-08T00:00:00Z"
        rec["cutoff_at_utc"] = "2026-09-07T23:00:00Z"
        ok, _ = g2_time(rec, NOW)
        self.assertFalse(ok)

    def test_stale_lag_fails(self):
        rec = _passing_record()
        ok, _ = g2_time(rec, NOW, max_lag_hours=0.5)
        self.assertFalse(ok)

    def test_retrieved_after_generated_fails(self):
        rec = _passing_record()
        rec["sources"][0]["retrieved_at"] = "2026-09-07T01:00:00Z"
        ok, _ = g2_time(rec, NOW)
        self.assertFalse(ok)


class TestGateG3(unittest.TestCase):
    """G3 전체 confirmed 정책."""

    def test_partial_status_fails(self):
        rec = _passing_record()
        rec["status"] = "partial"
        ok, reason = g3_full(rec)
        self.assertFalse(ok)
        self.assertIn("published", reason)

    def test_missing_slot_fails(self):
        rec = _passing_record()
        rec["metrics"] = [m for m in rec["metrics"]
                          if m["metric_id"] != "metric-session-vol"]
        ok, reason = g3_full(rec)
        self.assertFalse(ok)
        self.assertIn("metric-session-vol", reason)

    def test_unconfirmed_item_fails(self):
        rec = _passing_record()
        rec["claims"][0]["evidence_status"] = "partial"
        ok, _ = g3_full(rec)
        self.assertFalse(ok)


class TestGateG4(unittest.TestCase):
    """G4 투자조언 금지구문."""

    def test_price_target_fails(self):
        rec = _passing_record()
        rec["claims"][0]["text"] = "목표가 100,000원 제시"
        ok, reason = g4_advice(rec)
        self.assertFalse(ok)
        self.assertIn("목표가", reason)

    def test_net_selling_allowed(self):
        rec = _passing_record()
        rec["claims"][0]["text"] = "외국인 순매도 지속, 매수세 유입"
        ok, reason = g4_advice(rec)
        self.assertTrue(ok, reason)

    def test_bare_buy_fails(self):
        rec = _passing_record()
        rec["claims"][0]["text"] = "지금 매수 관점"
        ok, _ = g4_advice(rec)
        self.assertFalse(ok)


class TestGateG5(unittest.TestCase):
    """G5 유출 패턴 (repo 스캔은 분리, 순수 함수와 페이로드 기준으로 테스트)."""

    def test_secret_pattern_detected(self):
        # 리터럴 매치 문자열을 파일에 두면 G5 git grep이 자기 자신을 적발하므로 동적 조립한다.
        token = "ghp_" + "abcdefghijklmnopqrst"
        self.assertIsNotNone(scan_secret_text(f"key = '{token}'"))
        self.assertIsNone(scan_secret_text("공개 수치 7,656.31"))

    def test_payload_secret_fails(self):
        rec = _passing_record()
        rec["summary"] = "key = '" + "ghp_" + "abcdefghijklmnopqrst" + "'"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            (root / "data" / ".named-holdings.local").write_text("x", encoding="utf-8")
            ok, reason = g5_privacy(rec, root)
            self.assertFalse(ok)
            self.assertIn("ghp_", reason)
            self.assertNotIn("abcdefghijklmnopqrst", reason)

    def test_private_path_in_payload_fails(self):
        rec = _passing_record()
        rec["summary"] = "참고 /Users/noah/notes"
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            ok, _ = g5_privacy(rec, Path(d))
            self.assertFalse(ok)

    def test_missing_holdings_file_fails_closed(self):
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "data").mkdir()
            ok, reason = g5_privacy(rec, Path(d))
            self.assertFalse(ok)
            self.assertIn("named-holdings", reason)


class TestGateG6(unittest.TestCase):
    """G6 출처 권리."""

    def test_non_allowlist_domain_fails(self):
        rec = _passing_record()
        rec["sources"][0]["url"] = "https://example.test/data"
        ok, _ = g6_rights(rec)
        self.assertFalse(ok)

    def test_fred_confirmed_fails(self):
        rec = _passing_record()
        rec["sources"][0]["url"] = "https://fred.stlouisfed.org/series/DEXKOUS"
        ok, reason = g6_rights(rec)
        self.assertFalse(ok)
        self.assertIn("FRED", reason)

    def test_aggregator_confirmed_fails(self):
        rec = _passing_record()
        rec["sources"][0]["publisher"] = "yfinance snapshot"
        ok, _ = g6_rights(rec)
        self.assertFalse(ok)

    def test_bls_without_notice_fails(self):
        rec = _passing_record()
        rec["quality"] = []
        ok, _ = g6_rights(rec)
        self.assertFalse(ok)


class TestGateG6FirstSeen(unittest.TestCase):
    """G6-2 첫등장 출처."""

    def _seed(self, root: Path, publisher: str, url: str) -> None:
        other = _passing_record()
        other["sources"] = [{
            "source_id": "s-old", "publisher": publisher, "title": "t",
            "url": url, "as_of": "2026-09-06T06:00:00Z",
            "retrieved_at": "2026-09-06T23:30:00Z",
            "source_type": "economic_release", "status": "confirmed",
        }]
        (root / "data" / "old.json").write_text(json.dumps(other), encoding="utf-8")

    def test_known_source_passes(self):
        from gate_check import g6_first_seen
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            self._seed(root, "U.S. Bureau of Labor Statistics",
                       "https://www.bls.gov/news.release/example.htm")
            mine = root / "data" / "mine.json"
            mine.write_text(json.dumps(rec), encoding="utf-8")
            ok, reason = g6_first_seen(rec, root / "data", mine)
            self.assertTrue(ok, reason)

    def test_unknown_source_fails(self):
        from gate_check import g6_first_seen
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            self._seed(root, "Someone Else", "https://example.test/x")
            mine = root / "data" / "mine.json"
            mine.write_text(json.dumps(rec), encoding="utf-8")
            ok, reason = g6_first_seen(rec, root / "data", mine)
            self.assertFalse(ok)
            self.assertIn("첫등장", reason)


class TestGateG7(unittest.TestCase):
    """G7 diff 범위 (git 필요, 없으면 skip)."""

    def test_scope_pass_and_fail(self):
        import shutil
        import subprocess
        if shutil.which("git") is None:
            self.skipTest("git 없음")
        from gate_check import g7_scope
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
            cand = root / "data" / "c.json"
            cand.parent.mkdir()
            cand.write_text("{}", encoding="utf-8")
            subprocess.run(["git", "add", "-A"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
            ok, reason = g7_scope(root, cand, rec)
            self.assertTrue(ok, reason)
            # untracked는 --untracked-files=no로 안 보임이 정상(CI diff와 동일 의미).
            # 범위 밖 tracked 변경이 FAIL 사유다.
            (root / "stray.txt").write_text("x", encoding="utf-8")
            subprocess.run(["git", "add", "stray.txt"], cwd=root, check=True)
            ok, reason = g7_scope(root, cand, rec)
            self.assertFalse(ok)
            self.assertIn("stray.txt", reason)


class TestGateG8G9(unittest.TestCase):
    """G8 멱등성, G9 캘린더."""

    def test_duplicate_brief_id_fails(self):
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            other = copy.deepcopy(rec)
            other["brief_id"] = rec["brief_id"]
            other["out_path"] = "2026/09/07/other.html"
            (root / "data" / "other.json").write_text(
                json.dumps(other), encoding="utf-8")
            mine = root / "data" / "mine.json"
            mine.write_text(json.dumps(rec), encoding="utf-8")
            ok, reason = g8_idempotency(rec, root / "data", mine)
            self.assertFalse(ok)
            self.assertIn("brief_id", reason)

    def test_no_duplicate_passes(self):
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            mine = root / "data" / "mine.json"
            mine.write_text(json.dumps(rec), encoding="utf-8")
            ok, reason = g8_idempotency(rec, root / "data", mine)
            self.assertTrue(ok, reason)

    def test_calendar_closed_fails(self):
        self.assertFalse(g9_calendar("closed")[0])
        self.assertFalse(g9_calendar("unknown")[0])


class TestEvaluateShape(unittest.TestCase):
    """evaluate()는 G1~G9 전 키를 반환한다."""

    def test_all_gate_keys_present(self):
        rec = _passing_record()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data").mkdir()
            (root / "data" / ".named-holdings.local").write_text("x", encoding="utf-8")
            mine = root / "data" / "mine.json"
            mine.write_text(json.dumps(rec), encoding="utf-8")
            results = evaluate(rec, now=NOW, calendar="open", repo=root,
                               candidate=mine)
        self.assertEqual(sorted(results), ["G1", "G2", "G3", "G4", "G5",
                                           "G6", "G7", "G8", "G9"])


if __name__ == "__main__":
    unittest.main()
