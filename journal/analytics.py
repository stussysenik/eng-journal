from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from .claude import load_claude_window
from .codex import load_codex_window
from .config import SUBSCRIPTION_SCENARIOS, Paths
from .git_insights import gather_git_evidence
from .util import compact_text, dedupe_key, is_mega_prompt, keyword_tags, mean, month_fraction


def _top_counter(counter: Counter, limit: int = 8) -> list[dict]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def summarize_prompt_events(prompt_events: list[dict]) -> dict:
    prompt_lengths = [event.get("prompt_length", 0) for event in prompt_events if event.get("prompt_text")]
    duplicate_counter: Counter[str] = Counter()
    duplicate_texts: dict[str, str] = {}
    tag_counter: Counter[str] = Counter()

    for event in prompt_events:
        text = (event.get("prompt_text") or "").strip()
        if not text:
            continue
        key = dedupe_key(text)
        duplicate_counter[key] += 1
        duplicate_texts.setdefault(key, text)
        for tag in keyword_tags(text):
            tag_counter[tag] += 1

    duplicate_instances = sum(max(count - 1, 0) for count in duplicate_counter.values())
    duplicates = [
        {"count": count, "prompt": compact_text(duplicate_texts[key], 160)}
        for key, count in duplicate_counter.most_common()
        if count > 1
    ][:10]
    longest = [
        {
            "project_name": event.get("project_name", "unknown"),
            "prompt_length": event.get("prompt_length", 0),
            "prompt": compact_text(event.get("prompt_text", ""), 200),
        }
        for event in sorted(prompt_events, key=lambda item: item.get("prompt_length", 0), reverse=True)[:10]
    ]
    mega_count = sum(1 for event in prompt_events if is_mega_prompt(event.get("prompt_text", "")))

    return {
        "total_prompts": len(prompt_events),
        "avg_prompt_length": round(mean(prompt_lengths), 1),
        "mega_prompt_count": mega_count,
        "duplicate_prompt_instances": duplicate_instances,
        "duplicates": duplicates,
        "longest": longest,
        "tags": _top_counter(tag_counter),
    }


def _summarize_projects_from_events(events: list[dict], cost_field: str | None = None, token_field: str | None = None) -> list[dict]:
    projects: dict[str, dict] = {}
    for event in events:
        name = event.get("project_name") or "unknown"
        stats = projects.setdefault(name, {"project_name": name, "events": 0, "cost": 0.0, "tokens": 0})
        stats["events"] += 1
        if cost_field:
            stats["cost"] += float(event.get(cost_field, 0) or 0.0)
        if token_field:
            stats["tokens"] += int(event.get(token_field, 0) or 0)
    ranked = sorted(projects.values(), key=lambda item: (item["cost"], item["events"], item["tokens"]), reverse=True)
    return ranked[:10]


def _daily_rows(agent: str, events: list[dict], cost_field: str | None = None) -> list[dict]:
    per_day: dict[str, dict] = {}
    for event in events:
        date = event.get("date")
        if not date:
            continue
        row = per_day.setdefault(
            date,
            {
                "date": date,
                "agent": agent,
                "events": 0,
                "threads": set(),
                "projects": set(),
                "cost": 0.0,
            },
        )
        row["events"] += 1
        thread_id = event.get("thread_id")
        if thread_id:
            row["threads"].add(thread_id)
        project_name = event.get("project_name")
        if project_name:
            row["projects"].add(project_name)
        if cost_field:
            row["cost"] += float(event.get(cost_field, 0) or 0.0)
    return [
        {
            "date": date,
            "agent": row["agent"],
            "events": row["events"],
            "thread_count": len(row["threads"]),
            "project_count": len(row["projects"]),
            "cost": round(row["cost"], 4),
        }
        for date, row in sorted(per_day.items())
    ]


