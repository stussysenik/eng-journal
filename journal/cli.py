from __future__ import annotations

import argparse
import datetime as dt
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
from .gh_audit import (
    default_gh_audit_output_dir,
    default_gh_audit_workdir,
    gh_audit_reference_path,
    import_gh_audit_reference,
    load_gh_audit_reference,
    run_gh_audit_scan,
)
from .reporting import (
    render_appraisal_markdown,
    render_core_value_markdown,
    render_dashboard_ascii,
    render_daily_markdown,
    render_impact_markdown,
    render_learning_markdown,
    render_prompt_markdown,
    render_review_markdown,
    render_roi_markdown,
    render_scheduler_status_markdown,
    render_stats_markdown,
    render_weekly_markdown,
    stats_payload,
    write_report,
)
from .scheduler import (
    build_refresh_command,
    cron_schedule_status,
    install_cron_schedule,
    install_launchd_schedule,
    launchd_schedule_status,
    load_refresh_state,
    remove_cron_schedule,
    remove_launchd_schedule,
    schedule_status,
    schedule_runner,
    write_refresh_state,
)
from .screenshots import render_text_screenshot


def _default_start() -> str:
    return "2026-01-01"


def _default_end() -> str:
    return "2026-03-31"


def _period_slug(start_date: str, end_date: str) -> str:
    return f"{start_date}_to_{end_date}"


def _latest_verified_window(paths) -> tuple[str, str] | None:
    if not paths.checkpoints_dir.exists():
        return None
    candidates: list[tuple[str, str, str]] = []
    for manifest_path in paths.checkpoints_dir.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        window = manifest.get("window", {})
        start_date = window.get("start_date")
        end_date = window.get("end_date")
        verified_at = manifest.get("verified_at", "")
        if start_date and end_date and verified_at:
            candidates.append((verified_at, start_date, end_date))
    if not candidates:
        return None
    _, start_date, end_date = max(candidates)
    return start_date, end_date


def _resolve_window(paths, start_date: str | None, end_date: str | None) -> tuple[str, str]:
    if start_date and end_date:
        return start_date, end_date
    latest_verified = _latest_verified_window(paths)
    default_start = start_date or (latest_verified[0] if latest_verified else _default_start())
    default_end = end_date or (latest_verified[1] if latest_verified else _default_end())
    return default_start, default_end


def _dataset_matches_current_schema(dataset: dict) -> bool:
    agents = dataset.get("agents", {})
    if not agents:
        return False
    for agent in agents.values():
        if "first_activity_date" not in agent or "last_activity_date" not in agent or "event_count" not in agent:
            return False
        if "directive_signals" not in agent.get("prompt_metrics", {}):
            return False
        if "prompt_effectiveness" not in agent or "prompt_daily_rows" not in agent:
            return False
        if "source_bounds" not in agent:
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
        "impact": paths.reports_dir / f"impact-{slug}.md",
        "dashboard": paths.reports_dir / f"dashboard-{slug}.txt",
        "roi": paths.reports_dir / f"roi-{slug}.md",
        "prompts_claude": paths.reports_dir / f"prompts-claude_code-{slug}.md",
        "prompts_codex": paths.reports_dir / f"prompts-codex-{slug}.md",
        "scheduler_status": paths.reports_dir / "scheduler-status.md",
        "learning": paths.repo_root / "LEARNING.md",
        "checkpoint_manifest": checkpoint_manifest_path(paths, start_date, end_date),
        "checkpoint_dataset": checkpoint_dataset_path(paths, start_date, end_date),
    }


def _write_scheduler_status_report(paths, runner: str | None = None) -> Path:
    return write_report(
        paths.reports_dir / "scheduler-status.md",
        render_scheduler_status_markdown(schedule_status(paths, runner), load_refresh_state(paths)),
    )


