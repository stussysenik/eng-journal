from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .config import Paths, discover_sources
from .pricing import estimate_codex_cost
from .util import keyword_tags, project_name_from_path, utc_dt_from_unix, within_window


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _bounds_dict(first_ts, last_ts) -> dict:
    return {
        "first_date": first_ts.date().isoformat() if first_ts else "",
        "last_date": last_ts.date().isoformat() if last_ts else "",
    }


def _history_bounds(history_path: Path | None) -> dict:
    if not history_path or not history_path.exists():
        return _bounds_dict(None, None)
    first_ts = None
    last_ts = None
    with history_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            ts = payload.get("ts")
            if ts is None:
                continue
            timestamp = utc_dt_from_unix(int(ts))
            if first_ts is None or timestamp < first_ts:
                first_ts = timestamp
            if last_ts is None or timestamp > last_ts:
                last_ts = timestamp
    return _bounds_dict(first_ts, last_ts)


def _sqlite_bounds(db_path: Path | None, table: str, ts_column: str, end_column: str | None = None) -> dict:
    if not db_path or not db_path.exists():
        return _bounds_dict(None, None)
    conn = _connect(db_path)
    try:
        if end_column:
            row = conn.execute(
                f"select min({ts_column}) as first_ts, max({end_column}) as last_ts from {table}"
            ).fetchone()
        else:
            row = conn.execute(
                f"select min({ts_column}) as first_ts, max({ts_column}) as last_ts from {table}"
            ).fetchone()
    finally:
        conn.close()
    first_raw = row["first_ts"] if row else None
    last_raw = row["last_ts"] if row else None
    return _bounds_dict(
        utc_dt_from_unix(int(first_raw)) if first_raw is not None else None,
        utc_dt_from_unix(int(last_raw)) if last_raw is not None else None,
    )


def _load_prompt_history(history_path: Path | None, start_date: str, end_date: str) -> dict[str, list[dict]]:
    by_session: dict[str, list[dict]] = defaultdict(list)
    if not history_path or not history_path.exists():
        return by_session
    with history_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue
            ts = payload.get("ts")
            if ts is None:
                continue
            timestamp = utc_dt_from_unix(int(ts))
            date_str = timestamp.date().isoformat()
            if not within_window(date_str, start_date, end_date):
                continue
            by_session[str(payload.get("session_id", "") or "")].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "date": date_str,
                    "prompt_text": payload.get("text", ""),
                    "prompt_length": len(payload.get("text", "")),
                }
            )
    return by_session


def _fallback_prompt_events(prompt_history: dict[str, list[dict]]) -> list[dict]:
    prompt_events: list[dict] = []
    for session_id, prompts in prompt_history.items():
        for prompt in prompts:
            prompt_events.append(
                {
                    "agent": "codex",
                    "provider": "",
                    "thread_id": session_id,
                    "timestamp": prompt["timestamp"],
                    "date": prompt["date"],
                    "project_path": "",
                    "project_name": "unknown",
                    "event_kind": "prompt",
                    "prompt_text": prompt["prompt_text"],
                    "prompt_length": len(prompt["prompt_text"]),
                    "source_kind": "history",
                }
            )
    return prompt_events


def _load_log_signals(log_db: Path | None, start_date: str, end_date: str) -> dict[str, dict]:
    if not log_db or not log_db.exists():
        return {}
    conn = _connect(log_db)
    signals: dict[str, dict] = defaultdict(lambda: {"errors": 0, "warnings": 0, "apply_patch_failures": 0})
    rows = conn.execute(
        """
        select ts, thread_id, level, target, feedback_log_body
        from logs
        where ts >= strftime('%s', ?) and ts < strftime('%s', ?)
        """,
        (start_date, f"{end_date}T23:59:59"),
    )
    for row in rows:
        thread_id = row["thread_id"] or "_global"
        level = row["level"] or ""
        body = row["feedback_log_body"] or ""
        if level == "ERROR":
            signals[thread_id]["errors"] += 1
        elif level == "WARN":
            signals[thread_id]["warnings"] += 1
        if "apply_patch verification failed" in body:
            signals[thread_id]["apply_patch_failures"] += 1
    return signals


