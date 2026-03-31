# eng-journal

Standalone engineering journal and ROI analytics for local Claude Code and Codex usage.

The repo ingests raw local activity, normalizes both agents into one period dataset, and produces:

- CHARM-style ASCII dashboards
- verified base-zero reviews
- reusable stats snapshots
- daily Markdown journals
- weekly rollups
- prompt-efficiency reports
- prompt-effectiveness summaries and high-output day breakdowns
- repo-level impact summaries with imported `gh-audit` references
- ROI scorecards with subscription sensitivity tables
- appraisal reports with conservative, base, and aggressive option-value bands
- core-value reports for the observed builder window

The ingestion layer is Python-only and uses the standard library. The ROI scoring layer runs in Common Lisp through `sbcl`.

## Commands

```bash
./bin/journal doctor
./bin/journal reference gh-audit
./bin/journal reference gh-audit --scan --user stussysenik
./bin/journal refresh --scan-gh-audit --user stussysenik
./bin/journal schedule install --cadence daily --hour 3 --minute 17
./bin/journal schedule status
./bin/journal storage status
./bin/journal storage prune --keep-windows 1
./bin/journal report scheduler-status
./bin/journal review --start 2025-10-01 --end 2026-03-31
./bin/journal stats --start 2025-10-01 --end 2026-03-31 --format markdown
./bin/journal ingest --start 2025-10-01 --end 2026-03-31
./bin/journal report dashboard --start 2025-10-01 --end 2026-03-31
./bin/journal report impact --start 2025-10-01 --end 2026-03-31
./bin/journal report roi --start 2025-10-01 --end 2026-03-31
./bin/journal report appraisal --start 2026-02-12 --end 2026-03-31
./bin/journal report core-value --start 2026-02-12 --end 2026-03-31
./bin/journal report weekly --start 2026-02-12 --end 2026-03-31
./bin/journal report prompts --start 2025-10-01 --end 2026-03-31 --agent claude_code
./bin/journal report daily --date 2026-03-31
./bin/journal capture screenshots --start 2026-02-12 --end 2026-03-31
```

Generated reports land in `reports/`.

`review` is the high-level command:

- rebuilds the verified dataset when needed
- writes the base-zero review, stats, dashboard, ROI, and prompt reports
- writes the impact report when a normalized `gh-audit` reference exists
- freezes the window into `checkpoints/<window>/`
- updates `LEARNING.md` so the repo keeps the current verified learnings
- auto-maintains the latest verified window so later `review`, `stats`, `report`, and `capture` calls default to that checkpoint

The default window is no longer just a hardcoded date pair. If a verified checkpoint exists, the CLI uses that latest verified window automatically.

`refresh` is the automation command:

- optionally runs a fresh `gh-audit` Julia scan and imports the newest JSON reference
- rebuilds the verified review window with `--refresh`
- updates the impact report so the job-facing layer stays current
- prunes older windows by default and keeps only the latest durable window unless you override `--keep-windows` or pass `--no-prune`

`schedule` installs a local recurring refresh:

- `launchd` on macOS when `--runner auto`
- `cron` on other systems when `--runner auto`
- supports `install`, `status`, and `remove`
- keeps `reports/scheduler-status.md` current with the installed schedule and last refresh result

`storage` is the retention command:

- `storage status` shows tracked vs local-only storage by window
- `storage prune --keep-windows 1` removes older report/checkpoint windows
- this is the explicit broom if you want to collapse the repo back to one durable window immediately

## Portable Discovery

The loader is no longer tied to one laptop layout. It discovers the latest local sources automatically and also supports explicit overrides:

- `ENG_JOURNAL_CLAUDE_DIR`
- `ENG_JOURNAL_CODEX_DIR`
- `ENG_JOURNAL_CC_CONFIG_DIR`

Claude source precedence is:

- native project logs
- prompt history
- `cc-config/logs/*.jsonl` fallback and supplemental action coverage

Codex source precedence is:

- latest `state_*.sqlite`
- `history.jsonl` prompt history
- latest `logs_*.sqlite` diagnostics

## gh-audit Reference