def cmd_doctor(paths) -> int:
    sources = discover_sources(paths)
    scheduler = schedule_status(paths)
    refresh_state = load_refresh_state(paths)
    checks = {
        "claude_projects": sources.claude_projects_dir,
        "claude_history": sources.claude_history_file,
        "codex_history": sources.codex_history_file,
        "codex_state": sources.codex_state_db,
        "codex_logs": sources.codex_logs_db,
        "cc_config_logs": sources.cc_config_logs_dir,
        "cc_config_stats": sources.cc_config_stats_file,
        "gh_audit_dir": paths.gh_audit_dir,
        "gh_audit_reference": gh_audit_reference_path(paths) if gh_audit_reference_path(paths).exists() else None,
    }
    for name, path in checks.items():
        if path:
            print(f"{name}: ok ({path})")
        else:
            print(f"{name}: missing")
    if scheduler.get("installed"):
        hour = scheduler.get("hour")
        minute = scheduler.get("minute")
        time_text = (
            f"{int(hour):02d}:{int(minute):02d}"
            if isinstance(hour, int) and isinstance(minute, int)
            else "n/a"
        )
        cadence = scheduler.get("cadence", "n/a")
        weekday = scheduler.get("weekday", "")
        if cadence == "weekly" and weekday:
            cadence = f"{cadence}({weekday})"
        print(f"scheduler: {scheduler.get('runner')} installed path={scheduler.get('path')} timing={cadence}@{time_text}")
    else:
        print(f"scheduler: {scheduler.get('runner')} not installed")
    if refresh_state:
        print(
            "last_refresh: "
            f"status={refresh_state.get('status', 'unknown')} "
            f"completed_at={refresh_state.get('completed_at', 'n/a')}"
        )
    else:
        print("last_refresh: none")
    has_claude = bool(sources.claude_projects_dir or sources.claude_history_file or sources.cc_config_logs_dir)
    has_codex = bool(sources.codex_state_db or sources.codex_history_file)
    return 0 if has_claude and has_codex else 1


def cmd_ingest(paths, start_date: str, end_date: str) -> int:
    dataset = _build_and_cache_dataset(paths, start_date, end_date)
    cache_path = paths.cache_dir / f"{_period_slug(start_date, end_date)}.json"
    print(cache_path)
    return 0


def cmd_reference(paths, args) -> int:
    if args.reference_kind == "gh-audit":
        input_path = Path(args.input).expanduser().resolve() if args.input else None
        if args.scan:
            input_path = run_gh_audit_scan(
                paths,
                args.user,
                Path(args.workdir).expanduser().resolve() if args.workdir else default_gh_audit_workdir(paths),
                Path(args.output_dir).expanduser().resolve() if args.output_dir else default_gh_audit_output_dir(paths),
            )
        target = import_gh_audit_reference(paths, input_path)
        print(target)
        return 0
    raise ValueError(f"Unhandled reference kind: {args.reference_kind}")


def cmd_refresh(paths, args) -> int:
    start_date, end_date = _resolve_window(paths, args.start, args.end)
    state_payload: dict[str, object] = {
        "status": "running",
        "started_at": dt.datetime.now(dt.UTC).isoformat(),
        "completed_at": "",
        "scan_gh_audit": bool(args.scan_gh_audit),
        "window": {"start_date": start_date, "end_date": end_date},
    }
    write_refresh_state(paths, state_payload)
    try:
        if args.scan_gh_audit:
            source_path = run_gh_audit_scan(
                paths,
                args.user,
                Path(args.workdir).expanduser().resolve() if args.workdir else default_gh_audit_workdir(paths),
                Path(args.output_dir).expanduser().resolve() if args.output_dir else default_gh_audit_output_dir(paths),
            )
            reference_path = import_gh_audit_reference(paths, source_path)
            print(reference_path)
            state_payload["gh_audit_source_path"] = str(source_path)
            state_payload["reference_path"] = str(reference_path)
        review_args = argparse.Namespace(start=start_date, end=end_date, refresh=True)
        rc = cmd_review(paths, review_args)
        state_payload["status"] = "ok"
        state_payload["completed_at"] = dt.datetime.now(dt.UTC).isoformat()
        scheduler_report_path = paths.reports_dir / "scheduler-status.md"
        state_payload["scheduler_report_path"] = str(scheduler_report_path)
        write_refresh_state(paths, state_payload)
        _write_scheduler_status_report(paths)
        return rc
    except Exception as exc:
        state_payload["status"] = "failed"
        state_payload["completed_at"] = dt.datetime.now(dt.UTC).isoformat()
        state_payload["error"] = str(exc)
        scheduler_report_path = paths.reports_dir / "scheduler-status.md"
        state_payload["scheduler_report_path"] = str(scheduler_report_path)
        write_refresh_state(paths, state_payload)
        _write_scheduler_status_report(paths)
        raise


