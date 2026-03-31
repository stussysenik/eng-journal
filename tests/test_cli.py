from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from journal.cli import _resolve_window
from journal.config import Paths


class CliWindowTests(unittest.TestCase):
    def test_resolve_window_prefers_latest_verified_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            checkpoints_dir = root / "checkpoints"
            (checkpoints_dir / "2026-01-01_to_2026-03-31").mkdir(parents=True)
            (checkpoints_dir / "2025-10-01_to_2026-03-31").mkdir(parents=True)

            (checkpoints_dir / "2026-01-01_to_2026-03-31" / "manifest.json").write_text(
                json.dumps(
                    {
                        "verified_at": "2026-03-31T19:15:55.176822+00:00",
                        "window": {"start_date": "2026-01-01", "end_date": "2026-03-31"},
                    }
                ),
                encoding="utf-8",
            )
            (checkpoints_dir / "2025-10-01_to_2026-03-31" / "manifest.json").write_text(
                json.dumps(
                    {
                        "verified_at": "2026-03-31T19:17:56.169803+00:00",
                        "window": {"start_date": "2025-10-01", "end_date": "2026-03-31"},
                    }
                ),
                encoding="utf-8",
            )

            paths = Paths(
                repo_root=root,
                cache_dir=root / ".cache",
                local_reports_dir=root / ".cache" / "reports",
                local_checkpoints_dir=root / ".cache" / "checkpoints",
                reports_dir=root / "reports",
                checkpoints_dir=checkpoints_dir,
                references_dir=root / "references",
                claude_dir=root / ".claude",
                codex_dir=root / ".codex",
                cc_config_dir=root / "cc-config",
                gh_audit_dir=root / "gh-audit",
            )
            self.assertEqual(_resolve_window(paths, None, None), ("2025-10-01", "2026-03-31"))


if __name__ == "__main__":
    unittest.main()