def load_codex_window(paths: Paths, start_date: str, end_date: str) -> dict:
    sources = discover_sources(paths)
    prompt_history = _load_prompt_history(sources.codex_history_file, start_date, end_date)
    coverage = []
    if sources.codex_history_file:
        coverage.append("history")
    if sources.codex_state_db:
        coverage.append("sqlite_thread")
    if sources.codex_logs_db:
        coverage.append("native_log")

    if not sources.codex_state_db:
        return {
            "threads": [],
            "prompt_events": _fallback_prompt_events(prompt_history),
            "thread_events": [],
            "source_coverage": coverage,
            "source_bounds": {
                "history": _history_bounds(sources.codex_history_file),
                "sqlite_thread": _bounds_dict(None, None),
                "native_log": _bounds_dict(None, None),
            },
        }

    log_signals = _load_log_signals(sources.codex_logs_db, start_date, end_date)
    conn = _connect(sources.codex_state_db)

    threads: list[dict] = []
    thread_events: list[dict] = []
    prompt_events: list[dict] = []

    rows = conn.execute(
        """
        select id, rollout_path, created_at, updated_at, source, model_provider, cwd, title,
               sandbox_policy, approval_mode, tokens_used, git_sha, git_branch, cli_version,
               first_user_message, model, reasoning_effort
        from threads
        where created_at >= strftime('%s', ?) and created_at < strftime('%s', ?)
        order by created_at asc
        """,
        (start_date, f"{end_date}T23:59:59"),
    )

    for row in rows:
        created_at = utc_dt_from_unix(int(row["created_at"]))
        updated_at = utc_dt_from_unix(int(row["updated_at"]))
        date_str = created_at.date().isoformat()
        thread_id = row["id"]
        project_path = row["cwd"] or ""
        project_name = project_name_from_path(project_path)
        model = row["model"] or ""
        source = row["source"] or ""
        signal = log_signals.get(thread_id, {"errors": 0, "warnings": 0, "apply_patch_failures": 0})
        cost_estimate = estimate_codex_cost(int(row["tokens_used"] or 0), model)
        tags = keyword_tags((row["title"] or "") + " " + (row["first_user_message"] or ""))

        thread_record = {
            "thread_id": thread_id,
            "project_path": project_path,
            "project_name": project_name,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
            "date": date_str,
            "title": row["title"] or "",
            "first_user_message": row["first_user_message"] or "",
            "model": model,
            "model_provider": row["model_provider"] or "",
            "reasoning_effort": row["reasoning_effort"] or "",
            "tokens_used": int(row["tokens_used"] or 0),
            "cost_low": cost_estimate["low"],
            "cost_mid": cost_estimate["mid"],
            "cost_high": cost_estimate["high"],
            "git_branch": row["git_branch"] or "",
            "source": source,
            "subagent": "thread_spawn" in source,
            "errors": signal["errors"],
            "warnings": signal["warnings"],
            "apply_patch_failures": signal["apply_patch_failures"],
            "tags": tags,
        }
        threads.append(thread_record)

        thread_events.append(
            {
                "agent": "codex",
                "provider": row["model_provider"] or "",
                "thread_id": thread_id,
                "timestamp": created_at.isoformat(),
                "date": date_str,
                "project_path": project_path,
                "project_name": project_name,
                "event_kind": "thread",
                "title": row["title"] or "",
                "model": model,
                "reasoning_effort": row["reasoning_effort"] or "",
                "tokens_used": int(row["tokens_used"] or 0),
                "cost_low": cost_estimate["low"],
                "cost_mid": cost_estimate["mid"],
                "cost_high": cost_estimate["high"],
                "subagent": "thread_spawn" in source,
                "errors": signal["errors"],
                "warnings": signal["warnings"],
                "apply_patch_failures": signal["apply_patch_failures"],
                "source_kind": "sqlite_thread",
            }
        )

        history_prompts = prompt_history.get(thread_id, [])
        if not history_prompts:
            fallback_text = (row["first_user_message"] or row["title"] or "").strip()
            if fallback_text:
                history_prompts = [
                    {
                        "timestamp": created_at.isoformat(),
                        "date": date_str,
                        "prompt_text": fallback_text,
                        "prompt_length": len(fallback_text),
                    }
                ]
        for prompt in history_prompts:
            text = prompt["prompt_text"]
            prompt_events.append(
                {
                    "agent": "codex",
                    "provider": row["model_provider"] or "",
                    "thread_id": thread_id,
                    "timestamp": prompt["timestamp"],
                    "date": prompt["date"],
                    "project_path": project_path,
                    "project_name": project_name,
                    "event_kind": "prompt",
                    "prompt_text": text,
                    "prompt_length": len(text),
                    "source_kind": "history",
                }
            )

    return {
        "threads": threads,
        "thread_events": thread_events,
        "prompt_events": prompt_events,
        "source_coverage": coverage,
        "source_bounds": {
            "history": _history_bounds(sources.codex_history_file),
            "sqlite_thread": _sqlite_bounds(sources.codex_state_db, "threads", "created_at", "updated_at"),
            "native_log": _sqlite_bounds(sources.codex_logs_db, "logs", "ts"),
        },
    }
