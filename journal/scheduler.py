from __future__ import annotations

import os
import platform
import shlex
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from .config import Paths


CRON_MARKER_BEGIN = "# >>> eng-journal refresh >>>"
CRON_MARKER_END = "# <<< eng-journal refresh <<<"
WEEKDAY_TO_CRON = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}
WEEKDAY_TO_LAUNCHD = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


def schedule_runner(runner: str | None = None) -> str:
    if runner and runner != "auto":
        return runner
    return "launchd" if platform.system() == "Darwin" else "cron"


def refresh_log_path(paths: Paths) -> Path:
    return paths.cache_dir / "scheduled-refresh.log"


def schedule_label(paths: Paths) -> str:
    repo_slug = "".join(char if char.isalnum() else "-" for char in paths.repo_root.name.lower()).strip("-") or "eng-journal"
    return f"com.engjournal.{repo_slug}.refresh"


def launchd_plist_path(paths: Paths) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{schedule_label(paths)}.plist"


def build_refresh_command(
    paths: Paths,
    *,
    scan_gh_audit: bool = True,
    user: str = "stussysenik",
    workdir: Path | None = None,
    output_dir: Path | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> str:
    journal_bin = paths.repo_root / "bin" / "journal"
    parts = [shlex.quote(str(journal_bin)), "refresh"]
    if scan_gh_audit:
        parts.append("--scan-gh-audit")
        parts.extend(["--user", shlex.quote(user)])
        if workdir:
            parts.extend(["--workdir", shlex.quote(str(workdir))])
        if output_dir:
            parts.extend(["--output-dir", shlex.quote(str(output_dir))])
    if start_date:
        parts.extend(["--start", shlex.quote(start_date)])
    if end_date:
        parts.extend(["--end", shlex.quote(end_date)])
    return f"cd {shlex.quote(str(paths.repo_root))} && {' '.join(parts)}"


def _launchd_plist_xml(label: str, command: str, hour: int, minute: int, cadence: str, weekday: str, log_path: Path) -> str:
    interval = [
        "    <key>Hour</key>",
        f"    <integer>{hour}</integer>",
        "    <key>Minute</key>",
        f"    <integer>{minute}</integer>",
    ]
    if cadence == "weekly":
        interval.extend(
            [
                "    <key>Weekday</key>",
                f"    <integer>{WEEKDAY_TO_LAUNCHD[weekday]}</integer>",
            ]
        )
    interval_block = "\n".join(interval)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
        "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
        "<plist version=\"1.0\">\n"
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{escape(label)}</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        "    <string>/bin/zsh</string>\n"
        "    <string>-lc</string>\n"
        f"    <string>{escape(command)}</string>\n"
        "  </array>\n"
        "  <key>RunAtLoad</key>\n"
        "  <false/>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n"
        f"{interval_block}\n"
        "  </dict>\n"
        "  <key>WorkingDirectory</key>\n"
        f"  <string>{escape(str(log_path.parent.parent))}</string>\n"
        "  <key>StandardOutPath</key>\n"
        f"  <string>{escape(str(log_path))}</string>\n"
        "  <key>StandardErrorPath</key>\n"
        f"  <string>{escape(str(log_path))}</string>\n"
        "</dict>\n"
        "</plist>\n"
    )


def install_launchd_schedule(
    paths: Paths,
    *,
    command: str,
    hour: int,
    minute: int,
    cadence: str,
    weekday: str,
) -> Path:
    plist_path = launchd_plist_path(paths)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = refresh_log_path(paths)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_text(
        _launchd_plist_xml(schedule_label(paths), command, hour, minute, cadence, weekday, log_path),
        encoding="utf-8",
    )
    uid = str(os.getuid())
    subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)], check=False)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)], check=True)
    return plist_path


def remove_launchd_schedule(paths: Paths) -> Path:
    plist_path = launchd_plist_path(paths)
    uid = str(os.getuid())
    if plist_path.exists():
        subprocess.run(["launchctl", "bootout", f"gui/{uid}", str(plist_path)], check=False)
        plist_path.unlink()
    return plist_path


def launchd_schedule_status(paths: Paths) -> dict[str, str | bool]:
    plist_path = launchd_plist_path(paths)
    return {
        "runner": "launchd",
        "installed": plist_path.exists(),
        "path": str(plist_path),
        "log_path": str(refresh_log_path(paths)),
    }


def _current_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], check=False, capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 1:
        return ""
    raise RuntimeError(result.stderr.strip() or "crontab -l failed")


def _strip_cron_block(content: str) -> str:
    lines = content.splitlines()
    output: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped == CRON_MARKER_BEGIN:
            skipping = True
            continue
        if stripped == CRON_MARKER_END:
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return "\n".join(line for line in output if line.strip()).strip()


def _cron_schedule_line(command: str, hour: int, minute: int, cadence: str, weekday: str, log_path: Path) -> str:
    if cadence == "weekly":
        return f"{minute} {hour} * * {WEEKDAY_TO_CRON[weekday]} {command} >> {shlex.quote(str(log_path))} 2>&1"
    return f"{minute} {hour} * * * {command} >> {shlex.quote(str(log_path))} 2>&1"


def install_cron_schedule(
    paths: Paths,
    *,
    command: str,
    hour: int,
    minute: int,
    cadence: str,
    weekday: str,
) -> str:
    log_path = refresh_log_path(paths)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cron_line = _cron_schedule_line(command, hour, minute, cadence, weekday, log_path)
    current = _strip_cron_block(_current_crontab())
    block = "\n".join([CRON_MARKER_BEGIN, cron_line, CRON_MARKER_END])
    updated = "\n".join(part for part in [current, block] if part).strip() + "\n"
    subprocess.run(["crontab", "-"], input=updated, text=True, check=True)
    return cron_line


def remove_cron_schedule(paths: Paths) -> str:
    current = _current_crontab()
    updated = _strip_cron_block(current)
    subprocess.run(["crontab", "-"], input=(updated + "\n") if updated else "", text=True, check=True)
    return "removed"


def cron_schedule_status(paths: Paths) -> dict[str, str | bool]:
    current = _current_crontab()
    installed = CRON_MARKER_BEGIN in current and CRON_MARKER_END in current
    return {
        "runner": "cron",
        "installed": installed,
        "path": "crontab",
        "log_path": str(refresh_log_path(paths)),
    }
