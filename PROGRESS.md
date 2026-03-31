# Progress

## Current State

- Cross-agent ingestion works for local Claude Code and Codex data.
- Source discovery now works across machines via env overrides and latest-file discovery.
- Reports currently ship as Markdown through the CLI.
- Verified windows can now be checkpointed and reused through `review`.
- Prompt-effectiveness and per-day prompt rows are auto-generated inside the verified dataset and reports.
- ROI scoring runs through SBCL and uses current public pricing references captured in code.
- The current verified review window is `2025-10-01` through `2026-03-31`.

## Shipped

- `doctor` source verification command
- `ingest` normalized period dataset build
- `report daily`
- `report weekly`
- `report prompts`
- `report roi`
- `report appraisal`
- `report core-value`
- `report dashboard`
- `review` verified window checkpointing
- `stats` reusable metrics snapshots
- `capture screenshots`
- Portable source discovery for Claude, Codex, and optional `cc-config`
- Claude ingestion from native logs, `history.jsonl`, and `cc-config/logs/*.jsonl`
- Dynamic Codex discovery for `state_*.sqlite` and `logs_*.sqlite`
- Source availability ranges surfaced per agent and per source kind
- Prompt-effectiveness summaries and high-output prompt days
- Daily report enrichment with prompt mix, directive signals, top projects, and execution breakdowns
- Root `LEARNING.md` updated from the latest verified review
- Git evidence correlation across touched repos
- Corrected Claude Opus 4.5 pricing in `cc-config`

## Open Gaps

- Claude prompt-quality filtering still needs more aggressive suppression of command/internal traffic
- `cc-config` stats are discovered but not yet used as a synthetic cost fallback when native usage is missing
- Codex cost estimates are still range-based because local telemetry does not expose exact input/output token splits
- Codex execution metrics are still thin because local telemetry does not yet expose file/tool events the way Claude does
- Semantic-release is configured but still needs the first tagged release cycle
- GitHub Actions release flow assumes repository secrets and default branch protections exist
- Claude prompt-effectiveness still measures correlation against execution-heavy days, not strict causal lift

## Next Moves

- Tighten prompt-noise suppression rules for Claude history and backfilled journal prompts
- Add JSON export mode for every report type beyond `stats`
- Add richer project continuity scoring across windows
- Expose source coverage directly in ROI and dashboard reports
- Add checkpoint diffing so two verified windows can be compared directly
- Add project-cluster reports so “what was worked on” is generated explicitly per repo cluster
