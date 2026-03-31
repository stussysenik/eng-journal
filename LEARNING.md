# Learning

This file explains how verified review windows are structured so the same math and interpretation do not need to be regenerated every time.

## Architecture
1. Raw sources stay in local Claude/Codex data stores plus optional `cc-config` logs.
2. Mutable normalized datasets live in `.cache/` and are allowed to refresh.
3. Verified windows are frozen into `checkpoints/<window>/dataset.json` plus `manifest.json`.
4. Human-facing outputs for a verified window are the review, stats, ROI, prompt, and dashboard reports.
5. `review` is the checkpointing command. `stats` is the quick metrics command. `report` remains the lower-level renderer.

## Latest Verified Window
- Window: 2026-01-01 to 2026-03-31
- Review: `reports/review-2026-01-01_to_2026-03-31.md`
- Stats: `reports/stats-2026-01-01_to_2026-03-31.md`
- Checkpoint: `checkpoints/2026-01-01_to_2026-03-31/manifest.json`

## Current Learnings
- Claude Code value is strongest in execution breadth and continuity: 151 projects, 7744 threads, exact cost accounting, and heavy repo/file movement.
- Codex value is strongest in concentrated deep threads: 129 threads, 1,735,284,986 tokens, and 50 subagent threads.
- Interview-before-action prompts appear 30 times in Claude and 10 times in Codex.
- Verification-first prompts appear 1005 times in Claude and 26 times in Codex.
- Parallel/subagent directives appear 481 times in Claude and 32 times in Codex.

## Keep
- Preserve source coverage and checkpoint verified windows instead of re-deriving them ad hoc.
- Treat review files as durable base-zero summaries and stats files as machine-readable checkpoints.
- Keep ROI and appraisal separate from learning and workflow analysis.

## Tighten
- Reduce duplicate prompt churn before adding more modeling complexity.
- Continue suppressing command/history prompt noise so directive-signal metrics become cleaner.
- Add more structured execution signals for Codex if future local logs expose them.
