from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Scenario:
    label: str
    monthly_cost: float


@dataclass(frozen=True)
class Paths:
    repo_root: Path
    cache_dir: Path
    reports_dir: Path
    claude_dir: Path
    codex_dir: Path
    cc_config_dir: Path | None


@dataclass(frozen=True)
class SourcePaths:
    claude_projects_dir: Path | None
    claude_history_file: Path | None
    codex_history_file: Path | None
    codex_state_db: Path | None
    codex_logs_db: Path | None
    cc_config_logs_dir: Path | None
    cc_config_stats_file: Path | None


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _first_existing_dir(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    return None


def _discover_cc_config_dir(home: Path, repo_root: Path) -> Path | None:
    explicit = _env_path("ENG_JOURNAL_CC_CONFIG_DIR")
    if explicit and explicit.exists():
        return explicit
    candidates = [
        repo_root.parent / "cc-config",
        Path.cwd() / "cc-config",
        home / "Desktop" / "cc-config",
        home / "Documents" / "cc-config",
        home / "Code" / "cc-config",
        home / "Projects" / "cc-config",
        home / "dev" / "cc-config",
    ]
    return _first_existing_dir(candidates)


def _discover_latest_sqlite(directory: Path, pattern: str) -> Path | None:
    candidates = sorted(directory.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def default_paths(repo_root: Path | None = None) -> Paths:
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    home = Path.home()
    claude_dir = (_env_path("ENG_JOURNAL_CLAUDE_DIR") or (home / ".claude")).resolve()
    codex_dir = (_env_path("ENG_JOURNAL_CODEX_DIR") or (home / ".codex")).resolve()
    return Paths(
        repo_root=root,
        cache_dir=root / ".cache",
        reports_dir=root / "reports",
        claude_dir=claude_dir,
        codex_dir=codex_dir,
        cc_config_dir=_discover_cc_config_dir(home, root),
    )


def discover_sources(paths: Paths) -> SourcePaths:
    cc_logs_dir = None
    cc_stats_file = None
    if paths.cc_config_dir:
        logs_dir = paths.cc_config_dir / "logs"
        if logs_dir.exists():
            cc_logs_dir = logs_dir
            stats_file = logs_dir / ".stats.json"
            if stats_file.exists():
                cc_stats_file = stats_file
    claude_projects_dir = paths.claude_dir / "projects"
    claude_history_file = paths.claude_dir / "history.jsonl"
    codex_history_file = paths.codex_dir / "history.jsonl"
    return SourcePaths(
        claude_projects_dir=claude_projects_dir if claude_projects_dir.exists() else None,
        claude_history_file=claude_history_file if claude_history_file.exists() else None,
        codex_history_file=codex_history_file if codex_history_file.exists() else None,
        codex_state_db=_discover_latest_sqlite(paths.codex_dir, "state_*.sqlite") if paths.codex_dir.exists() else None,
        codex_logs_db=_discover_latest_sqlite(paths.codex_dir, "logs_*.sqlite") if paths.codex_dir.exists() else None,
        cc_config_logs_dir=cc_logs_dir,
        cc_config_stats_file=cc_stats_file,
    )


SUBSCRIPTION_SCENARIOS = (
    Scenario("Seat $20", 20.0),
    Scenario("Seat $100", 100.0),
    Scenario("Seat $200", 200.0),
)
