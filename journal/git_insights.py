from __future__ import annotations

import subprocess
from pathlib import Path


def git_root_for_path(path_value: str) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    target = path if path.is_dir() else path.parent
    if not target.exists():
        return None
    result = subprocess.run(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def commit_count_for_repo(repo_root: str, start_date: str, end_date: str) -> int:
    result = subprocess.run(
        [
            "git",
            "-C",
            repo_root,
            "log",
            "--since",
            f"{start_date}T00:00:00",
            "--until",
            f"{end_date}T23:59:59",
            "--format=%H",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def gather_git_evidence(project_paths: list[str], start_date: str, end_date: str) -> dict:
    roots = {}
    total_commits = 0
    for path_value in sorted(set(project_paths)):
        root = git_root_for_path(path_value)
        if not root or root in roots:
            continue
        commits = commit_count_for_repo(root, start_date, end_date)
        roots[root] = commits
        total_commits += commits
    return {
        "repo_count": len(roots),
        "commit_count": total_commits,
        "repos": [{"repo_root": root, "commit_count": count} for root, count in sorted(roots.items())],
    }

