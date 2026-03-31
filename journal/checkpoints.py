from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .config import Paths, discover_sources
from .util import sha256_text


def period_slug(start_date: str, end_date: str) -> str:
    return f"{start_date}_to_{end_date}"


def checkpoint_root(paths: Paths, start_date: str, end_date: str) -> Path:
    return paths.checkpoints_dir / period_slug(start_date, end_date)


def checkpoint_dataset_path(paths: Paths, start_date: str, end_date: str) -> Path:
    return checkpoint_root(paths, start_date, end_date) / "dataset.json"


def checkpoint_manifest_path(paths: Paths, start_date: str, end_date: str) -> Path:
    return checkpoint_root(paths, start_date, end_date) / "manifest.json"


def load_checkpoint_manifest(paths: Paths, start_date: str, end_date: str) -> dict | None:
    manifest_path = checkpoint_manifest_path(paths, start_date, end_date)
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def load_checkpoint_dataset(paths: Paths, start_date: str, end_date: str) -> dict | None:
    dataset_path = checkpoint_dataset_path(paths, start_date, end_date)
    if not dataset_path.exists():
        return None
    return json.loads(dataset_path.read_text(encoding="utf-8"))


def _path_metadata(path: Path | None, repo_root: Path) -> dict | None:
    if not path or not path.exists():
        return None
    stat = path.stat()
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(repo_root)) if path.is_relative_to(repo_root) else str(path),
        "size_bytes": stat.st_size,
        "modified_at": dt.datetime.fromtimestamp(stat.st_mtime, dt.UTC).isoformat(),
    }


def current_source_snapshot(paths: Paths) -> dict[str, dict | None]:
    sources = discover_sources(paths)
    return {
        "claude_projects": _path_metadata(sources.claude_projects_dir, paths.repo_root),
        "claude_history": _path_metadata(sources.claude_history_file, paths.repo_root),
        "codex_history": _path_metadata(sources.codex_history_file, paths.repo_root),
        "codex_state": _path_metadata(sources.codex_state_db, paths.repo_root),
        "codex_logs": _path_metadata(sources.codex_logs_db, paths.repo_root),
        "cc_config_logs": _path_metadata(sources.cc_config_logs_dir, paths.repo_root),
        "cc_config_stats": _path_metadata(sources.cc_config_stats_file, paths.repo_root),
    }


def _artifact_descriptor(repo_root: Path, path: Path) -> dict:
    content = path.read_text(encoding="utf-8") if path.suffix in {".md", ".txt", ".json"} else ""
    return {
        "path": str(path.relative_to(repo_root)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_text(content) if content else "",
    }


def write_checkpoint(paths: Paths, start_date: str, end_date: str, dataset: dict, artifacts: dict[str, Path]) -> Path:
    root = checkpoint_root(paths, start_date, end_date)
    root.mkdir(parents=True, exist_ok=True)
    dataset_path = checkpoint_dataset_path(paths, start_date, end_date)
    dataset_text = json.dumps(dataset, indent=2)
    dataset_path.write_text(dataset_text, encoding="utf-8")

    manifest = {
        "window": dataset["window"],
        "verified_at": dt.datetime.now(dt.UTC).isoformat(),
        "dataset": {
            "path": str(dataset_path.relative_to(paths.repo_root)),
            "sha256": sha256_text(dataset_text),
            "generated_at": dataset.get("generated_at", ""),
        },
        "sources": current_source_snapshot(paths),
        "artifacts": {name: _artifact_descriptor(paths.repo_root, path) for name, path in artifacts.items()},
    }
    manifest_path = checkpoint_manifest_path(paths, start_date, end_date)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path
