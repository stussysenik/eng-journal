from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from .pricing import estimate_codex_cost
from .util import keyword_tags, project_name_from_path, utc_dt_from_unix, within_window


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_prompt_history(codex_dir: Path, start_date: str, end_date: str) -> dict[str, list[dict]]:
    history_path = codex_dir / "history.jsonl"
    by_session: dict[str, list[dict]] = defaultdict(list)
    if not history_path.exists():
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
            by_session[payload.get("session_id", "")].append(
                {
                    "timestamp": timestamp.isoformat(),
                    "date": date_str,
                    "prompt_text": payload.get("text", ""),
                    "prompt_length": len(payload.get("text", "")),
                }
            )
    return by_session


def _load_log_signals(codex_dir: Path, start_date: str, end_date: str) -> dict[str, dict]:
    log_db = codex_dir / "logs_1.sqlite"
    if not log_db.exists():
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


def load_codex_window(codex_dir: Path, start_date: str, end_date: str) -> dict:
    state_path = codex_dir / "state_5.sqlite"
    if not state_path.exists():
        return {"threads": [], "prompt_events": [], "thread_events": []}

    prompt_history = _load_prompt_history(codex_dir, start_date, end_date)
    log_signals = _load_log_signals(codex_dir, start_date, end_date)
    conn = _connect(state_path)

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
    }
