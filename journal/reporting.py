from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path

from .serialization import write_sexp
from .util import compact_text


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


def render_appraisal_markdown(dataset: dict) -> str:
    claude = dataset["agents"]["claude_code"]
    codex = dataset["agents"]["codex"]
    period_compute_mid = float(claude["cost_mid"]) + float(codex["cost_mid"])
    monthly_compute_mid = float(claude["monthly_cost_mid"]) + float(codex["monthly_cost_mid"])
    commits = int(claude["git_evidence"]["commit_count"]) + int(codex["git_evidence"]["commit_count"])
    repos = int(claude["git_evidence"]["repo_count"]) + int(codex["git_evidence"]["repo_count"])
    projects = int(claude["project_count"]) + int(codex["project_count"])
    active_days = int(claude["active_days"]) + int(codex["active_days"])

    conservative = (period_compute_mid * 10.0) + (commits * 25.0) + (projects * 200.0) + (repos * 300.0)
    base = (period_compute_mid * 20.0) + (commits * 75.0) + (projects * 600.0) + (repos * 900.0)
    aggressive = (period_compute_mid * 45.0) + (commits * 180.0) + (projects * 1600.0) + (repos * 2400.0)

    candidates = []
    for agent_key, agent in dataset["agents"].items():
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
        f"- Period compute midpoint: ${period_compute_mid:,.2f}",
        f"- Monthlyized compute midpoint: ${monthly_compute_mid:,.2f}",
        f"- Active days observed: {active_days}",
        f"- Projects touched: {projects}",
        f"- Git repos with evidence: {repos}",
        f"- Git commits in window: {commits}",
        "",
        "## Scenario Bands",
        f"- Conservative replacement value: ${conservative:,.0f}",
        f"- Base appraisal value: ${base:,.0f}",
        f"- Aggressive option value: ${aggressive:,.0f}",
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
