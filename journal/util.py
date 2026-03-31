from __future__ import annotations

import datetime as dt
import hashlib
import math
import re
from pathlib import Path


DATE_FMT = "%Y-%m-%d"


def parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, DATE_FMT).date()


def date_to_str(value: dt.date) -> str:
    return value.strftime(DATE_FMT)


def utc_dt_from_unix(value: int | float) -> dt.datetime:
    return dt.datetime.fromtimestamp(value, dt.UTC)


def parse_iso_timestamp(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def within_window(date_str: str, start_date: str, end_date: str) -> bool:
    return start_date <= date_str <= end_date


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered)
    return cleaned.strip("-") or "item"


def project_name_from_path(path_value: str) -> str:
    if not path_value:
        return "unknown"
    parts = Path(path_value).parts
    skip = {"Users", "home", "Desktop", "Documents", "Projects", "Code", "dev", "Volumes"}
    for part in reversed(parts):
        if part and part not in skip and not part.startswith("."):
            return part
    return Path(path_value).name or "unknown"


def safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def dedupe_key(text: str) -> str:
    collapsed = " ".join(text.lower().split())
    return hashlib.sha1(collapsed.encode("utf-8")).hexdigest()


def month_fraction(start_date: str, end_date: str) -> float:
    start = parse_date(start_date)
    end = parse_date(end_date)
    days = (end - start).days + 1
    return max(days / 30.4375, 1 / 30.4375)


def is_mega_prompt(text: str) -> bool:
    return len(text.strip()) >= 900


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2)


def mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def keyword_tags(text: str) -> list[str]:
    lowered = text.lower()
    pairs = (
        ("plan", ("plan", "map", "spec", "architecture")),
        ("build", ("build", "implement", "create", "ship")),
        ("debug", ("debug", "fix", "error", "issue", "bug")),
        ("test", ("test", "validate", "verify", "coverage")),
        ("research", ("research", "search", "investigate", "look up")),
        ("refactor", ("refactor", "simplify", "reuse", "clean up")),
        ("design", ("design", "layout", "ui", "ux", "visual")),
        ("agents", ("agent", "subagent", "parallel", "worker", "explorer")),
    )
    tags: list[str] = []
    for tag, needles in pairs:
        if any(needle in lowered for needle in needles):
            tags.append(tag)
    return tags


def compact_text(text: str, limit: int = 120) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def log_scale(value: int | float) -> float:
    if value <= 0:
        return 0.0
    return math.log(value + 1.0)

