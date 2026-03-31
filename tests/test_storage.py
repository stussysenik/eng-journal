from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from journal.checkpoints import load_checkpoint_dataset
from journal.config import Paths
from journal.storage import prune_storage, storage_status


class StorageTests(unittest.TestCase):
    def _paths(self, root: Path) -> Paths:
        return Paths(
            repo_root=root,
            cache_dir=root / ".cache",
            local_reports_dir=root / ".cache" / "reports",
            local_checkpoints_dir=root / ".cache" / "checkpoints",
            reports_dir=root / "reports",
            checkpoints_dir=root / "checkpoints",
            references_dir=root / "references",
            claude_dir=root / ".claude",
            codex_dir=root / ".codex",
            cc_config_dir=None,
            gh_audit_dir=root / "gh-audit",
        )

    def test_storage_status_marks_latest_window_for_keep(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self._paths(root)
            for directory in (paths.reports_dir, paths.checkpoints_dir, paths.local_reports_dir, paths.local_checkpoints_dir):
                directory.mkdir(parents=True, exist_ok=True)
            (paths.reports_dir / "review-2026-01-01_to_2026-03-31.md").write_text("latest", encoding="utf-8")
            (paths.reports_dir / "review-2026-02-12_to_2026-03-31.md").write_text("older", encoding="utf-8")
            for slug, verified_at in (
                ("2026-01-01_to_2026-03-31", "2026-03-31T22:44:48+00:00"),
                ("2026-02-12_to_2026-03-31", "2026-03-31T20:10:00+00:00"),
            ):
                checkpoint_dir = paths.checkpoints_dir / slug
                checkpoint_dir.mkdir(parents=True, exist_ok=True)
                (checkpoint_dir / "manifest.json").write_text(
                    json.dumps({"verified_at": verified_at, "window": {}}),
                    encoding="utf-8",
                )

            payload = storage_status(paths, keep_windows=1)
            windows = payload["windows"]
            assert isinstance(windows, list)
            self.assertEqual(windows[0]["slug"], "2026-01-01_to_2026-03-31")
            self.assertTrue(windows[0]["keep"])
            self.assertFalse(windows[1]["keep"])

    def test_prune_storage_keeps_latest_window_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self._paths(root)
            for directory in (paths.reports_dir, paths.checkpoints_dir, paths.local_reports_dir, paths.local_checkpoints_dir, paths.cache_dir):
                directory.mkdir(parents=True, exist_ok=True)
            old_slug = "2026-01-01_to_2026-03-31"
            new_slug = "2026-02-12_to_2026-03-31"
            (paths.reports_dir / f"review-{old_slug}.md").write_text("old", encoding="utf-8")
            (paths.reports_dir / f"review-{new_slug}.md").write_text("new", encoding="utf-8")
            (paths.checkpoints_dir / old_slug).mkdir(parents=True, exist_ok=True)
            (paths.checkpoints_dir / new_slug).mkdir(parents=True, exist_ok=True)
            (paths.checkpoints_dir / old_slug / "manifest.json").write_text("{}", encoding="utf-8")
            (paths.checkpoints_dir / new_slug / "manifest.json").write_text("{}", encoding="utf-8")
            (paths.local_checkpoints_dir / old_slug).mkdir(parents=True, exist_ok=True)
            (paths.local_checkpoints_dir / new_slug).mkdir(parents=True, exist_ok=True)
            (paths.local_checkpoints_dir / old_slug / "dataset.json").write_text("{}", encoding="utf-8")
            (paths.local_checkpoints_dir / new_slug / "dataset.json").write_text("{}", encoding="utf-8")
            (paths.local_reports_dir / f"stats-{old_slug}.json").write_text("{}", encoding="utf-8")
            (paths.local_reports_dir / f"stats-{new_slug}.json").write_text("{}", encoding="utf-8")
            (paths.cache_dir / f"{old_slug}.json").write_text("{}", encoding="utf-8")
            (paths.cache_dir / f"{new_slug}.json").write_text("{}", encoding="utf-8")

            prune_storage(paths, keep_windows=1)

            self.assertFalse((paths.reports_dir / f"review-{old_slug}.md").exists())
            self.assertFalse((paths.checkpoints_dir / old_slug).exists())
            self.assertFalse((paths.local_checkpoints_dir / old_slug).exists())
            self.assertFalse((paths.local_reports_dir / f"stats-{old_slug}.json").exists())
            self.assertFalse((paths.cache_dir / f"{old_slug}.json").exists())
            self.assertTrue((paths.reports_dir / f"review-{new_slug}.md").exists())
            self.assertTrue((paths.checkpoints_dir / new_slug).exists())
            self.assertTrue((paths.local_checkpoints_dir / new_slug).exists())

    def test_load_checkpoint_dataset_falls_back_to_legacy_repo_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            paths = self._paths(root)
            slug = "2026-01-01_to_2026-03-31"
            legacy_dir = paths.checkpoints_dir / slug
            legacy_dir.mkdir(parents=True, exist_ok=True)
            (legacy_dir / "dataset.json").write_text('{"agents": {}}', encoding="utf-8")

            payload = load_checkpoint_dataset(paths, "2026-01-01", "2026-03-31")
            assert payload is not None
            self.assertEqual(payload["agents"], {})


if __name__ == "__main__":
    unittest.main()
