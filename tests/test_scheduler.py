from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from journal.config import Paths
from journal.scheduler import _strip_cron_block, build_refresh_command, load_refresh_state, schedule_runner, write_refresh_state


class SchedulerTests(unittest.TestCase):
    def test_schedule_runner_auto_prefers_platform_default(self) -> None:
        with patch("journal.scheduler.platform.system", return_value="Darwin"):
            self.assertEqual(schedule_runner("auto"), "launchd")
        with patch("journal.scheduler.platform.system", return_value="Linux"):
            self.assertEqual(schedule_runner("auto"), "cron")

    def test_build_refresh_command_includes_expected_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "eng-journal"
            paths = Paths(
                repo_root=root,
                cache_dir=root / ".cache",
                reports_dir=root / "reports",
                checkpoints_dir=root / "checkpoints",
                references_dir=root / "references",
                claude_dir=root / ".claude",
                codex_dir=root / ".codex",
                cc_config_dir=None,
                gh_audit_dir=root / "gh-audit",
            )
            command = build_refresh_command(
                paths,
                scan_gh_audit=True,
                user="alice",
                workdir=Path("/tmp/work"),
                output_dir=Path("/tmp/output"),
                start_date="2026-01-01",
                end_date="2026-03-31",
            )
            self.assertIn("refresh", command)
            self.assertIn("--scan-gh-audit", command)
            self.assertIn("--user alice", command)
            self.assertIn("--workdir /tmp/work", command)
            self.assertIn("--output-dir /tmp/output", command)
            self.assertIn("--start 2026-01-01", command)
            self.assertIn("--end 2026-03-31", command)

    def test_strip_cron_block_removes_existing_managed_entries(self) -> None:
        content = "\n".join(
            [
                "MAILTO=\"\"",
                "# >>> eng-journal refresh >>>",
                "17 3 * * * /tmp/refresh",
                "# <<< eng-journal refresh <<<",
                "0 12 * * * /tmp/keep",
            ]
        )
        self.assertEqual(_strip_cron_block(content), "MAILTO=\"\"\n0 12 * * * /tmp/keep")

    def test_refresh_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = Paths(
                repo_root=root / "eng-journal",
                cache_dir=root / ".cache",
                reports_dir=root / "reports",
                checkpoints_dir=root / "checkpoints",
                references_dir=root / "references",
                claude_dir=root / ".claude",
                codex_dir=root / ".codex",
                cc_config_dir=None,
                gh_audit_dir=root / "gh-audit",
            )
            write_refresh_state(paths, {"status": "ok", "completed_at": "2026-03-31T22:00:00+00:00"})
            payload = load_refresh_state(paths)
            assert payload is not None
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["completed_at"], "2026-03-31T22:00:00+00:00")
            self.assertIn("updated_at", payload)


if __name__ == "__main__":
    unittest.main()
