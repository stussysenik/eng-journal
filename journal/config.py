from __future__ import annotations

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
    cc_config_dir: Path


def default_paths(repo_root: Path | None = None) -> Paths:
    root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    home = Path.home()
    return Paths(
        repo_root=root,
        cache_dir=root / ".cache",
        reports_dir=root / "reports",
        claude_dir=home / ".claude",
        codex_dir=home / ".codex",
        cc_config_dir=home / "Desktop" / "cc-config",
    )


SUBSCRIPTION_SCENARIOS = (
    Scenario("Seat $20", 20.0),
    Scenario("Seat $100", 100.0),
    Scenario("Seat $200", 200.0),
)

