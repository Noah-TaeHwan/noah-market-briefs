#!/usr/bin/env python3
"""publish_brief.sh 회귀 — dry-run·파일명·verify 실패·stage 허용 경로만."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "publish_brief.sh"
PRODUCT_KR_PRE = REPO / "data" / "2026" / "09" / "07" / "korea-preopen.json"


def _source(cmd: str) -> subprocess.CompletedProcess[str]:
    """스크립트를 source 한 뒤 한 줄을 실행한다."""
    return subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}"; {cmd}'],
        capture_output=True,
        text=True,
        check=False,
    )


def _dry_run(*extra: str) -> subprocess.CompletedProcess[str]:
    """--dry-run으로 발행 스크립트를 돌린다."""
    return subprocess.run(
        [str(SCRIPT), "--dry-run", *extra],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(REPO),
    )


class PublishBriefTests(unittest.TestCase):
    """파일명·dry-run·verify 실패."""

    def test_canonical_kr_close(self) -> None:
        """KR close 정본 파일명은 korea-close.json 이다."""
        out = _source("canonical_basename KR close")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "korea-close.json")

    def test_canonical_us_preopen(self) -> None:
        """US preopen 정본 파일명은 us-preopen.json 이다."""
        out = _source("canonical_basename US preopen")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "us-preopen.json")

    def test_allowed_stage_paths(self) -> None:
        """오늘 JSON·생성 HTML·피드만 stage 허용, 파이프라인 파일은 거부."""
        ok = _source('allowed_stage_path data/2026/09/06/korea-close.json && echo yes')
        self.assertEqual(ok.stdout.strip(), "yes")
        html = _source('allowed_stage_path 2026/09/06/korea-close.html && echo yes')
        self.assertEqual(html.stdout.strip(), "yes")
        neighbor = _source('allowed_stage_path 2026/09/07/korea-preopen.html && echo yes')
        self.assertEqual(neighbor.stdout.strip(), "yes")
        bad = _source('if allowed_stage_path scripts/publish_brief.sh; then echo yes; else echo no; fi')
        self.assertEqual(bad.stdout.strip(), "no")
        forbid = _source('forbidden_staged scripts/foo.py && echo deny')
        self.assertEqual(forbid.stdout.strip(), "deny")

    def test_resolve_dest_renames_close_json(self) -> None:
        """close.json 후보는 data/YYYY/MM/DD/korea-close.json 으로 간다."""
        with tempfile.TemporaryDirectory() as raw:
            src = Path(raw) / "close.json"
            src.write_text(
                '{"market_code":"KR","window_code":"close","market_session_date":"2026-09-06"}\n',
                encoding="utf-8",
            )
            out = _source(f'resolve_dest "{src}"')
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), "data/2026/09/06/korea-close.json")

    def test_dry_run_verify_fail_stops(self) -> None:
        """검증 실패 후보는 dry-run에서도 발행 계획을 진행하지 않는다."""
        with tempfile.TemporaryDirectory() as raw:
            bad = Path(raw) / "close.json"
            bad.write_text("{}\n", encoding="utf-8")
            r = _dry_run("--calendar", "closed", "--now", "2026-09-06T07:00:00Z", str(bad))
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("gh pr merge", r.stdout)

    def test_dry_run_valid_candidate_skips_git(self) -> None:
        """유효 후보는 dry-run에서 verify만 하고 git/gh를 부르지 않는다."""
        if not PRODUCT_KR_PRE.is_file():
            self.skipTest("후보 JSON 없음")
        before = {p.name for p in (REPO / "data" / "2026" / "09" / "06").glob("*")} if (REPO / "data" / "2026" / "09" / "06").exists() else set()
        r = _dry_run("--calendar", "open", "--now", "2026-09-07T00:30:00Z", str(PRODUCT_KR_PRE))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("DRY-RUN", r.stdout)
        self.assertIn("PLAN", r.stdout)
        after_dir = REPO / "data" / "2026" / "09" / "06"
        after = {p.name for p in after_dir.glob("*")} if after_dir.exists() else set()
        self.assertEqual(before, after)
        self.assertNotIn("git push", r.stdout)
        self.assertNotIn("gh pr create", r.stdout)


if __name__ == "__main__":
    unittest.main()
