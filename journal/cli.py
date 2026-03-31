from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import build_period_dataset, write_period_dataset
from .checkpoints import (
    checkpoint_dataset_path,
    checkpoint_manifest_path,
    load_checkpoint_dataset,
    load_checkpoint_manifest,
    write_checkpoint,
)
from .config import default_paths, discover_sources
from .reporting import (
    render_appraisal_markdown,
    render_core_value_markdown,
    render_dashboard_ascii,
    render_daily_markdown,
    render_learning_markdown,
    render_prompt_markdown,
    render_review_markdown,
    render_roi_markdown,
    render_stats_markdown,
    render_weekly_markdown,
    stats_payload,
    write_report,
)
from .screenshots import render_text_screenshot


def _default_start() -> str:
    return "2026-01-01"


def _default_end() -> str:
    return "2026-03-31"


def _period_slug(start_date: str, end_date: str) -> str:
    return f"{start_date}_to_{end_date}"


def _dataset_matches_current_schema(dataset: dict) -> bool:
    agents = dataset.get("agents", {})
    if not agents:
        return False
    for agent in agents.values():
        if "first_activity_date" not in agent or "last_activity_date" not in agent or "event_count" not in agent:
            return False
        if "directive_signals" not in agent.get("prompt_metrics", {}):
            return False
    return True


def _load_or_build_dataset(paths, start_date: str, end_date: str) -> dict:
    cache_path = paths.cache_dir / f"{_period_slug(start_date, end_date)}.json"
    if cache_path.exists():
        dataset = json.loads(cache_path.read_text(encoding="utf-8"))
        if _dataset_matches_current_schema(dataset):
            return dataset
    dataset = build_period_dataset(paths, start_date, end_date)
    write_period_dataset(paths, start_date, end_date, dataset)
    return dataset


def _build_and_cache_dataset(paths, start_date: str, end_date: str) -> dict:
    dataset = build_period_dataset(paths, start_date, end_date)
    write_period_dataset(paths, start_date, end_date, dataset)
    return dataset


def _load_review_dataset(paths, start_date: str, end_date: str, refresh: bool = False) -> dict:
    if not refresh:
        checkpoint_dataset = load_checkpoint_dataset(paths, start_date, end_date)
        if checkpoint_dataset is not None and _dataset_matches_current_schema(checkpoint_dataset):
            return checkpoint_dataset
    return _build_and_cache_dataset(paths, start_date, end_date) if refresh else _load_or_build_dataset(paths, start_date, end_date)


def _all_exist(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)


def _review_artifact_paths(paths, start_date: str, end_date: str) -> dict[str, Path]:
    slug = _period_slug(start_date, end_date)
    return {
        "review": paths.reports_dir / f"review-{slug}.md",
        "stats_markdown": paths.reports_dir / f"stats-{slug}.md",
        "stats_json": paths.reports_dir / f"stats-{slug}.json",
        "dashboard": paths.reports_dir / f"dashboard-{slug}.txt",
        "roi": paths.reports_dir / f"roi-{slug}.md",
        "prompts_claude": paths.reports_dir / f"prompts-claude_code-{slug}.md",
        "prompts_codex": paths.reports_dir / f"prompts-codex-{slug}.md",
        "learning": paths.repo_root / "LEARNING.md",
        "checkpoint_manifest": checkpoint_manifest_path(paths, start_date, end_date),
        "checkpoint_dataset": checkpoint_dataset_path(paths, start_date, end_date),
    }


def cmd_doctor(paths) -> int:
    sources = discover_sources(paths)
    checks = {
        "claude_projects": sources.claude_projects_dir,
        "claude_history": sources.claude_history_file,
        "codex_history": sources.codex_history_file,
        "codex_state": sources.codex_state_db,
        "codex_logs": sources.codex_logs_db,
        "cc_config_logs": sources.cc_config_logs_dir,
        "cc_config_stats": sources.cc_config_stats_file,
    }
    for name, path in checks.items():
        if path:
            print(f"{name}: ok ({path})")
        else:
            print(f"{name}: missing")
    has_claude = bool(sources.claude_projects_dir or sources.claude_history_file or sources.cc_config_logs_dir)
    has_codex = bool(sources.codex_state_db or sources.codex_history_file)
    return 0 if has_claude and has_codex else 1


def cmd_ingest(paths, start_date: str, end_date: str) -> int:
    dataset = _build_and_cache_dataset(paths, start_date, end_date)
    cache_path = paths.cache_dir / f"{_period_slug(start_date, end_date)}.json"
    print(cache_path)
    return 0


def cmd_stats(paths, args) -> int:
    start_date = args.start or _default_start()
    end_date = args.end or _default_end()
    dataset = _load_review_dataset(paths, start_date, end_date, refresh=args.refresh)
    slug = _period_slug(start_date, end_date)
    suffix = f"-{args.agent}" if args.agent else ""
    if args.format == "json":
        content = json.dumps(stats_payload(dataset, args.agent), indent=2) + "\n"
        target = write_report(paths.reports_dir / f"stats{suffix}-{slug}.json", content)
    else:
        content = render_stats_markdown(dataset, args.agent)
        target = write_report(paths.reports_dir / f"stats{suffix}-{slug}.md", content)
    print(target)
    return 0


