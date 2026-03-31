# Scheduler Status

This report tracks the local auto-refresh loop for gh-audit imports and review regeneration.

## Schedule
- Runner: launchd
- Installed: yes
- Path: `/Users/s3nik/Library/LaunchAgents/com.engjournal.eng-journal.refresh.plist`
- Log: `/Users/s3nik/Desktop/eng-journal/.cache/scheduled-refresh.log`
- Timing: daily at 03:17
- Runtime state: not running
- Launch count: 0
- Command: `cd /Users/s3nik/Desktop/eng-journal && /Users/s3nik/Desktop/eng-journal/bin/journal refresh --scan-gh-audit --user stussysenik --workdir /Users/s3nik/Desktop/gh-audit-work --output-dir /Users/s3nik/Desktop/gh-audit-output`

## Last Refresh
- Status: ok
- Started at: 2026-03-31T22:00:09.441962+00:00
- Completed at: 2026-03-31T22:01:15.932847+00:00
- Window: 2025-10-01 to 2026-03-31
- gh-audit scan: no
- Retention: keep latest 1 window(s)
- Pruned paths: 0
- Scheduler report: `/Users/s3nik/Desktop/eng-journal/reports/scheduler-status.md`
