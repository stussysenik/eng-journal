from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

from .config import Paths


def gh_audit_reference_path(paths: Paths) -> Path:
    return paths.references_dir / "gh-audit" / "latest.json"


def discover_latest_gh_audit_report(paths: Paths) -> Path | None:
    if not paths.gh_audit_dir or not paths.gh_audit_dir.exists():
        return None
    candidates = sorted(paths.gh_audit_dir.glob("gh-audit-report-*.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def default_gh_audit_workdir(paths: Paths) -> Path:
    return (paths.repo_root.parent / "gh-audit-work").resolve()


def default_gh_audit_output_dir(paths: Paths) -> Path:
    return (paths.repo_root.parent / "gh-audit-output").resolve()


def run_gh_audit_scan(
    paths: Paths,
    user: str,
    workdir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    if not paths.gh_audit_dir or not paths.gh_audit_dir.exists():
        raise FileNotFoundError("No gh-audit repo found. Configure ENG_JOURNAL_GH_AUDIT_DIR or place gh-audit next to eng-journal.")

    workdir = (workdir or default_gh_audit_workdir(paths)).expanduser().resolve()
    output_dir = (output_dir or default_gh_audit_output_dir(paths)).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    before = set(output_dir.glob("gh-audit-report-*.json"))
    subprocess.run(
        [
            "julia",
            "--project=.",
            "bin/ghaudit.jl",
            "scan",
            "--user",
            user,
            "--workdir",
            str(workdir),
            "--output",
            str(output_dir),
        ],
        cwd=paths.gh_audit_dir,
        check=True,
    )
    after = set(output_dir.glob("gh-audit-report-*.json"))
    candidates = sorted(after - before)
    if candidates:
        return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))
    latest = sorted(after)
    if latest:
        return max(latest, key=lambda path: (path.stat().st_mtime, path.name))
    raise FileNotFoundError(f"No gh-audit JSON report found in {output_dir}")


def _leverage_rank(value_per_kloc: float) -> str:
    if value_per_kloc > 50_000:
        return "Diamond"
    if value_per_kloc > 20_000:
        return "Gold"
    if value_per_kloc > 10_000:
        return "Silver"
    if value_per_kloc > 5_000:
        return "Bronze"
    return "Raw"


def normalize_gh_audit_report(source_path: Path) -> dict:
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    repos: list[dict] = []

    for repo in payload.get("repos", []):
        valuation = repo.get("valuation", {}) or {}
        perspectives = repo.get("perspectives", {}) or {}
        estimated_value = float(valuation.get("estimated_value_usd", 0.0) or 0.0)
        raw_estimated_value = float(valuation.get("raw_estimated_value_usd", estimated_value) or 0.0)
        kloc = float(valuation.get("kloc", 0.0) or 0.0)
        leverage = float(valuation.get("leverage_score", 0.0) or 0.0) or (estimated_value / max(kloc, 0.0001))
        repos.append(
            {
                "name": str(repo.get("name", "") or ""),
                "classification": str(repo.get("classification", "") or ""),
                "language": str(repo.get("language", "") or ""),
                "deep_scanned": bool(repo.get("deep_scanned", False)),
                "finding_count": len(repo.get("findings", []) or []),
                "nda_score": int(repo.get("nda_score", 0) or 0),
                "nda_reasons": list(repo.get("nda_reasons", []) or []),
                "loc": int(repo.get("loc", 0) or 0),
                "kloc": kloc,
                "disk_kb": int(repo.get("disk_kb", 0) or 0),
                "estimated_value_usd": estimated_value,
                "raw_estimated_value_usd": raw_estimated_value,
                "adjustment_factor": float(valuation.get("adjustment_factor", 1.0) or 1.0),
                "cocomo_cost_usd": float(valuation.get("cocomo_cost_usd", 0.0) or 0.0),
                "cocomo_effort_pm": float(valuation.get("cocomo_effort_pm", 0.0) or 0.0),
                "market_score": float(valuation.get("market_score", 0.0) or 0.0),
                "portfolio_score": float(valuation.get("portfolio_score", 0.0) or 0.0),
                "leverage_usd_per_kloc": leverage,
                "leverage_rank": str(valuation.get("leverage_rank", "") or _leverage_rank(leverage)),
                "confidence_score": float(valuation.get("confidence_score", 0.0) or 0.0),
                "confidence_label": str(valuation.get("confidence_label", "") or ""),
                "loc_source": str(valuation.get("loc_source", "") or ""),
                "warning_flags": list(valuation.get("warning_flags", []) or []),
                "staff_engineer": float(perspectives.get("staff_engineer", 0.0) or 0.0),
                "design_engineer": float(perspectives.get("design_engineer", 0.0) or 0.0),
                "ai_ml_researcher": float(perspectives.get("ai_ml_researcher", 0.0) or 0.0),
                "staff_eng_notes": str(perspectives.get("staff_eng_notes", "") or ""),
                "design_eng_notes": str(perspectives.get("design_eng_notes", "") or ""),
                "ai_ml_notes": str(perspectives.get("ai_ml_notes", "") or ""),
            }
        )

    repos.sort(key=lambda item: item["estimated_value_usd"], reverse=True)
    loc_outliers = [repo["name"] for repo in repos if repo["kloc"] >= 500.0]
    value_outliers = [repo["name"] for repo in repos if repo["estimated_value_usd"] >= 5_000_000.0]
    deep_scanned_count = sum(1 for repo in repos if repo["deep_scanned"])

    return {
        "imported_at": dt.datetime.now(dt.UTC).isoformat(),
        "source_report_path": str(source_path),
        "source_timestamp": str(payload.get("timestamp", "") or ""),
        "portfolio": {
            "total_repos": int(payload.get("total_repos", 0) or 0),
            "total_findings": int(payload.get("total_findings", 0) or 0),
            "total_portfolio_value_usd": float(payload.get("total_portfolio_value_usd", 0.0) or 0.0),
            "raw_total_portfolio_value_usd": float(
                payload.get("raw_total_portfolio_value_usd", payload.get("total_portfolio_value_usd", 0.0)) or 0.0
            ),
            "safe_count": int(payload.get("safe_count", 0) or 0),
            "needs_fixes_count": int(payload.get("needs_fixes_count", 0) or 0),
            "too_sensitive_count": int(payload.get("too_sensitive_count", 0) or 0),
            "nda_count": int(payload.get("nda_count", 0) or 0),
            "critical_count": int(payload.get("critical_count", 0) or 0),
            "average_confidence_score": float(payload.get("average_confidence_score", 0.0) or 0.0),
            "deep_scanned_count": deep_scanned_count,
            "loc_outlier_count": len(loc_outliers),
            "value_outlier_count": len(value_outliers),
            "top_repo_value_usd": repos[0]["estimated_value_usd"] if repos else 0.0,
            "top_repo_name": repos[0]["name"] if repos else "",
        },
        "method_caveats": [
            "gh-audit is best treated as a repo replacement-cost and portfolio-reference engine, not a company valuation engine.",
            "Adjusted gh-audit values attenuate shallow or outlier-heavy LOC estimates, but they are still valuation references rather than price discovery.",
            "LOC-sensitive COCOMO math can still overstate value on generated, vendored, binary-heavy, or data-heavy repos.",
            "Market and portfolio scores are heuristic rankings, not investor-grade price discovery.",
            "Portfolio totals can over-count overlapping codebases and shared internal scaffolding.",
        ],
        "outliers": {
            "loc_outliers": loc_outliers[:25],
            "value_outliers": value_outliers[:25],
        },
        "repos": repos,
    }


def import_gh_audit_reference(paths: Paths, input_path: Path | None = None) -> Path:
    source_path = (input_path or discover_latest_gh_audit_report(paths))
    if source_path is None:
        raise FileNotFoundError("No gh-audit report found. Provide --input or configure ENG_JOURNAL_GH_AUDIT_DIR.")
    normalized = normalize_gh_audit_report(source_path)
    target = gh_audit_reference_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return target


def load_gh_audit_reference(paths: Paths) -> dict | None:
    target = gh_audit_reference_path(paths)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))