def cmd_review(paths, args) -> int:
    start_date = args.start or _default_start()
    end_date = args.end or _default_end()
    artifact_paths = _review_artifact_paths(paths, start_date, end_date)
    manifest = load_checkpoint_manifest(paths, start_date, end_date)
    existing_outputs = [
        artifact_paths["review"],
        artifact_paths["stats_markdown"],
        artifact_paths["stats_json"],
        artifact_paths["dashboard"],
        artifact_paths["roi"],
        artifact_paths["prompts_claude"],
        artifact_paths["prompts_codex"],
        artifact_paths["learning"],
        artifact_paths["checkpoint_manifest"],
        artifact_paths["checkpoint_dataset"],
    ]
    checkpoint_dataset = load_checkpoint_dataset(paths, start_date, end_date) if manifest else None
    if manifest and not args.refresh and _all_exist(existing_outputs) and checkpoint_dataset is not None and _dataset_matches_current_schema(checkpoint_dataset):
        dataset = checkpoint_dataset
        if dataset is not None:
            write_report(
                artifact_paths["learning"],
                render_learning_markdown(
                    dataset,
                    str(artifact_paths["review"].relative_to(paths.repo_root)),
                    str(artifact_paths["stats_markdown"].relative_to(paths.repo_root)),
                    str(artifact_paths["checkpoint_manifest"].relative_to(paths.repo_root)),
                ),
            )
        for path in existing_outputs:
            print(path)
        return 0

    dataset = _build_and_cache_dataset(paths, start_date, end_date) if (args.refresh or manifest is None) else _load_review_dataset(paths, start_date, end_date)
    artifacts = {
        "review": write_report(artifact_paths["review"], render_review_markdown(dataset)),
        "stats_markdown": write_report(artifact_paths["stats_markdown"], render_stats_markdown(dataset)),
        "stats_json": write_report(artifact_paths["stats_json"], json.dumps(stats_payload(dataset), indent=2) + "\n"),
        "dashboard": write_report(artifact_paths["dashboard"], render_dashboard_ascii(dataset)),
        "roi": write_report(artifact_paths["roi"], render_roi_markdown(paths.repo_root, dataset, start_date, end_date)),
        "prompts_claude": write_report(
            artifact_paths["prompts_claude"],
            render_prompt_markdown(dataset, "claude_code"),
        ),
        "prompts_codex": write_report(
            artifact_paths["prompts_codex"],
            render_prompt_markdown(dataset, "codex"),
        ),
    }
    manifest_path = write_checkpoint(paths, start_date, end_date, dataset, artifacts)
    learning_path = write_report(
        artifact_paths["learning"],
        render_learning_markdown(
            dataset,
            str(artifact_paths["review"].relative_to(paths.repo_root)),
            str(artifact_paths["stats_markdown"].relative_to(paths.repo_root)),
            str(manifest_path.relative_to(paths.repo_root)),
        ),
    )
    artifacts["learning"] = learning_path
    manifest_path = write_checkpoint(paths, start_date, end_date, dataset, artifacts)
    for path in [
        artifacts["review"],
        artifacts["stats_markdown"],
        artifacts["stats_json"],
        artifacts["dashboard"],
        artifacts["roi"],
        artifacts["prompts_claude"],
        artifacts["prompts_codex"],
        learning_path,
        manifest_path,
        checkpoint_dataset_path(paths, start_date, end_date),
    ]:
        print(path)
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

    stats = subparsers.add_parser("stats", help="Render reusable stats snapshots")
    stats.add_argument("--start", default=_default_start())
    stats.add_argument("--end", default=_default_end())
    stats.add_argument("--agent", choices=["claude_code", "codex"])
    stats.add_argument("--format", choices=["markdown", "json"], default="markdown")
    stats.add_argument("--refresh", action="store_true")

    review = subparsers.add_parser("review", help="Freeze a verified review window and generate durable outputs")
    review.add_argument("--start", default=_default_start())
    review.add_argument("--end", default=_default_end())
    review.add_argument("--refresh", action="store_true")

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
    paths.checkpoints_dir.mkdir(exist_ok=True)

    if args.command == "doctor":
        return cmd_doctor(paths)
    if args.command == "ingest":
        return cmd_ingest(paths, args.start, args.end)
    if args.command == "stats":
        return cmd_stats(paths, args)
    if args.command == "review":
        return cmd_review(paths, args)
    if args.command == "report":
        return cmd_report(paths, args)
    if args.command == "capture":
        if args.capture_kind == "screenshots":
            return cmd_capture(paths, args)
    raise ValueError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
