# Progress

## Current State

- Cross-agent ingestion works for local Claude Code and Codex data.
- Source discovery now works across machines via env overrides and latest-file discovery.
- Reports currently ship as Markdown through the CLI.
- ROI scoring runs through SBCL and uses current public pricing references captured in code.
- The initial aligned comparison window is `2026-02-12` through `2026-03-31`.

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
- `capture screenshots`
- Portable source discovery for Claude, Codex, and optional `cc-config`
- Claude ingestion from native logs, `history.jsonl`, and `cc-config/logs/*.jsonl`
- Dynamic Codex discovery for `state_*.sqlite` and `logs_*.sqlite`
- Git evidence correlation across touched repos
- Corrected Claude Opus 4.5 pricing in `cc-config`

## Open Gaps

- Claude prompt-quality filtering still needs more aggressive suppression of command/internal traffic
- `cc-config` stats are discovered but not yet used as a synthetic cost fallback when native usage is missing
- Codex cost estimates are still range-based because local telemetry does not expose exact input/output token splits
- Semantic-release is configured but still needs the first tagged release cycle
- GitHub Actions release flow assumes repository secrets and default branch protections exist

## Next Moves

- Tighten prompt-noise suppression rules for Claude history and backfilled journal prompts
- Add JSON export mode for every report type
- Add richer project continuity scoring across windows
- Expose source coverage directly in ROI and dashboard reports
