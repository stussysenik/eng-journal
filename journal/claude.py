from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path

from .config import Paths, discover_sources
from .pricing import calculate_claude_cost
from .util import compact_text, dedupe_key, keyword_tags, parse_iso_timestamp, project_name_from_path, utc_dt_from_unixish, within_window


def _iter_claude_log_files(projects_dir: Path | None) -> list[Path]:
    if not projects_dir or not projects_dir.exists():
        return []
    return sorted(projects_dir.glob("**/*.jsonl"))


def _bounds_dict(first_ts: dt.datetime | None, last_ts: dt.datetime | None) -> dict:
    return {
        "first_date": first_ts.date().isoformat() if first_ts else "",
        "last_date": last_ts.date().isoformat() if last_ts else "",
    }


def _native_log_bounds(projects_dir: Path | None) -> dict:
    first_ts = None
    last_ts = None
    for log_file in _iter_claude_log_files(projects_dir):
        try:
            with log_file.open(encoding="utf-8") as handle:
                for raw_line in handle:
                    if not raw_line.strip():
                        continue
                    try:
                        data = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    timestamp = parse_iso_timestamp(data.get("timestamp", ""))
                    if not timestamp:
                        continue
                    if first_ts is None or timestamp < first_ts:
                        first_ts = timestamp
                    if last_ts is None or timestamp > last_ts:
                        last_ts = timestamp
        except OSError:
            continue
    return _bounds_dict(first_ts, last_ts)


def _history_bounds(history_path: Path | None) -> dict:
    first_ts = None
    last_ts = None
    if not history_path or not history_path.exists():
        return _bounds_dict(None, None)
    try:
        with history_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                timestamp = utc_dt_from_unixish(payload.get("timestamp"))
                if not timestamp:
                    continue
                if first_ts is None or timestamp < first_ts:
                    first_ts = timestamp
                if last_ts is None or timestamp > last_ts:
                    last_ts = timestamp
    except OSError:
        return _bounds_dict(None, None)
    return _bounds_dict(first_ts, last_ts)


def _journal_log_bounds(logs_dir: Path | None) -> dict:
    if not logs_dir or not logs_dir.exists():
        return _bounds_dict(None, None)
    dates = sorted(path.stem for path in logs_dir.glob("*.jsonl") if path.stem.count("-") == 2)
    if not dates:
        return _bounds_dict(None, None)
    return {
        "first_date": dates[0],
        "last_date": dates[-1],
    }


def _parse_tool_event(item: dict, base: dict) -> dict | None:
    tool_name = item.get("name", "")
    inputs = item.get("input", {}) or {}
    action = {
        "Write": "created_file",
        "Edit": "modified_file",
        "Read": "read_file",
        "Glob": "searched_code",
        "Grep": "searched_code",
        "Bash": "ran_command",
        "Task": "delegated",
        "TaskCreate": "task_planned",
        "TaskUpdate": "task_completed" if inputs.get("status") == "completed" else "task_updated",
        "TodoWrite": "planned_tasks",
        "WebFetch": "web_fetch",
        "WebSearch": "web_search",
    }.get(tool_name, "tool_use")
    target = (
        inputs.get("file_path")
        or inputs.get("command")
        or inputs.get("query")
        or inputs.get("url")
        or inputs.get("prompt")
        or inputs.get("description")
        or inputs.get("subject")
        or inputs.get("taskId")
        or ""
    )
    return {
        **base,
        "event_kind": "tool_use",
        "tool_name": tool_name,
        "action": action,
        "target": compact_text(str(target), 240),
    }


def _extract_user_prompt_text(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if value.get("type") == "tool_result":
            return ""
        return _extract_user_prompt_text(value.get("content", ""))
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                continue
            part = _extract_user_prompt_text(item)
            if part:
                parts.append(part)
        return "\n".join(parts).strip()
    return str(value).strip()


def _is_noise_prompt(text: str) -> bool:
    lowered = text.strip().lower()
    if not lowered:
        return True
    noise_prefixes = (
        "<local-command-",
        "<command-name>",
        "<command-message>",
        "<command-args>",
    )
    if lowered.startswith(noise_prefixes):
        return True
    if lowered.startswith("your task is to create a detailed summary of the conversation so far"):
        return True
    if lowered in {"/clear", "/compact", "/exit", "continue"}:
        return True
    return False


def _prompt_signature(event: dict) -> tuple[str, str, str]:
    return (
        event.get("date", ""),
        event.get("project_path") or event.get("project_name") or "unknown",
        dedupe_key(compact_text(event.get("prompt_text", ""), 220)),
    )


def _tool_signature(event: dict) -> tuple[str, str, str, str]:
    return (
        event.get("date", ""),
        event.get("project_path") or event.get("project_name") or "unknown",
        event.get("action", ""),
        compact_text(event.get("target", ""), 220).lower(),
    )


def _merge_unique_events(primary: list[dict], secondary: list[dict], signature_fn) -> list[dict]:
    merged = list(primary)
    seen = {signature_fn(event) for event in merged}
    for event in secondary:
        key = signature_fn(event)
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)
    return merged


