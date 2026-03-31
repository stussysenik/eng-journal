from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from journal.config import Paths
from journal.gh_audit import normalize_gh_audit_report, run_gh_audit_scan


class GHAuditTests(unittest.TestCase):
    def test_normalize_gh_audit_report_computes_reference_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "gh-audit-report-test.json"
            source.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-03-31_000000",
                        "total_repos": 1,
                        "total_findings": 0,
                        "total_portfolio_value_usd": 96000.0,
                        "raw_total_portfolio_value_usd": 120000.0,
                        "average_confidence_score": 0.82,
                        "safe_count": 1,
                        "needs_fixes_count": 0,
                        "too_sensitive_count": 0,
                        "nda_count": 0,
                        "critical_count": 0,
                        "repos": [
                            {
                                "name": "demo-repo",
                                "classification": "SAFE",
                                "language": "Julia",
                                "deep_scanned": True,
                                "findings": [],
                                "nda_score": 0,
                                "nda_reasons": ["No NDA signals detected"],
                                "loc": 3200,
                                "disk_kb": 100,
                                "valuation": {
                                    "kloc": 3.2,
                                    "estimated_value_usd": 96000.0,
                                    "raw_estimated_value_usd": 120000.0,
                                    "adjustment_factor": 0.8,
                                    "cocomo_cost_usd": 150000.0,
                                    "cocomo_effort_pm": 5.0,
                                    "market_score": 60.0,
                                    "portfolio_score": 35.0,
                                    "leverage_score": 30000.0,
                                    "leverage_rank": "Gold",
                                    "confidence_score": 0.82,
                                    "confidence_label": "medium",
                                    "loc_source": "disk_estimate",
                                    "warning_flags": ["disk_loc_estimate"],
                                },
                                "perspectives": {
                                    "staff_engineer": 40,
                                    "design_engineer": 30,
                                    "ai_ml_researcher": 20,
                                    "staff_eng_notes": "solid",
                                    "design_eng_notes": "clear",
                                    "ai_ml_notes": "interesting",
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            normalized = normalize_gh_audit_report(source)
            self.assertEqual(normalized["portfolio"]["total_repos"], 1)
            self.assertEqual(normalized["portfolio"]["deep_scanned_count"], 1)
            self.assertEqual(normalized["portfolio"]["raw_total_portfolio_value_usd"], 120000.0)
            self.assertEqual(normalized["repos"][0]["name"], "demo-repo")
            self.assertEqual(normalized["repos"][0]["leverage_rank"], "Gold")
            self.assertAlmostEqual(normalized["repos"][0]["leverage_usd_per_kloc"], 30000.0)
            self.assertEqual(normalized["repos"][0]["confidence_label"], "medium")

    def test_run_gh_audit_scan_returns_new_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            gh_audit_dir = root / "gh-audit"
            gh_audit_dir.mkdir()
            workdir = root / "work"
            output_dir = root / "output"
            paths = Paths(
                repo_root=root / "eng-journal",
                cache_dir=root / ".cache",
                local_reports_dir=root / ".cache" / "reports",
                local_checkpoints_dir=root / ".cache" / "checkpoints",
                reports_dir=root / "reports",
                checkpoints_dir=root / "checkpoints",
                references_dir=root / "references",
                claude_dir=root / ".claude",
                codex_dir=root / ".codex",
                cc_config_dir=None,
                gh_audit_dir=gh_audit_dir,
            )

            def fake_run(cmd, cwd, check):
                self.assertEqual(cwd, gh_audit_dir)
                self.assertTrue(check)
                self.assertIn("scan", cmd)
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "gh-audit-report-2026-03-31_999999.json").write_text("{}", encoding="utf-8")
                return None

            with patch("journal.gh_audit.subprocess.run", side_effect=fake_run):
                report_path = run_gh_audit_scan(paths, "stussysenik", workdir=workdir, output_dir=output_dir)

            self.assertEqual(report_path.name, "gh-audit-report-2026-03-31_999999.json")


if __name__ == "__main__":
    unittest.main()
