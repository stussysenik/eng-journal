from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import build_period_dataset, write_period_dataset
from .config import default_paths
from .reporting import (
    render_appraisal_markdown,
    render_core_value_markdown,
    render_dashboard_ascii,
    render_daily_markdown,
    render_prompt_markdown,
    render_roi_markdown,
    render_weekly_markdown,
    write_report,
)
from .screenshots import render_text_screenshot


def _default_start() -> str:
    return "2026-02-12"


def _default_end() -> str:
    return "2026-03-31"


def _period_slug(start_date: str, end_date: str) -> str:
    return f"{start_date}_to_{end_date}"


def _load_or_build_dataset(paths, start_date: str, end_date: str) -> dict:
    cache_path = paths.cache_dir / f"{_period_slug(start_date, end_date)}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    dataset = build_period_dataset(paths, start_date, end_date)
    write_period_dataset(paths, start_date, end_date, dataset)
    return dataset


def cmd_doctor(paths) -> int:
    checks = {
        "claude_projects": paths.claude_dir.joinpath("projects").exists(),
        "claude_history": paths.claude_dir.joinpath("history.jsonl").exists(),
        "codex_history": paths.codex_dir.joinpath("history.jsonl").exists(),
        "codex_state": paths.codex_dir.joinpath("state_5.sqlite").exists(),
        "codex_logs": paths.codex_dir.joinpath("logs_1.sqlite").exists(),
    }
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'missing'}")
    return 0 if all(checks.values()) else 1


def cmd_ingest(paths, start_date: str, end_date: str) -> int:
    dataset = build_period_dataset(paths, start_date, end_date)
    cache_path = write_period_dataset(paths, start_date, end_date, dataset)
    print(cache_path)
    return 0


def cmd_report(paths, args) -> int:
    if args.kind == "daily":
        dataset = _load_or_build_dataset(paths, args.date, args.date)
        content = render_daily_markdown(dataset, args.date)
        target = write_report(paths.reports_dir / f"daily-{args.date}.md", content)
    else:
        start_date = args.start or _default_start()
        end_date = args.end or _default_end()
        dataset = _load_or_build_dataset(paths, start_date, end_date)
        if args.kind == "weekly":
            content = render_weekly_markdown(dataset)
            target = write_report(paths.reports_dir / f"weekly-{_period_slug(start_date, end_date)}.md", content)
        elif args.kind == "prompts":
            content = render_prompt_markdown(dataset, args.agent)
            suffix = args.agent or "all"
            target = write_report(paths.reports_dir / f"prompts-{suffix}-{_period_slug(start_date, end_date)}.md", content)
        elif args.kind == "roi":
            content = render_roi_markdown(paths.repo_root, dataset, start_date, end_date)
            target = write_report(paths.reports_dir / f"roi-{_period_slug(start_date, end_date)}.md", content)
        elif args.kind == "appraisal":
            content = render_appraisal_markdown(dataset)
            target = write_report(paths.reports_dir / f"appraisal-{_period_slug(start_date, end_date)}.md", content)
        elif args.kind == "core-value":
            content = render_core_value_markdown(dataset)
            target = write_report(paths.reports_dir / f"core-value-{_period_slug(start_date, end_date)}.md", content)
        elif args.kind == "dashboard":
            content = render_dashboard_ascii(dataset)
            target = write_report(paths.reports_dir / f"dashboard-{_period_slug(start_date, end_date)}.txt", content)
        else:
            raise ValueError(f"Unknown report kind: {args.kind}")
    print(target)
    return 0


def cmd_capture(paths, args) -> int:
    start_date = args.start or _default_start()
    end_date = args.end or _default_end()
    slug = _period_slug(start_date, end_date)
    dataset = _load_or_build_dataset(paths, start_date, end_date)
    dashboard_path = write_report(paths.reports_dir / f"dashboard-{slug}.txt", render_dashboard_ascii(dataset))
    core_value_path = write_report(paths.reports_dir / f"core-value-{slug}.md", render_core_value_markdown(dataset))
    ascii_png = render_text_screenshot(
        dashboard_path,
        paths.repo_root / "assets" / "screenshots" / f"dashboard-{slug}.png",
        f"./bin/journal report dashboard --start {start_date} --end {end_date}",
    )
    core_value_png = render_text_screenshot(
        core_value_path,
        paths.repo_root / "assets" / "screenshots" / f"core-value-{slug}.png",
        f"./bin/journal report core-value --start {start_date} --end {end_date}",
    )
    print(ascii_png)
    print(core_value_png)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cross-agent engineering journal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("doctor", help="Check local data sources")

    ingest = subparsers.add_parser("ingest", help="Build a normalized period dataset")
    ingest.add_argument("--start", default=_default_start())
    ingest.add_argument("--end", default=_default_end())

    report = subparsers.add_parser("report", help="Render Markdown reports")
    report_sub = report.add_subparsers(dest="kind", required=True)

    daily = report_sub.add_parser("daily", help="Render a single-day journal")
    daily.add_argument("--date", required=True)

    weekly = report_sub.add_parser("weekly", help="Render weekly rollup")
    weekly.add_argument("--start", default=_default_start())
    weekly.add_argument("--end", default=_default_end())

    prompts = report_sub.add_parser("prompts", help="Render prompt report")
    prompts.add_argument("--start", default=_default_start())
    prompts.add_argument("--end", default=_default_end())
    prompts.add_argument("--agent", choices=["claude_code", "codex"])

    roi = report_sub.add_parser("roi", help="Render ROI scorecard through SBCL")
    roi.add_argument("--start", default=_default_start())
    roi.add_argument("--end", default=_default_end())

    appraisal = report_sub.add_parser("appraisal", help="Render portfolio appraisal report")
    appraisal.add_argument("--start", default=_default_start())
    appraisal.add_argument("--end", default=_default_end())

    core_value = report_sub.add_parser("core-value", help="Render core builder value report")
    core_value.add_argument("--start", default=_default_start())
    core_value.add_argument("--end", default=_default_end())

    dashboard = report_sub.add_parser("dashboard", help="Render ASCII analytics dashboard")
    dashboard.add_argument("--start", default=_default_start())
    dashboard.add_argument("--end", default=_default_end())

    capture = subparsers.add_parser("capture", help="Generate screenshot assets")
    capture_sub = capture.add_subparsers(dest="capture_kind", required=True)
    screenshots = capture_sub.add_parser("screenshots", help="Render screenshot PNGs from ASCII/text reports")
    screenshots.add_argument("--start", default=_default_start())
    screenshots.add_argument("--end", default=_default_end())

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    paths = default_paths()
    paths.cache_dir.mkdir(exist_ok=True)
    paths.reports_dir.mkdir(exist_ok=True)

    if args.command == "doctor":
        return cmd_doctor(paths)
    if args.command == "ingest":
        return cmd_ingest(paths, args.start, args.end)
    if args.command == "report":
        return cmd_report(paths, args)
    if args.command == "capture":
        if args.capture_kind == "screenshots":
            return cmd_capture(paths, args)
    raise ValueError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
