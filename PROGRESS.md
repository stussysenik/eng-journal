# Progress

## Current State

- Cross-agent ingestion works for local Claude Code and Codex data.
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
- Git evidence correlation across touched repos
- Corrected Claude Opus 4.5 pricing in `cc-config`

## Open Gaps

- Claude prompt-quality filtering still needs more aggressive suppression of command/internal traffic
- Codex cost estimates are still range-based because local telemetry does not expose exact input/output token splits
- Semantic-release is configured but still needs the first tagged release cycle
- GitHub Actions release flow assumes repository secrets and default branch protections exist

## Next Moves

- Tighten prompt-noise suppression rules for Claude
- Add JSON export mode for every report type
- Add richer project continuity scoring across windows
- Add optional dashboard once the CLI/report layer stabilizes

