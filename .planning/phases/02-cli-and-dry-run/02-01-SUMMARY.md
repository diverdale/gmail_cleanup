---
phase: 02-cli-and-dry-run
plan: "01"
subsystem: testing
tags: [pytest, python-dateutil, relativedelta, datetime, timezone, tdd]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Project scaffolding, pyproject.toml, uv package manager, gmail_cleanup package"
provides:
  - "gmail_cleanup/date_utils.py with three pure date utility functions"
  - "tests/ package with full TDD test suite (12 tests) for date utilities"
  - "pytest configured as dev dependency via uv"
affects:
  - 02-02
  - 02-03
  - main.py (CLI will call months_ago_to_cutoff and parse_date_to_cutoff)
  - gmail_client.py (will receive build_gmail_query output)

# Tech tracking
tech-stack:
  added: [pytest>=8.0 (dev), python-dateutil already in prod deps]
  patterns:
    - "TDD with RED-GREEN-REFACTOR: tests written before implementation"
    - "Pure functions with deterministic I/O for testability"
    - "Structural property testing for time-dependent functions (5-second tolerance window)"
    - "UTC-aware datetimes exclusively — no naive datetime objects"
    - "relativedelta for calendar-correct month arithmetic (not timedelta)"

key-files:
  created:
    - gmail_cleanup/date_utils.py
    - tests/__init__.py
    - tests/test_date_utils.py
  modified:
    - pyproject.toml (added [dependency-groups] dev with pytest)
    - uv.lock (updated with pytest, pluggy, iniconfig, packaging)

key-decisions:
  - "pytest added as dev dependency via [dependency-groups] in pyproject.toml, installed with uv sync --dev"
  - "months_ago_to_cutoff uses relativedelta not timedelta — ensures correct calendar-month arithmetic (e.g., 1 month before March 31 = Feb 29, not Mar 3)"
  - "Structural property tests (not exact datetime matching) for months_ago_to_cutoff — avoids time-dependent flakiness, uses 5-second tolerance window"
  - "build_gmail_query uses 'before:YYYY/MM/DD' slash format per Gmail API spec — Phase 3 will upgrade to epoch timestamp format"
  - "All datetimes are UTC-aware (tzinfo=timezone.utc) — no naive datetime objects anywhere in date_utils"

patterns-established:
  - "TDD pattern: test file committed RED before implementation file"
  - "Pure functions with no side effects — easy to test, easy to mock in integration"
  - "ValueError propagated from strptime — no custom exception wrapping needed"

requirements-completed: [CLI-01, CLI-02]

# Metrics
duration: 1min
completed: 2026-02-19
---

# Phase 02 Plan 01: Date Utilities Summary

**Three pure date utility functions (months_ago_to_cutoff, parse_date_to_cutoff, build_gmail_query) TDD-verified with 12 pytest tests covering UTC-aware datetime arithmetic and Gmail 'before:YYYY/MM/DD' query format**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T00:51:43Z
- **Completed:** 2026-02-19T00:52:58Z
- **Tasks:** 2 (RED + GREEN; no REFACTOR needed)
- **Files modified:** 5

## Accomplishments

- TDD cycle completed: failing tests committed before implementation, all 12 tests pass green
- `months_ago_to_cutoff` uses `relativedelta` for calendar-correct month subtraction (not timedelta)
- `parse_date_to_cutoff` returns UTC-aware midnight datetime and raises `ValueError` on invalid input
- `build_gmail_query` formats cutoff as `before:YYYY/MM/DD` per Gmail API slash-separated spec
- `pytest` installed as dev dependency and confirmed working in the uv-managed virtualenv

## Task Commits

Each task was committed atomically:

1. **TDD RED: Failing tests for date utility functions** - `56fb6dd` (test)
2. **TDD GREEN: date_utils.py implementation** - `a074cac` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks have two commits — test (RED) then feat (GREEN). No REFACTOR commit needed as implementation was already clean._

## Files Created/Modified

- `gmail_cleanup/date_utils.py` - Three pure functions: months_ago_to_cutoff, parse_date_to_cutoff, build_gmail_query
- `tests/__init__.py` - Empty package marker for tests directory
- `tests/test_date_utils.py` - 12 pytest tests across 3 test classes covering all functions including edge cases
- `pyproject.toml` - Added [dependency-groups] dev section with pytest>=8.0
- `uv.lock` - Updated with pytest 9.0.2, pluggy 1.6.0, iniconfig 2.3.0, packaging 26.0

## Decisions Made

- `pytest` added via `[dependency-groups]` (PEP 735, not `[project.optional-dependencies]`) — correct uv pattern for dev-only tools
- `relativedelta` chosen over `timedelta` for month arithmetic — `timedelta(days=30)` is calendar-imprecise, `relativedelta(months=N)` is exact
- Structural property tests (not exact equality) for `months_ago_to_cutoff` — time-dependent function tested with 5-second tolerance to avoid flakiness
- `build_gmail_query` uses simple `before:YYYY/MM/DD` format now; plan explicitly notes Phase 3 will upgrade to epoch timestamp

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pytest as dev dependency**
- **Found during:** TDD RED phase setup
- **Issue:** pytest not installed in project virtualenv — `uv run pytest` returned command not found
- **Fix:** Added `[dependency-groups] dev = ["pytest>=8.0"]` to pyproject.toml, ran `uv sync --dev`
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** `uv run pytest --version` returned pytest 9.0.2; tests ran successfully
- **Committed in:** `56fb6dd` (RED phase commit)

---

**Total deviations:** 1 auto-fixed (1 blocking dependency)
**Impact on plan:** pytest was a required prerequisite for TDD. Adding it as a dev dependency is the standard uv pattern. No scope creep.

## Issues Encountered

None beyond the auto-fixed pytest installation. The `VIRTUAL_ENV` pyenv warning is cosmetic — uv correctly ignores it and uses the project `.venv`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `date_utils.py` is ready to be imported by `main.py` (Phase 2 plan 02) for `--older-than` and `--before` CLI argument processing
- `build_gmail_query()` output is ready to be passed as the `query` argument to `gmail_client.count_messages()` (Phase 2 plan 03)
- All 12 tests pass and provide regression coverage for future refactoring

## Self-Check: PASSED

- FOUND: gmail_cleanup/date_utils.py
- FOUND: tests/__init__.py
- FOUND: tests/test_date_utils.py
- FOUND: .planning/phases/02-cli-and-dry-run/02-01-SUMMARY.md
- FOUND commit: 56fb6dd (test RED phase)
- FOUND commit: a074cac (feat GREEN phase)

---
*Phase: 02-cli-and-dry-run*
*Completed: 2026-02-19*
