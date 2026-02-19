---
phase: 03-message-discovery
plan: "02"
subsystem: api
tags: [gmail-api, pagination, mock, unittest, tdd]

# Dependency graph
requires:
  - phase: 02-cli-and-dry-run
    provides: count_messages() single-call stub that this replaces with full pagination

provides:
  - list_message_ids(service, query) — paginated nextPageToken loop returning all matching message IDs
  - 7-test suite covering pagination, empty results, error propagation, and call argument verification
  - HttpError re-exported from gmail_client for Phase 4 callers

affects:
  - 03-03 (query builder upgrade — calls list_message_ids in main.py)
  - 04-deletion (cleaner.py imports list_message_ids and HttpError from gmail_client)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - nextPageToken loop pattern for Gmail API full-pagination
    - make_mock_service() helper pattern for testing Gmail API call chains

key-files:
  created:
    - tests/test_gmail_client.py
  modified:
    - gmail_cleanup/gmail_client.py

key-decisions:
  - "list_message_ids() replaces both count_messages() and list_messages() stub — callers use len() for count"
  - "HttpError kept as noqa re-export — Phase 4 (main.py, cleaner.py) imports it from gmail_client"
  - "TDD executed as RED (ImportError) -> GREEN (7/7 pass) — no REFACTOR commit needed (implementation was already clean)"

patterns-established:
  - "make_mock_service(pages): builds Gmail API mock chain via side_effect list — reusable in Phase 4 tests"
  - "nextPageToken loop: kwargs dict built each iteration, pageToken added only when non-None"

requirements-completed:
  - DISC-01

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 3 Plan 02: list_message_ids Pagination Summary

**Full-pagination message ID fetcher via nextPageToken loop replacing single-call count_messages(), with 7-test mock suite covering multi-page, empty, error, and call-arg verification**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T13:22:28Z
- **Completed:** 2026-02-19T13:23:28Z
- **Tasks:** 1 (TDD: RED + GREEN + REFACTOR)
- **Files modified:** 2

## Accomplishments

- Replaced `count_messages()` (single-call, capped at 500) and `list_messages()` stub with `list_message_ids()` that loops all pages via `nextPageToken`
- Created `tests/test_gmail_client.py` with 7 tests covering all behavioral cases including mid-pagination `HttpError` propagation
- Verified `count_messages` raises `ImportError` on import (fully removed); `list_message_ids` imports cleanly

## Task Commits

Each TDD phase committed atomically:

1. **RED: Failing tests for list_message_ids** - `d74ed9c` (test)
2. **GREEN: Implement list_message_ids** - `7b48c20` (feat)

No REFACTOR commit — implementation matched plan spec exactly, no cleanup needed.

## Files Created/Modified

- `/Users/dalwrigh/dev/gmail_cleanup/tests/test_gmail_client.py` - 7-test pagination suite using MagicMock; make_mock_service() helper pattern
- `/Users/dalwrigh/dev/gmail_cleanup/gmail_cleanup/gmail_client.py` - Replaced entirely: list_message_ids() with nextPageToken loop; HttpError re-exported

## Decisions Made

- `list_message_ids()` replaces both `count_messages()` and `list_messages()` stub — callers use `len()` for count, avoids a separate count endpoint
- `HttpError` kept with `noqa: F401` re-export comment — Phase 4 callers import it from `gmail_client` (preserves existing import contract)
- No REFACTOR commit made — GREEN implementation was already clean, matches plan spec verbatim

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `list_message_ids()` ready for integration in `main.py` (Phase 3, Plan 03)
- `HttpError` export available for Phase 4 deletion callers
- All 20 tests pass (7 new + 13 date_utils from 03-01)

---
*Phase: 03-message-discovery*
*Completed: 2026-02-19*
