from __future__ import annotations

import json
from pathlib import Path


def _keyword(name: str) -> str:
    return ":" + name.replace("_", "-")


def to_sexp(value) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "t"
    if value is False:
        return "nil"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, (list, tuple)):
        return "(" + " ".join(to_sexp(item) for item in value) + ")"
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            parts.append(_keyword(str(key)))
            parts.append(to_sexp(item))
        return "(" + " ".join(parts) + ")"
    raise TypeError(f"Unsupported value for s-expression serialization: {type(value)!r}")


def write_sexp(path: Path, payload: dict) -> None:
    path.write_text(to_sexp(payload) + "\n", encoding="utf-8")