`eng-journal` can import repo-level asset references from the separate Julia repo [`gh-audit`](https://github.com/stussysenik/gh-audit).

- `eng-journal` stays the usage/ROI/learning system
- `gh-audit` stays the repo security/replacement-cost/portfolio-reference system
- the bridge is a normalized import at `references/gh-audit/latest.json`
- `./bin/journal reference gh-audit --scan` runs a fresh Julia portfolio scan and imports the resulting JSON in one step
- `./bin/journal refresh --scan-gh-audit` runs the full local refresh loop in one command
- `./bin/journal schedule install` makes that refresh loop run nightly or weekly without manual intervention
- `./bin/journal report scheduler-status` renders the current local scheduler + last refresh state into the repo

The imported reference keeps both:

- `estimated_value_usd`: adjusted reference value after outlier / shallow-scan attenuation
- `raw_estimated_value_usd`: unadjusted replacement-cost style reference

That makes the impact report safer for applications and summaries because it no longer treats a huge shallow LOC estimate as equal to a smaller deep-scanned repo.

That keeps Julia out of the core ingestion pipeline while still letting repo-level appraisals show up in the job/application impact report.

## ASCII Dashboard

```text
+---------------------------------------------------------------------------------------------------------+
| eng-journal :: ascii analytics dashboard                                                                |
| window 2025-10-01 -> 2026-03-31                                                                         |
+---------------------------------------------------------------------------------------------------------+
| agent          | days | projects | threads | tokens         | mid cost   | month mid  | confidence      |
+---------------------------------------------------------------------------------------------------------+
| Claude Code    | 87   | 158      | 7744    | 12,178,728,869 | $6,681     | $1,117     | exact           |
| Codex          | 19   | 35       | 137     | 2,208,553,386  | $9,635     | $1,611     | estimated_range |
+---------------------------------------------------------------------------------------------------------+
```

## Checkpoints

Verified windows are frozen into:

- `checkpoints/<window>/manifest.json`
- `.cache/checkpoints/<window>/dataset.json`

That gives the repo a durable base summary layer without forcing heavy machine-readable datasets into git. Mutable cache files in `.cache/` can refresh; tracked manifests and summaries remain the canonical reviewed snapshots.

## Storage Policy

Tracked and intended for git:

- `reports/*.md`
- `reports/*.txt`
- `reports/scheduler-status.md`
- `checkpoints/<window>/manifest.json`
- `references/gh-audit/latest.json`
- `LEARNING.md`

Local-only and ignored:

- `.cache/<window>.json`
- `.cache/reports/*.json`
- `.cache/checkpoints/<window>/dataset.json`
- raw `gh-audit-output/*.json`

The intent is simple: human-facing verified summaries stay in the repo, while bulky machine-readable intermediates stay local.

## Screenshots

ASCII outputs can be rendered into committed terminal-style PNGs:

![ASCII dashboard](assets/screenshots/dashboard-2026-02-12_to_2026-03-31.png)

![Core value report](assets/screenshots/core-value-2026-02-12_to_2026-03-31.png)

## Data sources

- `~/.claude/projects/**/*.jsonl`
- `~/.claude/history.jsonl`
- `~/Desktop/cc-config/logs/*.jsonl`
- `~/Desktop/cc-config/logs/.stats.json`
- `~/.codex/history.jsonl`
- `~/.codex/state_*.sqlite`
- `~/.codex/logs_*.sqlite`

## Pricing notes

Claude costs are computed exactly when native usage fields are present.

Codex local telemetry currently exposes `tokens_used` per thread but not a full input/output split, so Codex report costs are shown as a low/high range plus a blended midpoint estimate.

Subscription payback is shown as a sensitivity table because local auth does not expose a definitive ChatGPT/Codex plan tier.

## Repo Files

- `README.md`: repo purpose, commands, and source-of-truth usage
- `LEARNING.md`: current learning framework and latest verified review pointers
- `reports/scheduler-status.md`: current local automation status, installed cadence, and last refresh result
- `PROGRESS.md`: current implementation status and next gaps
- `hyperdata.json`: structured repo metadata, current windows, report inventory, and appraisal framing
- `CHANGELOG.md`: semantic-release changelog target
- `checkpoints/<window>/manifest.json`: auto-maintained source-of-truth for the latest verified window
- `.cache/checkpoints/<window>/dataset.json`: local-only verified dataset backing fast reloads
- `.cache/reports/stats-<window>.json`: local-only machine-readable stats snapshot
- `references/gh-audit/latest.json`: normalized external repo-asset reference imported from `gh-audit`

## Valuation Scope

The appraisal report is intentionally separate from the ROI report.

- ROI answers: are the tools paying back their subscription and compute-equivalent cost?
- Appraisal answers: what are the delivered artifacts, continuity, and option value plausibly worth as a portfolio?

That separation keeps the engineering journal grounded while still giving you a structured way to appraise the work.
