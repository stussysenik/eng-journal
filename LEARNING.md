# Learning

This file explains how verified review windows are structured so the same math and interpretation do not need to be regenerated every time.

## Architecture
1. Raw sources stay in local Claude/Codex data stores plus optional `cc-config` logs.
2. Mutable normalized datasets live in `.cache/` and are allowed to refresh.
3. Verified windows are frozen into `checkpoints/<window>/dataset.json` plus `manifest.json`.
4. Human-facing outputs for a verified window are the review, stats, ROI, prompt, and dashboard reports.
5. `review` is the checkpointing command. `stats` is the quick metrics command. `report` remains the lower-level renderer.

## Latest Verified Window
- Window: 2025-10-01 to 2026-03-31
- Review: `reports/review-2025-10-01_to_2026-03-31.md`
- Stats: `reports/stats-2025-10-01_to_2026-03-31.md`
- Checkpoint: `checkpoints/2025-10-01_to_2026-03-31/manifest.json`
- Impact: `reports/impact-2025-10-01_to_2026-03-31.md`
- gh-audit reference: `references/gh-audit/latest.json`

## Current Learnings
- Claude Code value is strongest in execution breadth and continuity: 158 projects, 7746 threads, exact cost accounting, and heavy repo/file movement.
- Codex value is strongest in concentrated deep threads: 157 threads, 3,151,297,318 tokens, and 77 subagent threads.
- The learning/report layer is auto-generated from the verified window, including prompt-effectiveness and daily prompt rows.
- Interview-before-action prompts appear 30 times in Claude and 10 times in Codex.
- Verification-first prompts appear 1132 times in Claude and 29 times in Codex.
- Parallel/subagent directives appear 481 times in Claude and 38 times in Codex.

## Keep
- Preserve source coverage and checkpoint verified windows instead of re-deriving them ad hoc.
- Treat review files as durable base-zero summaries and stats files as machine-readable checkpoints.
- Keep prompt-effectiveness and per-day prompt rows generated from the same verified dataset as the headline reports.
- Keep ROI and appraisal separate from learning and workflow analysis.

## Tighten
- Reduce duplicate prompt churn before adding more modeling complexity.
- Continue suppressing command/history prompt noise so directive-signal metrics become cleaner.
- Add more structured execution signals for Codex if future local logs expose them.
