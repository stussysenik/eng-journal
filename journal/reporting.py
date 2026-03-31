from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from .serialization import write_sexp
from .util import compact_text, safe_div


def render_daily_markdown(dataset: dict, date_str: str) -> str:
    rows = [row for row in dataset["daily_rows"] if row["date"] == date_str]
    lines = [f"# Daily Engineering Journal - {date_str}", ""]
    if not rows:
        lines.append("No activity found for this date.")
        return "\n".join(lines) + "\n"
    for row in rows:
        agent = dataset["agents"][row["agent"]]
        prompt_day = next((item for item in agent.get("prompt_daily_rows", []) if item["date"] == date_str), None)
        lines.append(f"## {agent['display_name']}")
        lines.append(f"- Events: {row['events']}")
        lines.append(f"- Threads: {row['thread_count']}")
        lines.append(f"- Projects: {row['project_count']}")
        lines.append(f"- Cost proxy: ${row['cost']:.2f}")
        if prompt_day:
            lines.append(
                f"- Prompts: {prompt_day['prompt_count']} total, {prompt_day['substantive_prompt_count']} substantive, "
                f"{prompt_day['mega_prompt_count']} mega, {prompt_day['duplicate_prompt_instances']} duplicate instances"
            )
            lines.append(f"- Average prompt length: {prompt_day['avg_prompt_length']:.1f} chars")
            if prompt_day["top_projects"]:
                lines.append("- Top projects: " + ", ".join(prompt_day["top_projects"]))
            if prompt_day["top_tags"]:
                lines.append("- Top tags: " + ", ".join(prompt_day["top_tags"]))
            if prompt_day["directive_signals"]:
                lines.append(
                    "- Directive signals: "
                    + ", ".join(f"{name} ({count})" for name, count in sorted(prompt_day["directive_signals"].items()))
                )
            if prompt_day["execution"]:
                lines.append(
                    "- Execution: "
                    + ", ".join(f"{name} ({count})" for name, count in sorted(prompt_day["execution"].items()))
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_weekly_markdown(dataset: dict) -> str:
    lines = [
        f"# Weekly Rollup - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
    ]
    for agent_name, agent in dataset["agents"].items():
        lines.append(f"## {agent['display_name']}")
        for row in agent["weekly_rows"]:
            lines.append(
                f"- {row['week']}: {row['days_active']} active days, {row['events']} events, "
                f"{row['threads']} threads, ${row['cost']:.2f} cost proxy"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_prompt_markdown(dataset: dict, agent_filter: str | None = None) -> str:
    lines = [
        f"# Prompt Efficiency Report - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
    ]
    agent_items = dataset["agents"].items()
    for agent_name, agent in agent_items:
        if agent_filter and agent_name != agent_filter:
            continue
        prompt_metrics = agent["prompt_metrics"]
        lines.append(f"## {agent['display_name']}")
        lines.append(f"- Total prompts: {prompt_metrics['total_prompts']}")
        lines.append(f"- Average length: {prompt_metrics['avg_prompt_length']:.1f} chars")
        lines.append(f"- Mega prompts: {prompt_metrics['mega_prompt_count']}")
        lines.append(
            f"- Control prompts: {prompt_metrics.get('control_prompt_count', 0)} | "
            f"Substantive prompts: {prompt_metrics.get('substantive_prompt_count', 0)}"
        )
        lines.append(f"- Duplicate prompt instances: {prompt_metrics['duplicate_prompt_instances']}")
        if "substantive_duplicate_instances" in prompt_metrics:
            lines.append(f"- Substantive duplicate instances: {prompt_metrics['substantive_duplicate_instances']}")
        if prompt_metrics["tags"]:
            lines.append("- Top semantic tags: " + ", ".join(f"{item['name']} ({item['count']})" for item in prompt_metrics["tags"]))
        if prompt_metrics.get("directive_signals"):
            lines.append("- Directive signals: " + ", ".join(f"{item['name']} ({item['count']})" for item in prompt_metrics["directive_signals"]))
        lines.append("")
        lines.append("### What Worked")
        effectiveness = agent.get("prompt_effectiveness", {})
        baseline = effectiveness.get("baseline", {})
        if baseline:
            lines.append(
                f"- Baseline active day: {baseline['avg_projects']:.2f} projects, {baseline['avg_threads']:.2f} threads, "
                f"{baseline['avg_execution_total']:.2f} execution actions, {baseline['avg_mega_prompts']:.2f} mega prompts"
            )
        patterns = effectiveness.get("patterns", [])
        if patterns:
            for item in sorted(patterns, key=lambda entry: (entry["execution_delta_vs_baseline"], entry["projects_delta_vs_baseline"]), reverse=True):
                lines.append(
                    f"- {item['name']}: {item['days']} days / {item['prompt_count']} prompts, "
                    f"{item['avg_projects']:.2f} projects/day ({item['projects_delta_vs_baseline']:+.2f}), "
                    f"{item['avg_execution_total']:.2f} execution/day ({item['execution_delta_vs_baseline']:+.2f})"
                )
        else:
            lines.append("- No directive-signal effectiveness patterns detected.")
        lines.append("")
        lines.append("### Highest-Output Prompt Days")
        high_output_days = effectiveness.get("high_output_days", [])
        if high_output_days:
            for row in high_output_days[:10]:
                signal_summary = ", ".join(
                    f"{name} ({count})" for name, count in sorted(row.get("directive_signals", {}).items())
                ) or "none"
                lines.append(
                    f"- {row['date']}: {row['prompt_count']} prompts, {row['project_count']} projects, "
                    f"{row['execution_total']} execution actions, top projects {', '.join(row['top_projects']) or 'none'}, "
                    f"signals {signal_summary}"
                )
        else:
            lines.append("- No prompt-daily rows available.")
        lines.append("")
        lines.append("### Repeated prompts")
        if prompt_metrics["duplicates"]:
            for item in prompt_metrics["duplicates"]:
                lines.append(f"- {item['count']}x {item['prompt']}")
        else:
            lines.append("- None detected")
        lines.append("")
        lines.append("### Longest prompts")
        for item in prompt_metrics["longest"]:
            lines.append(f"- {item['project_name']} [{item['prompt_length']} chars]: {item['prompt']}")
        lines.append("")
        if agent_name == "codex":
            lines.append("### Highest-cost Codex threads")
            for thread in agent["sample_threads"][:10]:
                lines.append(
                    f"- {thread['project_name']} ${thread['usage_cost']:.2f} midpoint, {thread['tokens_total']:,} tokens: {thread.get('title', '')}"
                )
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _signal_counts(prompt_metrics: dict) -> dict[str, int]:
    return {item["name"]: item["count"] for item in prompt_metrics.get("directive_signals", [])}


def _format_source_bounds(source_bounds: dict[str, dict]) -> str:
    parts = []
    for source_name, bounds in source_bounds.items():
        first_date = bounds.get("first_date", "")
        last_date = bounds.get("last_date", "")
        if not first_date and not last_date:
            continue
        parts.append(f"{source_name} {first_date or 'n/a'} to {last_date or 'n/a'}")
    return ", ".join(parts) if parts else "none"


def stats_payload(dataset: dict, agent_filter: str | None = None) -> dict:
    payload = {
        "window": dataset["window"],
        "generated_at": dataset["generated_at"],
        "agents": {},
    }
    for agent_name, agent in dataset["agents"].items():
        if agent_filter and agent_name != agent_filter:
            continue
        prompt_metrics = agent["prompt_metrics"]
        execution_metrics = agent["execution_metrics"]
        friction_metrics = agent["friction_metrics"]
        payload["agents"][agent_name] = {
            "display_name": agent["display_name"],
            "source_coverage": agent.get("source_coverage", []),
            "source_bounds": agent.get("source_bounds", {}),
            "cost_confidence": agent["cost_confidence"],
            "active_days": agent["active_days"],
            "first_activity_date": agent.get("first_activity_date", ""),
            "last_activity_date": agent.get("last_activity_date", ""),
            "event_count": agent.get("event_count", 0),
            "thread_count": agent["thread_count"],
            "project_count": agent["project_count"],
            "work_unit_count": agent["work_unit_count"],
            "total_tokens": agent["total_tokens"],
            "cost_low": agent["cost_low"],
            "cost_mid": agent["cost_mid"],
            "cost_high": agent["cost_high"],
            "monthly_cost_low": agent["monthly_cost_low"],
            "monthly_cost_mid": agent["monthly_cost_mid"],
            "monthly_cost_high": agent["monthly_cost_high"],
            "prompt_metrics": prompt_metrics,
            "prompt_effectiveness": agent.get("prompt_effectiveness", {}),
            "prompt_daily_rows": agent.get("prompt_daily_rows", []),
            "execution_metrics": execution_metrics,
            "friction_metrics": friction_metrics,
            "git_evidence": {
                "repo_count": agent["git_evidence"]["repo_count"],
                "commit_count": agent["git_evidence"]["commit_count"],
            },
            "derived": {
                "tokens_per_thread": round(safe_div(agent["total_tokens"], agent["thread_count"]), 2),
                "tokens_per_project": round(safe_div(agent["total_tokens"], agent["project_count"]), 2),
                "prompts_per_active_day": round(safe_div(prompt_metrics["total_prompts"], agent["active_days"]), 2),
                "mega_prompt_rate": round(safe_div(prompt_metrics["mega_prompt_count"], max(prompt_metrics["total_prompts"], 1)), 4),
                "duplicate_prompt_rate": round(safe_div(prompt_metrics["duplicate_prompt_instances"], max(prompt_metrics["total_prompts"], 1)), 4),
                "cost_per_work_unit_mid": round(safe_div(agent["cost_mid"], max(agent["work_unit_count"], 1)), 4),
            },
            "top_projects": agent["top_projects"][:8],
            "sample_threads": agent["sample_threads"][:8],
        }
    return payload


def render_stats_markdown(dataset: dict, agent_filter: str | None = None) -> str:
    payload = stats_payload(dataset, agent_filter)
    lines = [
        f"# Stats Snapshot - {payload['window']['start_date']} to {payload['window']['end_date']}",
        "",
    ]
    for _, agent in payload["agents"].items():
        lines.append(f"## {agent['display_name']}")
        lines.append("- Source coverage: " + (", ".join(agent["source_coverage"]) or "none"))
        lines.append("- Source availability: " + _format_source_bounds(agent.get("source_bounds", {})))
        lines.append(f"- Cost confidence: {agent['cost_confidence']}")
        lines.append(
            f"- Activity span: {agent['first_activity_date'] or 'n/a'} to {agent['last_activity_date'] or 'n/a'} "
            f"across {agent['active_days']} active days"
        )
        lines.append(
            f"- Surface: {agent['event_count']} events, {agent['thread_count']} threads, "
            f"{agent['project_count']} projects, {agent['work_unit_count']} work units"
        )
        lines.append(
            f"- Cost: ${agent['cost_mid']:,.2f} period midpoint, ${agent['monthly_cost_mid']:,.2f} monthly midpoint"
        )
        lines.append(
            f"- Prompt shape: {agent['prompt_metrics']['total_prompts']} prompts, "
            f"{agent['prompt_metrics']['mega_prompt_count']} mega, "
            f"{agent['prompt_metrics']['duplicate_prompt_instances']} duplicate instances"
        )
        lines.append(
            f"- Prompt mix: {agent['prompt_metrics'].get('control_prompt_count', 0)} control, "
            f"{agent['prompt_metrics'].get('substantive_prompt_count', 0)} substantive, "
            f"{agent['prompt_metrics'].get('substantive_duplicate_instances', 0)} substantive duplicates"
        )
        if agent["prompt_metrics"].get("directive_signals"):
            lines.append(
                "- Directive signals: "
                + ", ".join(f"{item['name']} ({item['count']})" for item in agent["prompt_metrics"]["directive_signals"])
            )
        patterns = agent.get("prompt_effectiveness", {}).get("patterns", [])
        if patterns:
            top_pattern = sorted(
                patterns,
                key=lambda item: (item["execution_delta_vs_baseline"], item["projects_delta_vs_baseline"]),
                reverse=True,
            )[0]
            lines.append(
                f"- Prompt signal with strongest output lift: {top_pattern['name']} on {top_pattern['days']} days, "
                f"{top_pattern['avg_projects']:.2f} projects/day ({top_pattern['projects_delta_vs_baseline']:+.2f}), "
                f"{top_pattern['avg_execution_total']:.2f} execution/day ({top_pattern['execution_delta_vs_baseline']:+.2f})"
            )
        lines.append(
            f"- Derived: {agent['derived']['tokens_per_thread']:,.0f} tokens/thread, "
            f"{agent['derived']['tokens_per_project']:,.0f} tokens/project, "
            f"{agent['derived']['cost_per_work_unit_mid']:,.2f} cost/work-unit"
        )
        if any(agent["execution_metrics"].values()):
            lines.append(
                f"- Execution: created {agent['execution_metrics']['created_file']}, "
                f"modified {agent['execution_metrics']['modified_file']}, "
                f"read {agent['execution_metrics']['read_file']}, "
                f"commands {agent['execution_metrics']['ran_command']}, "
                f"delegated {agent['execution_metrics']['delegated']}, "
                f"web {agent['execution_metrics']['web_search']}"
            )
        lines.append(
            f"- Friction: errors {agent['friction_metrics']['error_count']}, "
            f"warnings {agent['friction_metrics']['warning_count']}, "
            f"patch failures {agent['friction_metrics']['apply_patch_failures']}, "
            f"subagent threads {agent['friction_metrics']['subagent_threads']}"
        )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _agent_strength_lines(agent_name: str, agent: dict) -> list[str]:
    lines: list[str] = []
    prompt_metrics = agent["prompt_metrics"]
    execution = agent["execution_metrics"]
    derived = stats_payload({"window": {"start_date": "", "end_date": ""}, "generated_at": "", "agents": {agent_name: agent}})["agents"][agent_name]["derived"]
    signals = _signal_counts(prompt_metrics)
    if agent["project_count"] >= 25:
        lines.append(f"- Cross-project continuity is strong: {agent['project_count']} projects and {agent['work_unit_count']} work units in-window.")
    if execution.get("created_file", 0) + execution.get("modified_file", 0) >= 1000:
        lines.append(
            f"- Direct execution is real, not just chat: {execution['created_file']} files created and {execution['modified_file']} modified."
        )
    if derived["tokens_per_thread"] >= 5_000_000:
        lines.append(f"- Thread depth is high: roughly {derived['tokens_per_thread']:,.0f} tokens per thread on average.")
    if signals.get("interview_before_action", 0):
        lines.append(f"- Interview-before-action prompting is present in {signals['interview_before_action']} prompts.")
    if signals.get("verification_first", 0):
        lines.append(f"- Verification-first behavior shows up in {signals['verification_first']} prompts.")
    if signals.get("parallel_agents", 0):
        lines.append(f"- Parallel/subagent orchestration appears in {signals['parallel_agents']} prompts.")
    if not lines:
        lines.append("- The strongest current signal is sustained activity across multiple projects with stable source coverage.")
    return lines


def _agent_tighten_lines(agent: dict) -> list[str]:
    lines: list[str] = []
    prompt_metrics = agent["prompt_metrics"]
    friction = agent["friction_metrics"]
    duplicate_rate = safe_div(prompt_metrics["duplicate_prompt_instances"], max(prompt_metrics["total_prompts"], 1))
    mega_rate = safe_div(prompt_metrics["mega_prompt_count"], max(prompt_metrics["total_prompts"], 1))
    if duplicate_rate >= 0.1:
        lines.append(
            f"- Duplicate prompt churn is high enough to tighten: {prompt_metrics['duplicate_prompt_instances']} duplicate instances."
        )
    if mega_rate >= 0.15:
        lines.append(f"- Mega-prompt usage is heavy: {prompt_metrics['mega_prompt_count']} mega prompts.")
    if friction["warning_count"] > 0:
        lines.append(f"- Warning volume is non-zero: {friction['warning_count']} warnings in-window.")
    if friction["apply_patch_failures"] > 0:
        lines.append(f"- Patch verification failed {friction['apply_patch_failures']} times; tighten edit/validation loops.")
    if not lines:
        lines.append("- The main next step is keeping this shape stable while compressing prompt noise.")
    return lines


def render_review_markdown(dataset: dict) -> str:
    lines = [
        f"# Base-Zero Review - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
        "This review is the canonical high-signal summary for the window. It is intended to be checkpointed and reused instead of re-deriving the same conclusions from scratch.",
        "",
        "## Trust",
    ]
    for agent_name, agent in dataset["agents"].items():
        lines.append(
            f"- {agent['display_name']}: source coverage {', '.join(agent.get('source_coverage', [])) or 'none'}, "
            f"source availability {_format_source_bounds(agent.get('source_bounds', {}))}, "
            f"cost confidence {agent['cost_confidence']}, active span {agent.get('first_activity_date', 'n/a')} to {agent.get('last_activity_date', 'n/a')}"
        )
    lines.extend(["", "## Agent Reviews"])

    for agent_name, agent in dataset["agents"].items():
        prompt_metrics = agent["prompt_metrics"]
        lines.append(f"### {agent['display_name']}")
        lines.append(
            f"- Base summary: {agent['active_days']} active days, {agent['thread_count']} threads, {agent['project_count']} projects, "
            f"{agent['work_unit_count']} work units, {agent['total_tokens']:,} tokens, ${agent['monthly_cost_mid']:,.2f} monthly midpoint."
        )
        lines.append("What moved:")
        for project in agent["top_projects"][:5]:
            lines.append(
                f"- {project['project_name']}: {project['events']} events, ${project['cost']:,.2f}, {project['tokens']:,} tokens"
            )
        lines.append("Strong signals:")
        lines.extend(_agent_strength_lines(agent_name, agent))
        patterns = agent.get("prompt_effectiveness", {}).get("patterns", [])
        if patterns:
            lines.append("Prompt patterns that worked:")
            for item in sorted(
                patterns,
                key=lambda entry: (entry["execution_delta_vs_baseline"], entry["projects_delta_vs_baseline"]),
                reverse=True,
            )[:3]:
                lines.append(
                    f"- {item['name']}: {item['days']} days, {item['avg_projects']:.2f} projects/day "
                    f"({item['projects_delta_vs_baseline']:+.2f} vs baseline), "
                    f"{item['avg_execution_total']:.2f} execution/day ({item['execution_delta_vs_baseline']:+.2f})"
                )
        lines.append("Tighten next:")
        lines.extend(_agent_tighten_lines(agent))
        high_output_days = agent.get("prompt_effectiveness", {}).get("high_output_days", [])
        if high_output_days:
            lines.append("Highest-output days:")
            for row in high_output_days[:3]:
                lines.append(
                    f"- {row['date']}: {row['prompt_count']} prompts, {row['project_count']} projects, "
                    f"{row['execution_total']} execution actions, top projects {', '.join(row['top_projects']) or 'none'}"
                )
        lines.append("Representative threads:")
        for thread in agent["sample_threads"][:5]:
            title = thread.get("title", "")
            if title:
                lines.append(
                    f"- {thread['project_name']}: ${thread['usage_cost']:,.2f}, {thread['tokens_total']:,} tokens, {title}"
                )
            else:
                lines.append(f"- {thread['project_name']}: ${thread['usage_cost']:,.2f}, {thread['tokens_total']:,} tokens")
        lines.append("")

    lines.extend(
        [
            "## Cross-Agent Read",
            f"- Claude Code currently reads as the breadth/execution engine: {dataset['agents']['claude_code']['project_count']} projects, exact usage accounting, and heavy file/command activity.",
            f"- Codex currently reads as the deep-focus/concentrated thread engine: {dataset['agents']['codex']['thread_count']} threads with high per-thread token depth and visible subagent usage.",
            "- The review question should stay stable: what compounds, what repeats, what creates leverage, and what should be compressed next.",
            "",
        ]
    )
    return "\n".join(lines)


def render_learning_markdown(
    dataset: dict,
    review_relpath: str,
    stats_relpath: str,
    checkpoint_relpath: str,
    impact_relpath: str = "",
    gh_audit_reference_relpath: str = "",
) -> str:
    claude = dataset["agents"]["claude_code"]
    codex = dataset["agents"]["codex"]
    claude_signals = _signal_counts(claude["prompt_metrics"])
    codex_signals = _signal_counts(codex["prompt_metrics"])
    lines = [
        "# Learning",
        "",
        "This file explains how verified review windows are structured so the same math and interpretation do not need to be regenerated every time.",
        "",
        "## Architecture",
        "1. Raw sources stay in local Claude/Codex data stores plus optional `cc-config` logs.",
        "2. Mutable normalized datasets live in `.cache/` and are allowed to refresh.",
        "3. Verified windows are frozen into `checkpoints/<window>/dataset.json` plus `manifest.json`.",
        "4. Human-facing outputs for a verified window are the review, stats, ROI, prompt, and dashboard reports.",
        "5. `review` is the checkpointing command. `stats` is the quick metrics command. `report` remains the lower-level renderer.",
        "",
        "## Latest Verified Window",
        f"- Window: {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        f"- Review: `{review_relpath}`",
        f"- Stats: `{stats_relpath}`",
        f"- Checkpoint: `{checkpoint_relpath}`",
        *([f"- Impact: `{impact_relpath}`"] if impact_relpath else []),
        *([f"- gh-audit reference: `{gh_audit_reference_relpath}`"] if gh_audit_reference_relpath else []),
        "",
        "## Current Learnings",
        f"- Claude Code value is strongest in execution breadth and continuity: {claude['project_count']} projects, {claude['thread_count']} threads, exact cost accounting, and heavy repo/file movement.",
        f"- Codex value is strongest in concentrated deep threads: {codex['thread_count']} threads, {codex['total_tokens']:,} tokens, and {codex['friction_metrics']['subagent_threads']} subagent threads.",
        f"- The learning/report layer is auto-generated from the verified window, including prompt-effectiveness and daily prompt rows.",
        f"- Interview-before-action prompts appear {claude_signals.get('interview_before_action', 0)} times in Claude and {codex_signals.get('interview_before_action', 0)} times in Codex.",
        f"- Verification-first prompts appear {claude_signals.get('verification_first', 0)} times in Claude and {codex_signals.get('verification_first', 0)} times in Codex.",
        f"- Parallel/subagent directives appear {claude_signals.get('parallel_agents', 0)} times in Claude and {codex_signals.get('parallel_agents', 0)} times in Codex.",
        "",
        "## Keep",
        "- Preserve source coverage and checkpoint verified windows instead of re-deriving them ad hoc.",
        "- Treat review files as durable base-zero summaries and stats files as machine-readable checkpoints.",
        "- Keep prompt-effectiveness and per-day prompt rows generated from the same verified dataset as the headline reports.",
        "- Keep ROI and appraisal separate from learning and workflow analysis.",
        "",
        "## Tighten",
        "- Reduce duplicate prompt churn before adding more modeling complexity.",
        "- Continue suppressing command/history prompt noise so directive-signal metrics become cleaner.",
        "- Add more structured execution signals for Codex if future local logs expose them.",
        "",
    ]
    return "\n".join(lines)


def _combined_git_repos(dataset: dict) -> list[dict]:
    by_name: dict[str, dict] = {}
    for agent in dataset["agents"].values():
        for repo in agent["git_evidence"].get("repos", []):
            repo_name = Path(repo.get("repo_root", "")).name or "unknown"
            row = by_name.setdefault(
                repo_name,
                {
                    "name": repo_name,
                    "commit_count": 0,
                    "agents": set(),
                },
            )
            row["commit_count"] = max(row["commit_count"], int(repo.get("commit_count", 0) or 0))
            row["agents"].add(agent["display_name"])
    return [
        {
            "name": name,
            "commit_count": item["commit_count"],
            "agents": sorted(item["agents"]),
        }
        for name, item in by_name.items()
    ]


def _combined_project_activity(dataset: dict) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    for agent in dataset["agents"].values():
        for project in agent["top_projects"]:
            name = project["project_name"]
            item = lookup.setdefault(
                name,
                {
                    "project_name": name,
                    "events": 0,
                    "cost": 0.0,
                    "tokens": 0,
                    "agents": set(),
                },
            )
            item["events"] += int(project.get("events", 0) or 0)
            item["cost"] += float(project.get("cost", 0.0) or 0.0)
            item["tokens"] += int(project.get("tokens", 0) or 0)
            item["agents"].add(agent["display_name"])
    return lookup


def _matched_gh_audit_repos(dataset: dict, gh_audit_reference: dict) -> list[dict]:
    project_lookup = _combined_project_activity(dataset)
    git_lookup = {repo["name"]: repo for repo in _combined_git_repos(dataset)}
    reference_lookup = {repo["name"]: repo for repo in gh_audit_reference.get("repos", [])}
    matched_names = sorted(set(project_lookup) | set(git_lookup))
    matches = []
    for name in matched_names:
        repo_ref = reference_lookup.get(name)
        if not repo_ref:
            continue
        activity = project_lookup.get(
            name,
            {
                "project_name": name,
                "events": 0,
                "cost": 0.0,
                "tokens": 0,
                "agents": set(),
            },
        )
        git_repo = git_lookup.get(name, {"commit_count": 0, "agents": []})
        agents = set(activity.get("agents", set())) | set(git_repo.get("agents", []))
        matches.append(
            {
                "name": name,
                "classification": repo_ref["classification"],
                "language": repo_ref["language"],
                "estimated_value_usd": repo_ref["estimated_value_usd"],
                "raw_estimated_value_usd": repo_ref.get("raw_estimated_value_usd", repo_ref["estimated_value_usd"]),
                "cocomo_cost_usd": repo_ref["cocomo_cost_usd"],
                "market_score": repo_ref["market_score"],
                "portfolio_score": repo_ref["portfolio_score"],
                "leverage_rank": repo_ref["leverage_rank"],
                "leverage_usd_per_kloc": repo_ref["leverage_usd_per_kloc"],
                "confidence_label": repo_ref.get("confidence_label", ""),
                "loc_source": repo_ref.get("loc_source", ""),
                "staff_engineer": repo_ref["staff_engineer"],
                "design_engineer": repo_ref["design_engineer"],
                "ai_ml_researcher": repo_ref["ai_ml_researcher"],
                "finding_count": repo_ref["finding_count"],
                "deep_scanned": repo_ref["deep_scanned"],
                "events": activity.get("events", 0),
                "window_cost": activity.get("cost", 0.0),
                "window_tokens": activity.get("tokens", 0),
                "commit_count": git_repo.get("commit_count", 0),
                "agents": sorted(agents),
            }
        )
    matches.sort(key=lambda item: (item["commit_count"], item["events"], item["estimated_value_usd"]), reverse=True)
    return matches


def render_impact_markdown(dataset: dict, gh_audit_reference: dict | None) -> str:
    claude = dataset["agents"]["claude_code"]
    codex = dataset["agents"]["codex"]
    unique_repos = _combined_git_repos(dataset)
    total_commits = sum(repo["commit_count"] for repo in unique_repos)
    lines = [
        f"# Impact Report - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
        "This report combines the verified eng-journal window with repo-level gh-audit references.",
        "It is intended for portfolio summaries, job applications, and impact framing.",
        "",
        "## Window Scale",
        f"- Claude Code: {claude['active_days']} active days, {claude['project_count']} projects, {claude['thread_count']} threads, {claude['git_evidence']['commit_count']} git commits with evidence",
        f"- Codex: {codex['active_days']} active days, {codex['project_count']} projects, {codex['thread_count']} threads, {codex['git_evidence']['commit_count']} git commits with evidence",
        f"- Unique repos with git evidence across the window: {len(unique_repos)}",
        f"- Total unique-commit evidence across those repos: {total_commits}",
        "",
    ]

    claude_patterns = claude.get("prompt_effectiveness", {}).get("patterns", [])
    codex_patterns = codex.get("prompt_effectiveness", {}).get("patterns", [])
    claude_best = (
        sorted(claude_patterns, key=lambda item: (item["execution_delta_vs_baseline"], item["projects_delta_vs_baseline"]), reverse=True)[0]
        if claude_patterns
        else None
    )
    codex_best = (
        sorted(codex_patterns, key=lambda item: (item["projects_delta_vs_baseline"], item["execution_delta_vs_baseline"]), reverse=True)[0]
        if codex_patterns
        else None
    )

    lines.extend(
        [
            "## Application Framing",
            f"- Operated as an AI-native engineering lead across {len(unique_repos)} repos and {total_commits} git commits in a verified window, with Claude Code acting as the breadth/execution engine and Codex as the deep-thread engine.",
            f"- Shipped across product, design-system, research, and infrastructure-heavy repos rather than a single narrow stack: Claude alone touched {claude['project_count']} projects with exact usage accounting.",
            f"- Verified prompt strategy was not random. Claude's strongest measured output lifts came from `{claude_best['name']}` and Codex's best project-spread signal came from `{codex_best['name']}`."
            if claude_best and codex_best
            else "- Verified prompt strategy is tracked in the review and prompt reports, with highest-output days and directive-signal lift now quantified.",
            f"- Strongest repo clusters in the window included {', '.join(project['project_name'] for project in claude['top_projects'][:4])}.",
            "",
        ]
    )

    if not gh_audit_reference:
        lines.extend(
            [
                "## gh-audit Reference",
                "- No normalized gh-audit reference is imported yet.",
                "- Run `./bin/journal reference gh-audit` to import the latest portfolio report into `references/gh-audit/latest.json`.",
                "",
            ]
        )
        return "\n".join(lines)

    portfolio = gh_audit_reference["portfolio"]
    matched = _matched_gh_audit_repos(dataset, gh_audit_reference)
    matched_value = sum(item["estimated_value_usd"] for item in matched)
    matched_raw_value = sum(item["raw_estimated_value_usd"] for item in matched)
    matched_safe = sum(1 for item in matched if item["classification"] == "SAFE")
    matched_nda = sum(1 for item in matched if "NDA" in item["classification"])

    lines.extend(
        [
            "## gh-audit Reference",
            f"- Source report: `{gh_audit_reference['source_report_path']}`",
            f"- Source timestamp: {gh_audit_reference['source_timestamp'] or 'n/a'}",
            f"- Portfolio reference: {portfolio['total_repos']} repos, ${portfolio['total_portfolio_value_usd']:,.0f} adjusted total, ${portfolio.get('raw_total_portfolio_value_usd', portfolio['total_portfolio_value_usd']):,.0f} raw total, {portfolio['safe_count']} SAFE, {portfolio['nda_count']} NDA_REQUIRED",
            f"- Average valuation confidence: {portfolio.get('average_confidence_score', 0.0) * 100:.1f}%",
            f"- Method flags: {portfolio['loc_outlier_count']} LOC outliers, {portfolio['value_outlier_count']} value outliers, {portfolio['deep_scanned_count']} deep-scanned repos",
            f"- Repos touched in this verified window that match gh-audit by name: {len(matched)}",
            f"- Adjusted gh-audit reference across matched repos: ${matched_value:,.0f}",
            f"- Raw gh-audit reference across matched repos: ${matched_raw_value:,.0f}",
            f"- Matched classifications: {matched_safe} SAFE, {matched_nda} NDA-related",
            "",
            "## Matched Repo References",
        ]
    )
    for item in matched[:12]:
        lines.append(
            f"- {item['name']}: {item['commit_count']} commits, {item['events']} top-project events, "
            f"${item['estimated_value_usd']:,.0f} adjusted ref value (${item['raw_estimated_value_usd']:,.0f} raw), {item['leverage_rank']} leverage, "
            f"{item['confidence_label'] or 'n/a'} confidence via {item['loc_source'] or 'unknown'}, "
            f"{item['classification']}, staff/design/ai {item['staff_engineer']:.0f}/{item['design_engineer']:.0f}/{item['ai_ml_researcher']:.0f}"
        )

    lines.extend(
        [
            "",
            "## Job-Ready Summary Bullets",
        ]
    )
    if matched:
        top_names = ", ".join(item["name"] for item in matched[:4])
        lines.append(
            f"- Built and evolved a multi-repo portfolio across {len(unique_repos)} verified repos / {total_commits} commits, with standardized external repo references available for {len(matched)} repos including {top_names}."
        )
        lines.append(
            f"- Worked on repos that gh-audit currently tags mostly as SAFE and appraises at ${matched_value:,.0f} adjusted replacement-cost reference across the matched set (${matched_raw_value:,.0f} raw); treat that as a repo-asset signal, not a compensation or company valuation claim."
        )
    lines.append(
        f"- Ran a measured AI-assisted engineering workflow with {claude['thread_count'] + codex['thread_count']} total threads in-window, explicit review/checkpointing, and quantified prompt-pattern lift instead of anecdotal prompting."
    )
    lines.append(
        f"- Demonstrated range across app/product work, research systems, and internal tooling, with top active repo clusters including {', '.join(project['project_name'] for project in claude['top_projects'][:5])}."
    )

    lines.extend(
        [
            "",
            "## Method Caveats",
        ]
    )
    for caveat in gh_audit_reference.get("method_caveats", []):
        lines.append(f"- {caveat}")
    lines.extend(
        [
            "- For hiring or portfolio use, the safest framing is output scale, repo breadth, commit evidence, and matched repo references, not a single portfolio-dollar headline.",
            "",
        ]
    )
    return "\n".join(lines)


def render_scheduler_status_markdown(schedule_status: dict, refresh_state: dict | None) -> str:
    lines = [
        "# Scheduler Status",
        "",
        "This report tracks the local auto-refresh loop for gh-audit imports and review regeneration.",
        "",
        "## Schedule",
        f"- Runner: {schedule_status.get('runner', 'unknown')}",
        f"- Installed: {'yes' if schedule_status.get('installed') else 'no'}",
        f"- Path: `{schedule_status.get('path', '')}`" if schedule_status.get("path") else "- Path: n/a",
        f"- Log: `{schedule_status.get('log_path', '')}`" if schedule_status.get("log_path") else "- Log: n/a",
    ]
    if schedule_status.get("installed"):
        cadence = str(schedule_status.get("cadence", "") or "")
        hour = schedule_status.get("hour")
        minute = schedule_status.get("minute")
        weekday = str(schedule_status.get("weekday", "") or "")
        if cadence:
            timing = f"{cadence}"
            if cadence == "weekly" and weekday:
                timing += f" on {weekday}"
            if hour is not None and minute is not None:
                timing += f" at {int(hour):02d}:{int(minute):02d}"
            lines.append(f"- Timing: {timing}")
        if schedule_status.get("state"):
            lines.append(f"- Runtime state: {schedule_status['state']}")
        if schedule_status.get("runs") is not None:
            lines.append(f"- Launch count: {schedule_status['runs']}")
        if schedule_status.get("command"):
            lines.append(f"- Command: `{schedule_status['command']}`")
    lines.extend(["", "## Last Refresh"])
    if not refresh_state:
        lines.append("- No refresh state recorded yet.")
        return "\n".join(lines) + "\n"
    lines.append(f"- Status: {refresh_state.get('status', 'unknown')}")
    lines.append(f"- Started at: {refresh_state.get('started_at', 'n/a')}")
    lines.append(f"- Completed at: {refresh_state.get('completed_at', 'n/a')}")
    if refresh_state.get("window"):
        window = refresh_state["window"]
        lines.append(f"- Window: {window.get('start_date', 'n/a')} to {window.get('end_date', 'n/a')}")
    lines.append(f"- gh-audit scan: {'yes' if refresh_state.get('scan_gh_audit') else 'no'}")
    if "keep_windows" in refresh_state:
        lines.append(f"- Retention: keep latest {refresh_state.get('keep_windows')} window(s)")
    if "pruned_paths" in refresh_state:
        lines.append(f"- Pruned paths: {len(refresh_state.get('pruned_paths') or [])}")
    if refresh_state.get("gh_audit_source_path"):
        lines.append(f"- gh-audit source: `{refresh_state['gh_audit_source_path']}`")
    if refresh_state.get("reference_path"):
        lines.append(f"- Imported reference: `{refresh_state['reference_path']}`")
    if refresh_state.get("scheduler_report_path"):
        lines.append(f"- Scheduler report: `{refresh_state['scheduler_report_path']}`")
    if refresh_state.get("error"):
        lines.append(f"- Error: {refresh_state['error']}")
    return "\n".join(lines) + "\n"


def _appraisal_metrics(dataset: dict) -> dict[str, float]:
    claude = dataset["agents"]["claude_code"]
    codex = dataset["agents"]["codex"]
    period_compute_mid = float(claude["cost_mid"]) + float(codex["cost_mid"])
    monthly_compute_mid = float(claude["monthly_cost_mid"]) + float(codex["monthly_cost_mid"])
    commits = int(claude["git_evidence"]["commit_count"]) + int(codex["git_evidence"]["commit_count"])
    repos = int(claude["git_evidence"]["repo_count"]) + int(codex["git_evidence"]["repo_count"])
    projects = int(claude["project_count"]) + int(codex["project_count"])
    active_days = int(claude["active_days"]) + int(codex["active_days"])
    period_days = int(dataset["window"]["period_days"])

    conservative = (period_compute_mid * 10.0) + (commits * 25.0) + (projects * 200.0) + (repos * 300.0)
    base = (period_compute_mid * 20.0) + (commits * 75.0) + (projects * 600.0) + (repos * 900.0)
    aggressive = (period_compute_mid * 45.0) + (commits * 180.0) + (projects * 1600.0) + (repos * 2400.0)

    return {
        "period_compute_mid": period_compute_mid,
        "monthly_compute_mid": monthly_compute_mid,
        "commits": commits,
        "repos": repos,
        "projects": projects,
        "active_days": active_days,
        "period_days": period_days,
        "conservative": conservative,
        "base": base,
        "aggressive": aggressive,
        "conservative_monthly": conservative / max((period_days / 30.4375), 0.0001),
        "base_monthly": base / max((period_days / 30.4375), 0.0001),
        "aggressive_monthly": aggressive / max((period_days / 30.4375), 0.0001),
    }


def _scale_bar(value: float, max_value: float, width: int = 24) -> str:
    if max_value <= 0:
        return "." * width
    filled = max(1 if value > 0 else 0, round((value / max_value) * width))
    filled = min(width, filled)
    return "#" * filled + "." * (width - filled)


def _ascii_row(columns: list[tuple[str, int]], values: list[str]) -> str:
    parts = []
    for value, (_, width) in zip(values, columns):
        parts.append(value.ljust(width)[:width])
    return "| " + " | ".join(parts) + " |"


def render_dashboard_ascii(dataset: dict) -> str:
    window_label = f"window {dataset['window']['start_date']} -> {dataset['window']['end_date']}"
    cols = [
        ("agent", 14),
        ("days", 4),
        ("projects", 8),
        ("threads", 7),
        ("tokens", 14),
        ("mid cost", 10),
        ("month mid", 10),
        ("confidence", 15),
    ]
    header_row = _ascii_row(cols, [name for name, _ in cols])
    width = len(header_row)
    border = "+" + "-" * (width - 2) + "+"
    inner = width - 4
    lines = [
        border,
        f"| {'eng-journal :: ascii analytics dashboard'.ljust(inner)} |",
        f"| {window_label.ljust(inner)} |",
        border,
    ]
    lines.append(header_row)
    lines.append(border)

    for key in ("claude_code", "codex"):
        agent = dataset["agents"][key]
        lines.append(
            _ascii_row(
                cols,
                [
                    agent["display_name"],
                    str(agent["active_days"]),
                    str(agent["project_count"]),
                    str(agent["thread_count"]),
                    f"{agent['total_tokens']:,}",
                    f"${agent['cost_mid']:,.0f}",
                    f"${agent['monthly_cost_mid']:,.0f}",
                    agent["cost_confidence"],
                ],
            )
        )
    lines.append(border)
    lines.append("")

    lines.append("SOURCE COVERAGE")
    for key in ("claude_code", "codex"):
        agent = dataset["agents"][key]
        coverage = ", ".join(agent.get("source_coverage", [])) or "none"
        lines.append(f"  {agent['display_name']}: {coverage}")
    lines.append("")

    lines.append("WEEKLY COST SHAPE")
    for key in ("claude_code", "codex"):
        agent = dataset["agents"][key]
        max_cost = max((row["cost"] for row in agent["weekly_rows"]), default=0.0)
        lines.append(f"{agent['display_name']}:")
        for row in agent["weekly_rows"]:
            bar = _scale_bar(float(row["cost"]), float(max_cost), width=28)
            lines.append(f"  {row['week']}  [{bar}]  ${row['cost']:>7.2f}")
        lines.append("")

    lines.append("TOP PROJECTS")
    for key in ("claude_code", "codex"):
        agent = dataset["agents"][key]
        lines.append(f"{agent['display_name']}:")
        for project in agent["top_projects"][:5]:
            lines.append(
                f"  - {project['project_name'][:24].ljust(24)}  events={project['events']:>5}  cost=${project['cost']:>8.2f}  tokens={project['tokens']:>12,}"
            )
        lines.append("")

    appraisal = _appraisal_metrics(dataset)
    lines.append("BONUS :: CORE VALUE")
    lines.append(f"  conservative={appraisal['conservative']:,.0f}  base={appraisal['base']:,.0f}  aggressive={appraisal['aggressive']:,.0f}")
    lines.append(f"  monthly-band={appraisal['conservative_monthly']:,.0f} -> {appraisal['aggressive_monthly']:,.0f}")
    lines.append("  note=keep roi and appraisal separate; this is option value, not company valuation")
    return "\n".join(lines) + "\n"


def render_appraisal_markdown(dataset: dict) -> str:
    appraisal = _appraisal_metrics(dataset)

    candidates = []
    for _, agent in dataset["agents"].items():
        for project in agent["top_projects"][:8]:
            candidates.append(
                {
                    "agent": agent["display_name"],
                    "project_name": project["project_name"],
                    "cost": float(project.get("cost", 0.0) or 0.0),
                    "events": int(project.get("events", 0) or 0),
                    "tokens": int(project.get("tokens", 0) or 0),
                }
            )
    candidates.sort(key=lambda item: (item["cost"], item["events"], item["tokens"]), reverse=True)

    lines = [
        f"# Appraisal Report - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
        "This report appraises the observed work as a portfolio of build assets and future options.",
        "It is not a market transaction price, not an equity valuation, and not support for a nine-figure claim.",
        "",
        "## Evidence Base",
        f"- Period compute midpoint: ${appraisal['period_compute_mid']:,.2f}",
        f"- Monthlyized compute midpoint: ${appraisal['monthly_compute_mid']:,.2f}",
        f"- Active days observed: {appraisal['active_days']}",
        f"- Projects touched: {appraisal['projects']}",
        f"- Git repos with evidence: {appraisal['repos']}",
        f"- Git commits in window: {appraisal['commits']}",
        "",
        "## Scenario Bands",
        f"- Conservative replacement value: ${appraisal['conservative']:,.0f}",
        f"- Base appraisal value: ${appraisal['base']:,.0f}",
        f"- Aggressive option value: ${appraisal['aggressive']:,.0f}",
        "",
        "## Interpretation",
        "- Conservative means: what it would plausibly cost to recreate the observed delivery, continuity, and telemetry with a competent small team.",
        "- Base means: replacement cost plus meaningful portfolio continuity and future leverage from reusable work and instrumentation.",
        "- Aggressive means: option value if a few of the strongest repos or workflows compound into products, consulting leverage, or acquisition-quality internal tools.",
        "- The current local evidence does not justify a $350M portfolio valuation. That number would require demonstrated revenue, distribution, proprietary data advantages, or strategic buyers.",
        "",
        "## Option Carriers",
    ]
    for item in candidates[:12]:
        lines.append(
            f"- {item['project_name']} via {item['agent']}: ${item['cost']:,.2f} cost proxy, {item['events']} events, {item['tokens']:,} tokens"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "- Keep the separation. Use ROI for tool economics and keep appraisal as a separate portfolio/options lens.",
            "- If you want this to become more defensible, the next step is to add revenue, user, deployment, and adoption evidence into the appraisal model.",
            "",
        ]
    )
    return "\n".join(lines)


def render_core_value_markdown(dataset: dict) -> str:
    appraisal = _appraisal_metrics(dataset)
    lines = [
        f"# Core Value Report - {dataset['window']['start_date']} to {dataset['window']['end_date']}",
        "",
        "This report answers a narrower question than the appraisal report: what does the last-two-month window suggest about your core builder value?",
        "",
        "## Core Read",
        "- You read like an AI-native founder-operator / technical creative director, not just an implementation engineer.",
        "- The strongest signal is cross-project continuity plus willingness to push parallel, high-context, design-heavy, and systems-heavy work in the same window.",
        "- The machine evidence supports strong builder leverage. It does not support a nine-figure personal valuation from telemetry alone.",
        "",
        "## Value Bands",
        f"- Observed portfolio value created in-window: ${appraisal['conservative']:,.0f} to ${appraisal['aggressive']:,.0f}",
        f"- Base portfolio value created in-window: ${appraisal['base']:,.0f}",
        f"- Monthlyized creation band from this window: ${appraisal['conservative_monthly']:,.0f} to ${appraisal['aggressive_monthly']:,.0f}",
        f"- Monthlyized base creation rate: ${appraisal['base_monthly']:,.0f}",
        "",
        "## Personal Worth Lens",
        "- Cash-comp builder lens: strong evidence for high-end founding-engineer / technical creative leadership value rather than commodity contractor pricing.",
        "- Option-value lens: the upside is in compounding the strongest repos into distribution, recurring revenue, or strategic internal tooling, not in the raw repo count alone.",
        "- Defensible current statement: your observed output window supports a serious low-six to low-seven figure portfolio-value story, not a $350M story.",
        "",
        "## Bonus",
        "- Bonus appraisal stays separate from ROI because tool economics and personal/portfolio value are different decisions.",
        "- Bonus option carriers come from the same project set surfaced in the appraisal report.",
        "",
    ]
    return "\n".join(lines)


def roi_input_payload(dataset: dict) -> dict:
    return {
        "window": dataset["window"],
        "generated_at": dataset["generated_at"],
        "subscription_scenarios": dataset["subscription_scenarios"],
        "agents": list(dataset["agents"].values()),
    }


def render_roi_markdown(repo_root: Path, dataset: dict, start_date: str, end_date: str) -> str:
    cache_dir = repo_root / ".cache"
    cache_dir.mkdir(exist_ok=True)
    input_path = cache_dir / f"roi-{start_date}-to-{end_date}.sexp"
    output_path = cache_dir / f"roi-{start_date}-to-{end_date}.md"
    write_sexp(input_path, roi_input_payload(dataset))
    result = subprocess.run(
        ["sbcl", "--script", str(repo_root / "lisp" / "roi-core.lisp"), str(input_path), str(output_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"SBCL ROI render failed: {result.stderr.strip()}")
    return output_path.read_text(encoding="utf-8")


def write_report(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