def cmd_schedule(paths, args) -> int:
    runner = schedule_runner(args.runner)
    start_date = args.start
    end_date = args.end
    workdir = Path(args.workdir).expanduser().resolve() if args.workdir else default_gh_audit_workdir(paths)
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else default_gh_audit_output_dir(paths)
    command = build_refresh_command(
        paths,
        scan_gh_audit=True,
        user=args.user,
        workdir=workdir,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
    )
    if args.schedule_action == "install":
        if runner == "launchd":
            target = install_launchd_schedule(
                paths,
                command=command,
                hour=args.hour,
                minute=args.minute,
                cadence=args.cadence,
                weekday=args.weekday,
            )
            print(target)
            print(_write_scheduler_status_report(paths, runner))
            return 0
        if runner == "cron":
            line = install_cron_schedule(
                paths,
                command=command,
                hour=args.hour,
                minute=args.minute,
                cadence=args.cadence,
                weekday=args.weekday,
            )
            print(line)
            print(_write_scheduler_status_report(paths, runner))
            return 0
    elif args.schedule_action == "remove":
        if runner == "launchd":
            print(remove_launchd_schedule(paths))
            print(_write_scheduler_status_report(paths, runner))
            return 0
        if runner == "cron":
            print(remove_cron_schedule(paths))
            print(_write_scheduler_status_report(paths, runner))
            return 0
    elif args.schedule_action == "status":
        status = schedule_status(paths, runner)
        print(json.dumps(status, indent=2))
        print(_write_scheduler_status_report(paths, runner))
        return 0
    raise ValueError(f"Unhandled schedule action: {args.schedule_action}")


