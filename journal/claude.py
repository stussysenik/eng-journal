from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .pricing import calculate_claude_cost
from .util import keyword_tags, parse_iso_timestamp, project_name_from_path, within_window


def _iter_claude_log_files(claude_dir: Path) -> list[Path]:
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []
    return sorted(projects_dir.glob("**/*.jsonl"))


def _parse_tool_event(item: dict, base: dict) -> dict | None:
    tool_name = item.get("name", "")
    inputs = item.get("input", {}) or {}
    target = inputs.get("file_path") or inputs.get("command") or inputs.get("query") or inputs.get("url") or ""
    action = {
        "Write": "created_file",
        "Edit": "modified_file",
        "Read": "read_file",
        "Glob": "searched_code",
        "Grep": "searched_code",
        "Bash": "ran_command",
        "Task": "delegated",
        "WebFetch": "web_fetch",
        "WebSearch": "web_search",
    }.get(tool_name, "tool_use")
    return {
        **base,
        "event_kind": "tool_use",
        "tool_name": tool_name,
        "action": action,
        "target": target[:240],
    }


def _stringify_content(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "content" in value:
            return _stringify_content(value.get("content"))
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, list):
        return "\n".join(part for part in (_stringify_content(item) for item in value) if part)
    return str(value)


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


def load_claude_window(claude_dir: Path, start_date: str, end_date: str) -> dict:
    threads: dict[str, dict] = {}
    prompt_events: list[dict] = []
    usage_events: list[dict] = []
    tool_events: list[dict] = []

    for log_file in _iter_claude_log_files(claude_dir):
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

    return {
        "threads": list(threads.values()),
        "prompt_events": prompt_events,
        "usage_events": usage_events,
        "tool_events": tool_events,
    }
