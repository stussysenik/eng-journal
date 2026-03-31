from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from journal.gh_audit import normalize_gh_audit_report


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
                        "total_portfolio_value_usd": 120000.0,
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
                                    "estimated_value_usd": 120000.0,
                                    "cocomo_cost_usd": 150000.0,
                                    "cocomo_effort_pm": 5.0,
                                    "market_score": 60.0,
                                    "portfolio_score": 35.0,
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
            self.assertEqual(normalized["repos"][0]["name"], "demo-repo")
            self.assertEqual(normalized["repos"][0]["leverage_rank"], "Gold")
            self.assertAlmostEqual(normalized["repos"][0]["leverage_usd_per_kloc"], 37500.0)


if __name__ == "__main__":
    unittest.main()