def cmd_stats(paths, args) -> int:
    start_date, end_date = _resolve_window(paths, args.start, args.end)
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
    start_date, end_date = _resolve_window(paths, args.start, args.end)
    artifact_paths = _review_artifact_paths(paths, start_date, end_date)
    manifest = load_checkpoint_manifest(paths, start_date, end_date)
    existing_outputs = [
        artifact_paths["review"],
        artifact_paths["stats_markdown"],
        artifact_paths["stats_json"],
        artifact_paths["impact"],
        artifact_paths["dashboard"],
        artifact_paths["roi"],
        artifact_paths["prompts_claude"],
        artifact_paths["prompts_codex"],
        artifact_paths["scheduler_status"],
        artifact_paths["learning"],
        artifact_paths["checkpoint_manifest"],
        artifact_paths["checkpoint_dataset"],
    ]
    checkpoint_dataset = load_checkpoint_dataset(paths, start_date, end_date) if manifest else None
    if manifest and not args.refresh and _all_exist(existing_outputs) and checkpoint_dataset is not None and _dataset_matches_current_schema(checkpoint_dataset):
        dataset = checkpoint_dataset
        gh_audit_reference = load_gh_audit_reference(paths)
        _write_scheduler_status_report(paths)
        if dataset is not None:
            write_report(
                artifact_paths["learning"],
                render_learning_markdown(
                    dataset,
                    str(artifact_paths["review"].relative_to(paths.repo_root)),
                    str(artifact_paths["stats_markdown"].relative_to(paths.repo_root)),
                    str(artifact_paths["checkpoint_manifest"].relative_to(paths.repo_root)),
                    str(artifact_paths["impact"].relative_to(paths.repo_root)),
                    str(gh_audit_reference_path(paths).relative_to(paths.repo_root)) if gh_audit_reference else "",
                ),
            )
        for path in existing_outputs:
            print(path)
        return 0

    dataset = _build_and_cache_dataset(paths, start_date, end_date) if (args.refresh or manifest is None) else _load_review_dataset(paths, start_date, end_date)
    gh_audit_reference = load_gh_audit_reference(paths)
    artifacts = {
        "review": write_report(artifact_paths["review"], render_review_markdown(dataset)),
        "stats_markdown": write_report(artifact_paths["stats_markdown"], render_stats_markdown(dataset)),
        "stats_json": write_report(artifact_paths["stats_json"], json.dumps(stats_payload(dataset), indent=2) + "\n"),
        "impact": write_report(artifact_paths["impact"], render_impact_markdown(dataset, gh_audit_reference)),
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
        "scheduler_status": _write_scheduler_status_report(paths),
    }
    manifest_path = write_checkpoint(paths, start_date, end_date, dataset, artifacts)
    learning_path = write_report(
        artifact_paths["learning"],
        render_learning_markdown(
            dataset,
            str(artifact_paths["review"].relative_to(paths.repo_root)),
            str(artifact_paths["stats_markdown"].relative_to(paths.repo_root)),
            str(manifest_path.relative_to(paths.repo_root)),
            str(artifact_paths["impact"].relative_to(paths.repo_root)),
            str(gh_audit_reference_path(paths).relative_to(paths.repo_root)) if gh_audit_reference else "",
        ),
    )
    artifacts["learning"] = learning_path
    manifest_path = write_checkpoint(paths, start_date, end_date, dataset, artifacts)
    for path in [
        artifacts["review"],
        artifacts["stats_markdown"],
        artifacts["stats_json"],
        artifacts["impact"],
        artifacts["dashboard"],
        artifacts["roi"],
        artifacts["prompts_claude"],
        artifacts["prompts_codex"],
        artifacts["scheduler_status"],
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
    elif args.kind == "scheduler-status":
        content = render_scheduler_status_markdown(schedule_status(paths), load_refresh_state(paths))
        target = write_report(paths.reports_dir / "scheduler-status.md", content)
    else:
        start_date, end_date = _resolve_window(paths, args.start, args.end)
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
        elif args.kind == "impact":
            content = render_impact_markdown(dataset, load_gh_audit_reference(paths))
            target = write_report(paths.reports_dir / f"impact-{_period_slug(start_date, end_date)}.md", content)
        else:
            raise ValueError(f"Unknown report kind: {args.kind}")
    print(target)
    return 0


def cmd_capture(paths, args) -> int:
    start_date, end_date = _resolve_window(paths, args.start, args.end)
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

    reference = subparsers.add_parser("reference", help="Import external reference data")
    reference_sub = reference.add_subparsers(dest="reference_kind", required=True)
    gh_audit = reference_sub.add_parser("gh-audit", help="Import the latest gh-audit report into eng-journal references")
    gh_audit.add_argument("--input")
    gh_audit.add_argument("--scan", action="store_true", help="Run a fresh gh-audit scan before importing")
    gh_audit.add_argument("--user", default="stussysenik")
    gh_audit.add_argument("--workdir")
    gh_audit.add_argument("--output-dir")

    ingest = subparsers.add_parser("ingest", help="Build a normalized period dataset")
    ingest.add_argument("--start")
    ingest.add_argument("--end")

    stats = subparsers.add_parser("stats", help="Render reusable stats snapshots")
    stats.add_argument("--start")
    stats.add_argument("--end")
    stats.add_argument("--agent", choices=["claude_code", "codex"])
    stats.add_argument("--format", choices=["markdown", "json"], default="markdown")
    stats.add_argument("--refresh", action="store_true")

    review = subparsers.add_parser("review", help="Freeze a verified review window and generate durable outputs")
    review.add_argument("--start")
    review.add_argument("--end")
    review.add_argument("--refresh", action="store_true")

    refresh = subparsers.add_parser("refresh", help="Refresh gh-audit references and rebuild review outputs")
    refresh.add_argument("--start")
    refresh.add_argument("--end")
    refresh.add_argument("--scan-gh-audit", action="store_true")
    refresh.add_argument("--user", default="stussysenik")
    refresh.add_argument("--workdir")
    refresh.add_argument("--output-dir")

    schedule = subparsers.add_parser("schedule", help="Install or inspect local scheduled refresh jobs")
    schedule.add_argument("schedule_action", choices=["install", "status", "remove"])
    schedule.add_argument("--runner", choices=["auto", "launchd", "cron"], default="auto")
    schedule.add_argument("--cadence", choices=["daily", "weekly"], default="daily")
    schedule.add_argument("--weekday", choices=["sun", "mon", "tue", "wed", "thu", "fri", "sat"], default="mon")
    schedule.add_argument("--hour", type=int, default=3)
    schedule.add_argument("--minute", type=int, default=17)
    schedule.add_argument("--start")
    schedule.add_argument("--end")
    schedule.add_argument("--user", default="stussysenik")
    schedule.add_argument("--workdir")
    schedule.add_argument("--output-dir")

    report = subparsers.add_parser("report", help="Render Markdown reports")
    report_sub = report.add_subparsers(dest="kind", required=True)

    daily = report_sub.add_parser("daily", help="Render a single-day journal")
    daily.add_argument("--date", required=True)

    weekly = report_sub.add_parser("weekly", help="Render weekly rollup")
    weekly.add_argument("--start")
    weekly.add_argument("--end")

    prompts = report_sub.add_parser("prompts", help="Render prompt report")
    prompts.add_argument("--start")
    prompts.add_argument("--end")
    prompts.add_argument("--agent", choices=["claude_code", "codex"])

    roi = report_sub.add_parser("roi", help="Render ROI scorecard through SBCL")
    roi.add_argument("--start")
    roi.add_argument("--end")

    appraisal = report_sub.add_parser("appraisal", help="Render portfolio appraisal report")
    appraisal.add_argument("--start")
    appraisal.add_argument("--end")

    core_value = report_sub.add_parser("core-value", help="Render core builder value report")
    core_value.add_argument("--start")
    core_value.add_argument("--end")

    dashboard = report_sub.add_parser("dashboard", help="Render ASCII analytics dashboard")
    dashboard.add_argument("--start")
    dashboard.add_argument("--end")
    impact = report_sub.add_parser("impact", help="Render job/application impact summary with gh-audit references")
    impact.add_argument("--start")
    impact.add_argument("--end")
    report_sub.add_parser("scheduler-status", help="Render local scheduler and refresh status")

    capture = subparsers.add_parser("capture", help="Generate screenshot assets")
    capture_sub = capture.add_subparsers(dest="capture_kind", required=True)
    screenshots = capture_sub.add_parser("screenshots", help="Render screenshot PNGs from ASCII/text reports")
    screenshots.add_argument("--start")
    screenshots.add_argument("--end")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    paths = default_paths()
    paths.cache_dir.mkdir(exist_ok=True)
    paths.reports_dir.mkdir(exist_ok=True)
    paths.checkpoints_dir.mkdir(exist_ok=True)
    paths.references_dir.mkdir(exist_ok=True)

    if args.command == "doctor":
        return cmd_doctor(paths)
    if args.command == "reference":
        return cmd_reference(paths, args)
    if args.command == "ingest":
        start_date, end_date = _resolve_window(paths, args.start, args.end)
        return cmd_ingest(paths, start_date, end_date)
    if args.command == "stats":
        return cmd_stats(paths, args)
    if args.command == "review":
        return cmd_review(paths, args)
    if args.command == "refresh":
        return cmd_refresh(paths, args)
    if args.command == "report":
        return cmd_report(paths, args)
    if args.command == "capture":
        if args.capture_kind == "screenshots":
            return cmd_capture(paths, args)
    if args.command == "schedule":
        return cmd_schedule(paths, args)
    raise ValueError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