def _weekly_rows(daily_rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in daily_rows:
        date_obj = dt.date.fromisoformat(row["date"])
        week_key = f"{date_obj.isocalendar().year}-W{date_obj.isocalendar().week:02d}"
        item = grouped.setdefault(
            week_key,
            {"week": week_key, "agent": row["agent"], "days_active": 0, "events": 0, "threads": 0, "projects": 0, "cost": 0.0},
        )
        item["days_active"] += 1
        item["events"] += row["events"]
        item["threads"] += row["thread_count"]
        item["projects"] = max(item["projects"], row["project_count"])
        item["cost"] += row["cost"]
    return [grouped[key] for key in sorted(grouped)]


def _summarize_claude(paths: Paths, start_date: str, end_date: str, data: dict) -> dict:
    prompt_events = data["prompt_events"]
    usage_events = data["usage_events"]
    tool_events = data["tool_events"]
    threads = data["threads"]
    all_events = prompt_events + usage_events + tool_events
    prompt_metrics = summarize_prompt_events(prompt_events)
    model_mix = Counter(event.get("model", "") for event in usage_events if event.get("model"))
    action_mix = Counter(event.get("action", "") for event in tool_events if event.get("action"))
    project_paths = [event.get("project_path", "") for event in all_events if event.get("project_path")]
    git_evidence = gather_git_evidence(project_paths, start_date, end_date)
    period_fraction = month_fraction(start_date, end_date)
    total_cost = round(sum(float(event.get("cost_actual", 0) or 0.0) for event in usage_events), 4)
    total_tokens = sum(int(event.get("total_tokens", 0) or 0) for event in usage_events)
    work_units = len({(event.get("project_name"), event.get("date")) for event in all_events if event.get("project_name") and event.get("date")})
    cost_confidence = "exact" if usage_events else ("history_only" if all_events else "no_data")

    return {
        "name": "claude_code",
        "display_name": "Claude Code",
        "cost_confidence": cost_confidence,
        "source_coverage": data.get("source_coverage", []),
        "active_days": len({event.get("date") for event in all_events if event.get("date")}),
        "thread_count": len({thread["thread_id"] for thread in threads}),
        "project_count": len({event.get("project_name") for event in all_events if event.get("project_name")}),
        "work_unit_count": work_units,
        "total_tokens": total_tokens,
        "cost_low": total_cost,
        "cost_mid": total_cost,
        "cost_high": total_cost,
        "monthly_cost_low": round(total_cost / period_fraction, 4),
        "monthly_cost_mid": round(total_cost / period_fraction, 4),
        "monthly_cost_high": round(total_cost / period_fraction, 4),
        "prompt_metrics": prompt_metrics,
        "model_mix": _top_counter(model_mix),
        "reasoning_mix": [],
        "execution_metrics": {
            "created_file": action_mix.get("created_file", 0),
            "modified_file": action_mix.get("modified_file", 0),
            "read_file": action_mix.get("read_file", 0),
            "delegated": action_mix.get("delegated", 0),
            "ran_command": action_mix.get("ran_command", 0),
            "web_search": action_mix.get("web_search", 0) + action_mix.get("web_fetch", 0),
        },
        "friction_metrics": {
            "error_count": 0,
            "warning_count": 0,
            "apply_patch_failures": 0,
            "subagent_threads": 0,
        },
        "git_evidence": git_evidence,
        "top_projects": _summarize_projects_from_events(usage_events or all_events, cost_field="cost_actual", token_field="total_tokens"),
        "daily_rows": _daily_rows("claude_code", usage_events or all_events, cost_field="cost_actual"),
        "weekly_rows": _weekly_rows(_daily_rows("claude_code", usage_events or all_events, cost_field="cost_actual")),
        "sample_threads": [
            {
                "project_name": thread.get("project_name", "unknown"),
                "thread_id": thread.get("thread_id", ""),
                "tokens_total": thread.get("tokens_total", 0),
                "usage_cost": round(float(thread.get("usage_cost", 0.0) or 0.0), 4),
            }
            for thread in sorted(threads, key=lambda item: item.get("usage_cost", 0.0), reverse=True)[:10]
        ],
    }


def _summarize_codex(paths: Paths, start_date: str, end_date: str, data: dict) -> dict:
    threads = data["threads"]
    prompt_events = data["prompt_events"]
    thread_events = data["thread_events"]
    prompt_metrics = summarize_prompt_events(prompt_events)
    model_mix = Counter(thread.get("model", "") for thread in threads if thread.get("model"))
    reasoning_mix = Counter(thread.get("reasoning_effort", "") for thread in threads if thread.get("reasoning_effort"))
    project_paths = [thread.get("project_path", "") for thread in threads if thread.get("project_path")]
    git_evidence = gather_git_evidence(project_paths, start_date, end_date)
    period_fraction = month_fraction(start_date, end_date)
    total_tokens = sum(int(thread.get("tokens_used", 0) or 0) for thread in threads)
    total_low = round(sum(float(thread.get("cost_low", 0.0) or 0.0) for thread in threads), 4)
    total_mid = round(sum(float(thread.get("cost_mid", 0.0) or 0.0) for thread in threads), 4)
    total_high = round(sum(float(thread.get("cost_high", 0.0) or 0.0) for thread in threads), 4)
    work_units = len({(thread.get("project_name"), thread.get("date")) for thread in threads if thread.get("project_name") and thread.get("date")})
    cost_confidence = "estimated_range" if threads else ("history_only" if prompt_events else "no_data")

    return {
        "name": "codex",
        "display_name": "Codex",
        "cost_confidence": cost_confidence,
        "source_coverage": data.get("source_coverage", []),
        "active_days": len({thread.get("date") for thread in threads if thread.get("date")}),
        "thread_count": len(threads),
        "project_count": len({thread.get("project_name") for thread in threads if thread.get("project_name")}),
        "work_unit_count": work_units,
        "total_tokens": total_tokens,
        "cost_low": total_low,
        "cost_mid": total_mid,
        "cost_high": total_high,
        "monthly_cost_low": round(total_low / period_fraction, 4),
        "monthly_cost_mid": round(total_mid / period_fraction, 4),
        "monthly_cost_high": round(total_high / period_fraction, 4),
        "prompt_metrics": prompt_metrics,
        "model_mix": _top_counter(model_mix),
        "reasoning_mix": _top_counter(reasoning_mix),
        "execution_metrics": {
            "created_file": 0,
            "modified_file": 0,
            "read_file": 0,
            "delegated": 0,
            "ran_command": 0,
            "web_search": 0,
        },
        "friction_metrics": {
            "error_count": sum(thread.get("errors", 0) for thread in threads),
            "warning_count": sum(thread.get("warnings", 0) for thread in threads),
            "apply_patch_failures": sum(thread.get("apply_patch_failures", 0) for thread in threads),
            "subagent_threads": sum(1 for thread in threads if thread.get("subagent")),
        },
        "git_evidence": git_evidence,
        "top_projects": _summarize_projects_from_events(thread_events, cost_field="cost_mid", token_field="tokens_used"),
        "daily_rows": _daily_rows("codex", thread_events, cost_field="cost_mid"),
        "weekly_rows": _weekly_rows(_daily_rows("codex", thread_events, cost_field="cost_mid")),
        "sample_threads": [
            {
                "project_name": thread.get("project_name", "unknown"),
                "thread_id": thread.get("thread_id", ""),
                "tokens_total": thread.get("tokens_used", 0),
                "usage_cost": round(float(thread.get("cost_mid", 0.0) or 0.0), 4),
                "title": compact_text(thread.get("title", ""), 120),
            }
            for thread in sorted(threads, key=lambda item: item.get("cost_mid", 0.0), reverse=True)[:12]
        ],
    }


def build_period_dataset(paths: Paths, start_date: str, end_date: str) -> dict:
    claude_data = load_claude_window(paths, start_date, end_date)
    codex_data = load_codex_window(paths, start_date, end_date)
    claude_summary = _summarize_claude(paths, start_date, end_date, claude_data)
    codex_summary = _summarize_codex(paths, start_date, end_date, codex_data)
    generated_at = dt.datetime.now(dt.UTC).isoformat()
    all_daily = sorted(claude_summary["daily_rows"] + codex_summary["daily_rows"], key=lambda row: (row["date"], row["agent"]))
    return {
        "generated_at": generated_at,
        "window": {
            "start_date": start_date,
            "end_date": end_date,
            "period_days": (dt.date.fromisoformat(end_date) - dt.date.fromisoformat(start_date)).days + 1,
            "month_fraction": month_fraction(start_date, end_date),
        },
        "subscription_scenarios": [
            {"label": scenario.label, "monthly_cost": scenario.monthly_cost}
            for scenario in SUBSCRIPTION_SCENARIOS
        ],
        "agents": {
            "claude_code": claude_summary,
            "codex": codex_summary,
        },
        "daily_rows": all_daily,
    }


def write_period_dataset(paths: Paths, start_date: str, end_date: str, dataset: dict) -> Path:
    slug = f"{start_date}_to_{end_date}"
    target = paths.cache_dir / f"{slug}.json"
    target.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    return target
