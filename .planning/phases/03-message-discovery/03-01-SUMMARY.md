---
phase: 03-message-discovery
plan: "01"
subsystem: testing
tags: [datetime, timezone, gmail-api, epoch, tdd, date_utils]

# Dependency graph
requires:
  - phase: 02-cli-and-dry-run
    provides: "date_utils.py with before:YYYY/MM/DD query format (Phase 2 decision noted for upgrade)"
provides:
  - "Local-timezone-correct date cutoffs via parse_date_to_cutoff (end-of-day, 23:59:59)"
  - "Epoch-based Gmail queries via build_gmail_query (before:{int} format)"
  - "Updated test suite: 13 tests covering new local-tz and epoch contracts"
affects:
  - 03-message-discovery
  - 04-delete-confirmed

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "datetime.now().astimezone() for local-tz-aware current time (not timezone.utc)"
    - "strptime().replace(hour=23, minute=59, second=59).astimezone() for end-of-day local cutoff"
    - "int(cutoff.timestamp()) for Unix epoch Gmail query"

key-files:
  created: []
  modified:
    - gmail_cleanup/date_utils.py
    - tests/test_date_utils.py

key-decisions:
  - "parse_date_to_cutoff returns 23:59:59 local tz (not UTC midnight) — end-of-day semantics, no timezone boundary ambiguity"
  - "build_gmail_query emits before:{epoch} integer format — Gmail before:EPOCH eliminates date-string tz ambiguity"
  - "months_ago_to_cutoff uses datetime.now().astimezone() — local tz, consistent with parse_date_to_cutoff"
  - "timezone import removed from date_utils.py — no longer needed after switching to astimezone()"

patterns-established:
  - "TDD RED->GREEN: tests updated first (5 failing), then implementation (all 13 pass)"
  - "Epoch queries: all Gmail date queries use before:{int(epoch)} not before:YYYY/MM/DD"

requirements-completed:
  - DISC-02

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 3 Plan 01: Date Utils Timezone and Epoch Upgrade Summary

**Local-timezone end-of-day cutoffs (23:59:59) and Unix epoch Gmail queries replacing UTC-midnight date strings**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T13:22:26Z
- **Completed:** 2026-02-19T13:24:00Z
- **Tasks:** 1 (TDD: RED + GREEN phases)
- **Files modified:** 2

## Accomplishments

- Updated `parse_date_to_cutoff` to return 23:59:59 in local timezone (was UTC midnight)
- Updated `build_gmail_query` to emit `before:{epoch}` integer format (was `before:YYYY/MM/DD`)
- Updated `months_ago_to_cutoff` to use local timezone via `datetime.now().astimezone()`
- Removed `timezone` import from date_utils.py — no longer needed
- All 13 tests pass with updated contracts

## Task Commits

Each phase committed atomically per TDD protocol:

1. **RED - Update tests to new contracts** - `ec5d4ab` (test)
2. **GREEN - Implement new behavior** - `3fcb3ab` (feat)

_No REFACTOR commit needed — docstrings were updated in GREEN, no further cleanup required._

## Files Created/Modified

- `/Users/dalwrigh/dev/gmail_cleanup/gmail_cleanup/date_utils.py` - Upgraded: local-tz semantics, epoch query format, removed timezone import
- `/Users/dalwrigh/dev/gmail_cleanup/tests/test_date_utils.py` - Updated: 13 tests covering local-tz and epoch contracts (was 12 tests with UTC contracts)

## Decisions Made

- `parse_date_to_cutoff` returns end-of-day (23:59:59) in local tz — a `--before 2024-01-01` flag should mean "include all of Jan 1" not "UTC midnight which is Dec 31 in PST"
- `build_gmail_query` uses `before:{int(epoch)}` — Gmail's epoch format eliminates the tz-boundary ambiguity inherent in `before:YYYY/MM/DD`
- `months_ago_to_cutoff` switched to `datetime.now().astimezone()` for consistency with local-tz semantics
- `timezone` import removed from `date_utils.py` — `.astimezone()` with no args attaches local tz without needing the `timezone` object

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- date_utils.py now provides timezone-correct cutoffs and epoch-based Gmail queries
- All downstream plans (message list, delete) should use `build_gmail_query` output directly
- The `before:{epoch}` format is the established contract for all Gmail search queries going forward

---
*Phase: 03-message-discovery*
*Completed: 2026-02-19*
