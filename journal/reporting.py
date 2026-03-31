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
        lines.append(f"## {row['agent']}")
        lines.append(f"- Events: {row['events']}")
        lines.append(f"- Threads: {row['thread_count']}")
        lines.append(f"- Projects: {row['project_count']}")
        lines.append(f"- Cost proxy: ${row['cost']:.2f}")
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
        lines.append(f"- Duplicate prompt instances: {prompt_metrics['duplicate_prompt_instances']}")
        if prompt_metrics["tags"]:
            lines.append("- Top semantic tags: " + ", ".join(f"{item['name']} ({item['count']})" for item in prompt_metrics["tags"]))
        if prompt_metrics.get("directive_signals"):
            lines.append("- Directive signals: " + ", ".join(f"{item['name']} ({item['count']})" for item in prompt_metrics["directive_signals"]))
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
        if agent["prompt_metrics"].get("directive_signals"):
            lines.append(
                "- Directive signals: "
                + ", ".join(f"{item['name']} ({item['count']})" for item in agent["prompt_metrics"]["directive_signals"])
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
        lines.append("Tighten next:")
        lines.extend(_agent_tighten_lines(agent))
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
        "",
        "## Current Learnings",
        f"- Claude Code value is strongest in execution breadth and continuity: {claude['project_count']} projects, {claude['thread_count']} threads, exact cost accounting, and heavy repo/file movement.",
        f"- Codex value is strongest in concentrated deep threads: {codex['thread_count']} threads, {codex['total_tokens']:,} tokens, and {codex['friction_metrics']['subagent_threads']} subagent threads.",
        f"- Interview-before-action prompts appear {claude_signals.get('interview_before_action', 0)} times in Claude and {codex_signals.get('interview_before_action', 0)} times in Codex.",
        f"- Verification-first prompts appear {claude_signals.get('verification_first', 0)} times in Claude and {codex_signals.get('verification_first', 0)} times in Codex.",
        f"- Parallel/subagent directives appear {claude_signals.get('parallel_agents', 0)} times in Claude and {codex_signals.get('parallel_agents', 0)} times in Codex.",
        "",
        "## Keep",
        "- Preserve source coverage and checkpoint verified windows instead of re-deriving them ad hoc.",
        "- Treat review files as durable base-zero summaries and stats files as machine-readable checkpoints.",
        "- Keep ROI and appraisal separate from learning and workflow analysis.",
        "",
        "## Tighten",
        "- Reduce duplicate prompt churn before adding more modeling complexity.",
        "- Continue suppressing command/history prompt noise so directive-signal metrics become cleaner.",
        "- Add more structured execution signals for Codex if future local logs expose them.",
        "",
    ]
    return "\n".join(lines)


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