def _load_claude_history_prompts(history_path: Path | None, start_date: str, end_date: str) -> list[dict]:
    prompt_events: list[dict] = []
    if not history_path or not history_path.exists():
        return prompt_events
    try:
        with history_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                try:
                    payload = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                timestamp = utc_dt_from_unixish(payload.get("timestamp"))
                if not timestamp:
                    continue
                date_str = timestamp.date().isoformat()
                if not within_window(date_str, start_date, end_date):
                    continue
                prompt_text = str(payload.get("display", "")).strip()
                if not prompt_text or _is_noise_prompt(prompt_text):
                    continue
                project_path = str(payload.get("project", "") or "")
                prompt_events.append(
                    {
                        "agent": "claude_code",
                        "provider": "anthropic",
                        "thread_id": "",
                        "timestamp": timestamp.isoformat(),
                        "date": date_str,
                        "project_path": project_path,
                        "project_name": project_name_from_path(project_path),
                        "git_branch": "",
                        "event_kind": "prompt",
                        "prompt_text": prompt_text,
                        "prompt_length": len(prompt_text),
                        "source_kind": "history",
                    }
                )
    except OSError:
        return []
    return prompt_events


def _timestamp_from_date_and_time(date_str: str, time_str: str) -> str:
    try:
        return dt.datetime.fromisoformat(f"{date_str}T{time_str}").isoformat()
    except ValueError:
        return f"{date_str}T00:00:00"


def _load_cc_config_window(logs_dir: Path | None, start_date: str, end_date: str) -> dict:
    threads: dict[str, dict] = {}
    prompt_events: list[dict] = []
    tool_events: list[dict] = []
    if not logs_dir or not logs_dir.exists():
        return {"threads": [], "prompt_events": [], "tool_events": []}

    for log_file in sorted(logs_dir.glob("*.jsonl")):
        date_str = log_file.stem
        if not within_window(date_str, start_date, end_date):
            continue
        try:
            with log_file.open(encoding="utf-8") as handle:
                for raw_line in handle:
                    if not raw_line.strip():
                        continue
                    try:
                        entry = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue
                    project_path = str(entry.get("cwd", "") or "")
                    project_name = str(entry.get("project", "") or project_name_from_path(project_path))
                    thread_id = str(entry.get("session", "") or "")
                    timestamp = _timestamp_from_date_and_time(date_str, str(entry.get("ts", "00:00:00") or "00:00:00"))
                    base = {
                        "agent": "claude_code",
                        "provider": "anthropic",
                        "thread_id": thread_id,
                        "timestamp": timestamp,
                        "date": date_str,
                        "project_path": project_path,
                        "project_name": project_name,
                        "git_branch": str(entry.get("branch", "") or ""),
                    }
                    if thread_id:
                        thread = threads.setdefault(
                            thread_id,
                            {
                                "thread_id": thread_id,
                                "project_path": project_path,
                                "project_name": project_name,
                                "created_at": timestamp,
                                "updated_at": timestamp,
                                "prompt_count": 0,
                                "tool_count": 0,
                                "usage_cost": 0.0,
                                "tokens_total": 0,
                                "models": Counter(),
                                "tags": Counter(),
                            },
                        )
                        thread["updated_at"] = timestamp
                        model_name = str(entry.get("model", "") or "")
                        if model_name:
                            thread["models"][model_name] += 1

                    action = str(entry.get("action", "") or "")
                    if action == "user_prompt":
                        prompt_text = str(entry.get("prompt", "") or "").strip()
                        if not prompt_text or _is_noise_prompt(prompt_text):
                            continue
                        prompt_events.append(
                            {
                                **base,
                                "event_kind": "prompt",
                                "prompt_text": prompt_text,
                                "prompt_length": len(prompt_text),
                                "source_kind": "journal_log",
                            }
                        )
                        if thread_id:
                            threads[thread_id]["prompt_count"] += 1
                            for tag in keyword_tags(prompt_text):
                                threads[thread_id]["tags"][tag] += 1
                        continue

                    if not action:
                        continue
                    target = (
                        entry.get("target")
                        or entry.get("path")
                        or entry.get("command")
                        or entry.get("query")
                        or entry.get("task")
                        or entry.get("description")
                        or ""
                    )
                    tool_events.append(
                        {
                            **base,
                            "event_kind": "tool_use",
                            "tool_name": str(entry.get("tool", "") or action),
                            "action": action,
                            "target": compact_text(str(target), 240),
                            "model": str(entry.get("model", "") or ""),
                            "source_kind": "journal_log",
                        }
                    )
                    if thread_id:
                        threads[thread_id]["tool_count"] += 1
        except OSError:
            continue

    return {
        "threads": list(threads.values()),
        "prompt_events": prompt_events,
        "tool_events": tool_events,
    }


