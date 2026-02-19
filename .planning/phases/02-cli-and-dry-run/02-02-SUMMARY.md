---
phase: 02-cli-and-dry-run
plan: "02"
subsystem: cli
tags: [typer, gmail-api, dry-run, cli, count-messages, argument-validation]

# Dependency graph
requires:
  - phase: 02-cli-and-dry-run
    plan: "01"
    provides: "months_ago_to_cutoff, parse_date_to_cutoff, build_gmail_query from date_utils.py"
  - phase: 01-foundation
    provides: "build_gmail_service() from auth.py, project scaffolding, pyproject.toml"
provides:
  - "gmail_cleanup/gmail_client.py with count_messages() function — approximate email count via Gmail API list endpoint"
  - "gmail_cleanup/main.py with real CLI: --older-than, --before, --execute; dry-run default; confirmation gate"
affects:
  - 02-03
  - 03-pagination-and-list

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Typer option with callback for pre-validation (validate_date runs before main body)"
    - "Mutual exclusion enforcement via explicit None checks at start of command body"
    - "Dry-run default pattern: --execute flag required to trigger writes"
    - "typer.confirm() gate for destructive operations — appends [y/N] automatically"
    - "Exit 0 for user-cancelled operations (not errors), Exit 1 for usage errors, Exit 2 for Typer validation"

key-files:
  created: []
  modified:
    - gmail_cleanup/gmail_client.py
    - gmail_cleanup/main.py

key-decisions:
  - "count_messages() uses maxResults=500 single-call — approximate count, Phase 3 adds full pagination"
  - "validate_date() is a Typer callback on --before, not inline check — triggers exit 2 (Typer protocol) not exit 1"
  - "HttpError imported in gmail_client.py for future use (Phase 3/4) even though not caught yet in count_messages"
  - "Cancel via N confirmation or Ctrl-C exits 0 — user intent, not an error condition"
  - "Deletion stub prints '(Phase 4)' to communicate incompleteness clearly"

patterns-established:
  - "count_messages() is separate from list_messages() — count is Phase 2, full list is Phase 3"
  - "Typer callback for --before validation: returns value or raises BadParameter"
  - "Gmail API calls wrapped in try/except HttpError with err=True echo"

requirements-completed: [CLI-01, CLI-02, CLI-03, CLI-04]

# Metrics
duration: 2min
completed: 2026-02-19
---

# Phase 02 Plan 02: Real CLI and count_messages() Summary

**Typer CLI with --older-than/--before mutual-exclusive targeting, dry-run default, --execute confirmation gate, and count_messages() using Gmail API maxResults=500 single-call approximation**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-19T00:57:37Z
- **Completed:** 2026-02-19T00:59:03Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `count_messages()` added to `gmail_client.py` — single API call, maxResults=500, returns len(messages), zero pagination
- `main.py` replaced: Phase 1 auth smoke-test removed, full CLI surface built with `--older-than`, `--before`, `--execute`
- Mutual exclusion enforced: neither arg exits 1, both args exit 1, invalid date exits 2 (Typer BadParameter)
- Dry-run path: only `.list()` read-only call made — zero write/delete API calls
- `--execute` path: `typer.confirm()` gate with cancel-exits-0 for both N response and Ctrl-C/Abort
- All 12 date_utils tests pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Add count_messages() to gmail_client.py** - `1d3337d` (feat)
2. **Task 2: Replace main.py with real CLI** - `98534a6` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `gmail_cleanup/gmail_client.py` - Added count_messages() with maxResults=500 single API call; list_messages() stub retained for Phase 3
- `gmail_cleanup/main.py` - Full CLI: --older-than (int, min=1), --before (str, validated callback), --execute (bool flag); mutual exclusion logic; dry-run output; typer.confirm() gate; deletion stub

## Decisions Made

- `count_messages()` uses a single API call with `maxResults=500` — accurate for mailboxes under 500 matching emails, approximate above. Phase 3 replaces with full pagination.
- `validate_date()` is registered as a Typer `callback` on `--before` option — this triggers exit code 2 (Typer's standard for validation errors) not exit code 1 (user-level errors). This is intentional and correct per Typer protocol.
- `HttpError` imported in `gmail_client.py` even though `count_messages()` does not catch it — intentional, preserves Phase 3/4 import stability and signals intended error-handling surface.
- User cancelling deletion (N at prompt, Ctrl-C, or `typer.Abort`) exits 0 — not an error, user changed their mind.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The `VIRTUAL_ENV` pyenv warning is cosmetic — uv correctly ignores it and uses the project `.venv`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `count_messages()` and the real CLI are ready for human verification in Plan 02-03 (live auth required)
- `--older-than` and `--before` both route through `date_utils.py` correctly — query strings verified offline
- `--execute` path is wired up to confirmation gate; deletion stub clearly marks Phase 4 boundary
- All 12 date_utils tests pass — no regressions from CLI additions

## Self-Check: PASSED

- FOUND: gmail_cleanup/gmail_client.py
- FOUND: gmail_cleanup/main.py
- FOUND: .planning/phases/02-cli-and-dry-run/02-02-SUMMARY.md
- FOUND commit: 1d3337d (feat: count_messages())
- FOUND commit: 98534a6 (feat: real CLI)

---
*Phase: 02-cli-and-dry-run*
*Completed: 2026-02-19*
