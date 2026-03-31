from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from journal.config import Paths, discover_sources
from journal.util import utc_dt_from_unixish


class ConfigDiscoveryTests(unittest.TestCase):
    def test_discover_sources_picks_latest_sqlite_and_optional_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            claude_dir = root / ".claude"
            codex_dir = root / ".codex"
            cc_config_dir = root / "cc-config"
            (claude_dir / "projects").mkdir(parents=True)
            codex_dir.mkdir(parents=True)
            (cc_config_dir / "logs").mkdir(parents=True)

            (claude_dir / "history.jsonl").write_text("", encoding="utf-8")
            (codex_dir / "history.jsonl").write_text("", encoding="utf-8")
            (codex_dir / "state_4.sqlite").write_text("", encoding="utf-8")
            (codex_dir / "state_7.sqlite").write_text("", encoding="utf-8")
            (codex_dir / "logs_1.sqlite").write_text("", encoding="utf-8")
            (cc_config_dir / "logs" / ".stats.json").write_text("{}", encoding="utf-8")

            paths = Paths(
                repo_root=root,
                cache_dir=root / ".cache",
                reports_dir=root / "reports",
                checkpoints_dir=root / "checkpoints",
                references_dir=root / "references",
                claude_dir=claude_dir,
                codex_dir=codex_dir,
                cc_config_dir=cc_config_dir,
                gh_audit_dir=root / "gh-audit",
            )
            sources = discover_sources(paths)
            self.assertEqual(sources.codex_state_db.name, "state_7.sqlite")
            self.assertEqual(sources.codex_logs_db.name, "logs_1.sqlite")
            self.assertIsNotNone(sources.claude_projects_dir)
            self.assertIsNotNone(sources.cc_config_logs_dir)
            self.assertIsNotNone(sources.cc_config_stats_file)

    def test_unixish_timestamp_supports_seconds_and_milliseconds(self) -> None:
        millis = utc_dt_from_unixish(1759318846066)
        seconds = utc_dt_from_unixish(1759318846)
        self.assertIsNotNone(millis)
        self.assertIsNotNone(seconds)
        self.assertEqual(millis.year, seconds.year)
        self.assertEqual(millis.month, seconds.month)
        self.assertEqual(millis.day, seconds.day)


if __name__ == "__main__":
    unittest.main()
