# eng-journal

Standalone engineering journal and ROI analytics for local Claude Code and Codex usage.

The repo ingests raw local activity, normalizes both agents into one period dataset, and produces:

- daily Markdown journals
- weekly rollups
- prompt-efficiency reports
- ROI scorecards with subscription sensitivity tables
- appraisal reports with conservative, base, and aggressive option-value bands

The ingestion layer is Python-only and uses the standard library. The ROI scoring layer runs in Common Lisp through `sbcl`.

## Commands

```bash
./bin/journal doctor
./bin/journal ingest --start 2026-02-12 --end 2026-03-31
./bin/journal report roi --start 2026-02-12 --end 2026-03-31
./bin/journal report appraisal --start 2026-02-12 --end 2026-03-31
./bin/journal report weekly --start 2026-02-12 --end 2026-03-31
./bin/journal report prompts --start 2026-02-12 --end 2026-03-31 --agent codex
./bin/journal report daily --date 2026-03-31
```

Generated reports land in `reports/`.

## Data sources

- `~/.claude/projects/**/*.jsonl`
- `~/.claude/history.jsonl`
- `~/.codex/history.jsonl`
- `~/.codex/state_5.sqlite`
- `~/.codex/logs_1.sqlite`

## Pricing notes

Claude costs are computed exactly when native usage fields are present.

Codex local telemetry currently exposes `tokens_used` per thread but not a full input/output split, so Codex report costs are shown as a low/high range plus a blended midpoint estimate.

Subscription payback is shown as a sensitivity table because local auth does not expose a definitive ChatGPT/Codex plan tier.

## Repo Files

- `README.md`: repo purpose, commands, and source-of-truth usage
- `PROGRESS.md`: current implementation status and next gaps
- `hyperdata.json`: structured repo metadata, current windows, report inventory, and appraisal framing
- `CHANGELOG.md`: semantic-release changelog target

## Valuation Scope

The appraisal report is intentionally separate from the ROI report.

- ROI answers: are the tools paying back their subscription and compute-equivalent cost?
- Appraisal answers: what are the delivered artifacts, continuity, and option value plausibly worth as a portfolio?

That separation keeps the engineering journal grounded while still giving you a structured way to appraise the work.

