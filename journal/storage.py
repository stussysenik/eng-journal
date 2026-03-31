from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .checkpoints import checkpoint_root
from .config import Paths


WINDOW_RE = re.compile(r"(?P<start>\d{4}-\d{2}-\d{2})_to_(?P<end>\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class WindowStorage:
    slug: str
    tracked_paths: tuple[Path, ...]
    local_paths: tuple[Path, ...]
    tracked_bytes: int
    local_bytes: int


def _path_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _window_slug(path: Path) -> str | None:
    match = WINDOW_RE.search(path.name)
    if not match:
        return None
    return f"{match.group('start')}_to_{match.group('end')}"


def _window_sort_key(slug: str) -> tuple[str, str]:
    start_date, end_date = slug.split("_to_")
    return (end_date, start_date)


def _verified_at(paths: Paths, slug: str) -> str:
    manifest_path = checkpoint_root(paths, *slug.split("_to_")) / "manifest.json"
    if not manifest_path.exists():
        return ""
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8")).get("verified_at", "")
    except Exception:
        return ""


def _tracked_window_paths(paths: Paths, slug: str) -> list[Path]:
    report_paths = sorted(path for path in paths.reports_dir.glob(f"*{slug}*") if path.is_file())
    screenshot_paths = sorted((paths.repo_root / "assets" / "screenshots").glob(f"*{slug}*")) if (paths.repo_root / "assets" / "screenshots").exists() else []
    checkpoint_dir = checkpoint_root(paths, *slug.split("_to_"))
    checkpoint_paths = sorted(checkpoint_dir.rglob("*")) if checkpoint_dir.exists() else []
    return [*report_paths, *(path for path in screenshot_paths if path.is_file()), *(path for path in checkpoint_paths if path.is_file())]


def _local_window_paths(paths: Paths, slug: str) -> list[Path]:
    local_paths: list[Path] = []
    cache_dataset = paths.cache_dir / f"{slug}.json"
    if cache_dataset.exists():
        local_paths.append(cache_dataset)
    checkpoint_dir = paths.local_checkpoints_dir / slug
    if checkpoint_dir.exists():
        local_paths.extend(path for path in checkpoint_dir.rglob("*") if path.is_file())
    local_report_paths = sorted(path for path in paths.local_reports_dir.glob(f"*{slug}*") if path.is_file())
    local_paths.extend(local_report_paths)
    return local_paths


def collect_window_storage(paths: Paths) -> list[WindowStorage]:
    slugs: set[str] = set()
    scan_roots = [
        paths.reports_dir,
        paths.checkpoints_dir,
        paths.repo_root / "assets" / "screenshots",
        paths.local_reports_dir,
        paths.local_checkpoints_dir,
        paths.cache_dir,
    ]
    for root in scan_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            slug = _window_slug(path)
            if slug:
                slugs.add(slug)
    rows: list[WindowStorage] = []
    for slug in sorted(slugs, key=lambda item: (_verified_at(paths, item), *_window_sort_key(item)), reverse=True):
        tracked_paths = tuple(_tracked_window_paths(paths, slug))
        local_paths = tuple(_local_window_paths(paths, slug))
        rows.append(
            WindowStorage(
                slug=slug,
                tracked_paths=tracked_paths,
                local_paths=local_paths,
                tracked_bytes=sum(_path_size(path) for path in tracked_paths),
                local_bytes=sum(_path_size(path) for path in local_paths),
            )
        )
    return rows


def storage_status(paths: Paths, keep_windows: int = 1) -> dict[str, object]:
    windows = collect_window_storage(paths)
    keep_slugs = {window.slug for window in windows[: max(keep_windows, 0)]}
    tracked_total = _path_size(paths.reports_dir) + _path_size(paths.checkpoints_dir) + _path_size(paths.references_dir)
    local_total = _path_size(paths.cache_dir)
    return {
        "policy": {
            "tracked": [
                "reports/*.md",
                "reports/*.txt",
                "reports/scheduler-status.md",
                "checkpoints/<window>/manifest.json",
                "references/gh-audit/latest.json",
                "LEARNING.md",
            ],
            "local_only": [
                ".cache/<window>.json",
                ".cache/reports/*.json",
                ".cache/checkpoints/<window>/dataset.json",
                "gh-audit-output/*.json",
            ],
        },
        "keep_windows": keep_windows,
        "tracked_total_bytes": tracked_total,
        "local_total_bytes": local_total,
        "windows": [
            {
                "slug": window.slug,
                "tracked_bytes": window.tracked_bytes,
                "local_bytes": window.local_bytes,
                "keep": window.slug in keep_slugs,
            }
            for window in windows
        ],
    }


def prune_storage(paths: Paths, keep_windows: int = 1) -> list[Path]:
    windows = collect_window_storage(paths)
    keep_slugs = {window.slug for window in windows[: max(keep_windows, 0)]}
    removed: list[Path] = []
    for window in windows:
        if window.slug in keep_slugs:
            continue
        checkpoint_dir = checkpoint_root(paths, *window.slug.split("_to_"))
        local_checkpoint_dir = paths.local_checkpoints_dir / window.slug
        local_cache_dataset = paths.cache_dir / f"{window.slug}.json"
        for path in window.tracked_paths:
            if path.exists():
                path.unlink()
                removed.append(path)
        for path in window.local_paths:
            if path.exists():
                path.unlink()
                removed.append(path)
        for directory in (checkpoint_dir, local_checkpoint_dir):
            if directory.exists():
                shutil.rmtree(directory)
                removed.append(directory)
        if local_cache_dataset.exists():
            local_cache_dataset.unlink()
            removed.append(local_cache_dataset)
    return removed