def load_claude_window(paths: Paths, start_date: str, end_date: str) -> dict:
    sources = discover_sources(paths)
    threads: dict[str, dict] = {}
    prompt_events: list[dict] = []
    usage_events: list[dict] = []
    tool_events: list[dict] = []

    for log_file in _iter_claude_log_files(sources.claude_projects_dir):
        try:
            with log_file.open(encoding="utf-8") as handle:
                for raw_line in handle:
                    if not raw_line.strip():
                        continue
                    try:
                        data = json.loads(raw_line)
                    except json.JSONDecodeError:
                        continue

                    timestamp = parse_iso_timestamp(data.get("timestamp", ""))
                    if not timestamp:
                        continue
                    date_str = timestamp.date().isoformat()
                    if not within_window(date_str, start_date, end_date):
                        continue

                    cwd = data.get("cwd", "")
                    session_id = data.get("sessionId") or data.get("agentId") or data.get("uuid") or ""
                    project_name = project_name_from_path(cwd)
                    base = {
                        "agent": "claude_code",
                        "provider": "anthropic",
                        "thread_id": session_id,
                        "timestamp": timestamp.isoformat(),
                        "date": date_str,
                        "project_path": cwd,
                        "project_name": project_name,
                        "git_branch": data.get("gitBranch", ""),
                    }

                    thread = threads.setdefault(
                        session_id,
                        {
                            "thread_id": session_id,
                            "project_path": cwd,
                            "project_name": project_name,
                            "created_at": timestamp.isoformat(),
                            "updated_at": timestamp.isoformat(),
                            "prompt_count": 0,
                            "tool_count": 0,
                            "usage_cost": 0.0,
                            "tokens_total": 0,
                            "models": Counter(),
                            "tags": Counter(),
                        },
                    )
                    thread["updated_at"] = timestamp.isoformat()

                    if data.get("type") == "user":
                        if data.get("isSidechain"):
                            continue
                        message = data.get("message", {})
                        content = _extract_user_prompt_text(message.get("content", ""))
                        if isinstance(content, str) and content.strip() and not _is_noise_prompt(content):
                            prompt_text = content.strip()
                            prompt_events.append(
                                {
                                    **base,
                                    "event_kind": "prompt",
                                    "prompt_text": prompt_text,
                                    "prompt_length": len(prompt_text),
                                    "source_kind": "native_log",
                                }
                            )
                            thread["prompt_count"] += 1
                            for tag in keyword_tags(prompt_text):
                                thread["tags"][tag] += 1

                    elif data.get("type") == "assistant":
                        message = data.get("message", {})
                        model = message.get("model", "")
                        usage = message.get("usage", {}) or {}
                        content = message.get("content", []) or []
                        if model:
                            thread["models"][model] += 1

                        if usage:
                            input_tokens = int(usage.get("input_tokens", 0) or 0)
                            output_tokens = int(usage.get("output_tokens", 0) or 0)
                            cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
                            cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
                            if input_tokens or output_tokens or cache_read or cache_write:
                                cost = calculate_claude_cost(model, input_tokens, output_tokens, cache_read, cache_write)
                                usage_events.append(
                                    {
                                        **base,
                                        "event_kind": "usage",
                                        "source_kind": "native_log",
                                        "model": model,
                                        "input_tokens": input_tokens,
                                        "output_tokens": output_tokens,
                                        "cache_read_tokens": cache_read,
                                        "cache_write_tokens": cache_write,
                                        "total_tokens": input_tokens + output_tokens + cache_read + cache_write,
                                        "cost_actual": cost["actual"],
                                        "cost_without_cache": cost["without_cache"],
                                        "cache_savings": cost["cache_savings"],
                                    }
                                )
                                thread["usage_cost"] += cost["actual"]
                                thread["tokens_total"] += input_tokens + output_tokens + cache_read + cache_write

                        for item in content:
                            if not isinstance(item, dict) or item.get("type") != "tool_use":
                                continue
                            event = _parse_tool_event(item, {**base, "source_kind": "native_log", "model": model})
                            if event:
                                tool_events.append(event)
                                thread["tool_count"] += 1
        except OSError:
            continue

    history_prompt_events = _load_claude_history_prompts(sources.claude_history_file, start_date, end_date)
    cc_config_data = _load_cc_config_window(sources.cc_config_logs_dir, start_date, end_date)
    prompt_events = _merge_unique_events(prompt_events, history_prompt_events, _prompt_signature)
    prompt_events = _merge_unique_events(prompt_events, cc_config_data["prompt_events"], _prompt_signature)
    tool_events = _merge_unique_events(tool_events, cc_config_data["tool_events"], _tool_signature)

    coverage = []
    if sources.claude_projects_dir:
        coverage.append("native_log")
    if sources.claude_history_file:
        coverage.append("history")
    if sources.cc_config_logs_dir:
        coverage.append("journal_log")

    return {
        "threads": list(threads.values()) if threads else cc_config_data["threads"],
        "prompt_events": prompt_events,
        "usage_events": usage_events,
        "tool_events": tool_events,
        "source_coverage": coverage,
        "source_bounds": {
            "native_log": _native_log_bounds(sources.claude_projects_dir),
            "history": _history_bounds(sources.claude_history_file),
            "journal_log": _journal_log_bounds(sources.cc_config_logs_dir),
        },
    }
