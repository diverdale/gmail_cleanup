---
phase: 03-message-discovery
plan: "03"
subsystem: cli
tags: [rich, typer, pagination, spinner, gmail-api]

# Dependency graph
requires:
  - phase: 03-message-discovery
    plan: "01"
    provides: "date_utils with local-tz semantics and epoch query builder"
  - phase: 03-message-discovery
    plan: "02"
    provides: "list_message_ids() with full nextPageToken pagination"

provides:
  - "main.py wired with paginated fetch via inline pagination loop"
  - "Rich spinner showing live running count during Gmail API pagination"
  - "Exact count output (no ~ prefix, no approximate qualifier)"
  - "Timestamp display with local timezone abbreviation (e.g. PST, EST)"
  - "Mid-pagination HttpError handling with page number in error message"

affects:
  - "04-deletion"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Inline pagination in main.py for UX control — main drives loop to update spinner per page"
    - "Rich console.status() context manager wraps pagination loop"
    - "cutoff.strftime('%Y-%m-%d %H:%M:%S %Z') for timezone-annotated display"

key-files:
  created: []
  modified:
    - "gmail_cleanup/main.py"

key-decisions:
  - "Inline pagination loop in main.py (not delegating to list_message_ids) so spinner can update per page"
  - "console.print() with Rich markup for dry-run count line; typer.echo() for plain follow-up line"
  - "cutoff_display built after both --older-than and --before branches — single strftime call covers both paths"

patterns-established:
  - "Spinner pattern: console.status() wraps loop, status.update() called after each page extend"
  - "Mid-pagination error format: page number included so user knows how far fetch progressed"

requirements-completed:
  - DISC-01
  - DISC-02

# Metrics
duration: ~15min
completed: 2026-02-19
---

# Phase 3 Plan 03: Wire main.py CLI Summary

**Rich spinner with live running count during paginated Gmail fetch, exact message count with local-timezone timestamp in dry-run and execute output**

## Performance

- **Duration:** ~15 min (including live Gmail verification)
- **Started:** 2026-02-19
- **Completed:** 2026-02-19
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files modified:** 1

## Accomplishments

- Replaced `count_messages()` single-call with inline pagination loop that updates a Rich spinner per page
- Dry-run and execute output now show exact count (no `~` prefix, no `(approximate)` qualifier)
- Timestamp display includes time and local timezone abbreviation: `Found N emails before 2024-01-01 23:59:59 PST.`
- Mid-pagination `HttpError` exits with code 1 and reports which page number failed
- All prior CLI behaviors preserved: mutual exclusion check, credential errors, confirmation gate, cancel exits 0

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire main.py with paginated fetch, spinner, and updated output** - `b0b4230` (feat)
2. **Task 2: Live verification — spinner, exact count, timezone display** - checkpoint:human-verify (approved, no code changes)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `/Users/dalwrigh/dev/gmail_cleanup/gmail_cleanup/main.py` - Updated with Rich Console import, module-level `console = Console()`, inline pagination loop inside `console.status()` context manager, `cutoff_display` strftime, Rich-formatted dry-run output, plain execute-path output

## Decisions Made

- **Inline pagination in main.py** — list_message_ids() remains available for Phase 4 (deletion loop), but the dry-run path uses an inline pagination loop so main.py can drive `status.update()` per page. Delegating entirely to list_message_ids() would obscure the spinner update point.
- **console.print() for count, typer.echo() for follow-up** — Rich markup applies only to the count line (`[bold]Found N emails[/bold]`); the plain "Run with --execute" line stays as typer.echo() to avoid Rich formatting overhead.
- **Single cutoff_display after both branches** — `cutoff_display = cutoff.strftime("%Y-%m-%d %H:%M:%S %Z").strip()` is computed once after either --older-than or --before resolves `cutoff`, keeping the display logic in one place.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 3 complete: epoch queries, full pagination, exact counts, timezone display all verified against live Gmail account
- `message_ids: list[str]` is ready for Phase 4 to consume — batch_delete can iterate directly over this list
- `list_message_ids()` from gmail_client.py remains available for Phase 4 deletion loop (not used in dry-run path but correct abstraction for deletion)

---
*Phase: 03-message-discovery*
*Completed: 2026-02-19*
