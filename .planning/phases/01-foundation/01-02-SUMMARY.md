---
phase: 01-foundation
plan: "02"
subsystem: auth
tags: [oauth2, google-auth, google-api-python-client, typer, gmail-api, token-caching]

# Dependency graph
requires:
  - phase: 01-01
    provides: "uv environment, pyproject.toml with all dependencies, .gitignore protecting credentials"
provides:
  - "gmail_cleanup/auth.py with get_credentials() and build_gmail_service() using https://mail.google.com/ scope"
  - "TOKEN_PATH at ~/.config/gmail-clean/token.json (XDG config, not CWD-relative)"
  - "CREDENTIALS_PATH at Path(__file__).parent.parent/credentials.json (project root, not os.getcwd())"
  - "gmail_cleanup/main.py Typer entry point verifying OAuth + API connection"
  - "gmail_cleanup/gmail_client.py stub for Phase 3 list_messages"
  - "gmail_cleanup/cleaner.py stub for Phase 4 batch_delete"
affects: [02-auth, 03-core-logic, 04-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OAuth scope https://mail.google.com/ required for batchDelete — NOT gmail.modify (403 on batchDelete)"
    - "Token cached at ~/.config/gmail-clean/token.json — XDG config dir, works from any invocation directory"
    - "CREDENTIALS_PATH via Path(__file__).parent.parent — project-root relative to source file, not os.getcwd()"
    - "InstalledAppFlow.run_local_server(port=0) — OS picks available port for OAuth redirect"

key-files:
  created:
    - "gmail_cleanup/auth.py"
    - "gmail_cleanup/gmail_client.py"
    - "gmail_cleanup/cleaner.py"
    - "gmail_cleanup/main.py"
  modified: []

key-decisions:
  - "Scope https://mail.google.com/ not gmail.modify — batchDelete requires full scope per googleapis/google-api-python-client#2710"
  - "TOKEN_PATH uses XDG config dir (~/.config/gmail-clean/token.json) not CWD-relative path — tool invoked from many directories"
  - "CREDENTIALS_PATH derived from Path(__file__) not os.getcwd() — ensures correct resolution regardless of invocation directory"

patterns-established:
  - "OAuth path resolution: always use Path(__file__) for package-relative paths, never os.getcwd() or hardcoded paths"
  - "Token persistence: TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True) before write — ~/.config/gmail-clean/ may not exist"
  - "Stub pattern: NotImplementedError with phase context string for unimplemented future-phase functions"

requirements-completed:
  - AUTH-02
  - AUTH-03

# Metrics
duration: 1min
completed: 2026-02-18
---

# Phase 1 Plan 2: Package Auth Module and CLI Entry Point Summary

**Full OAuth token-caching flow with https://mail.google.com/ scope, XDG token path, and Typer smoke-test entry point verifying Gmail API connection**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-18T22:26:10Z
- **Completed:** 2026-02-18T22:27:24Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- auth.py implements full OAuth token-caching flow: first run opens browser for consent, subsequent runs silently load or refresh the cached token at ~/.config/gmail-clean/token.json
- Correct scope https://mail.google.com/ enforced and documented — not gmail.modify, which returns HTTP 403 on batchDelete per upstream issue
- CREDENTIALS_PATH and TOKEN_PATH use file-system-stable resolution (Path(__file__) and Path.home()) — never breaks when tool is invoked from a different directory
- main.py Typer entry point verifies auth and API access: fetches user profile + one message ID, exits with code 1 on any error
- Two stub modules created: gmail_client.py (Phase 3) and cleaner.py (Phase 4), each raising NotImplementedError with phase context

## Task Commits

Each task was committed atomically:

1. **Task 1: Create package and auth module** - `1abdb14` (feat)
2. **Task 2: Create main.py entry point with connection smoke test** - `67f72d2` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `gmail_cleanup/auth.py` - Full OAuth flow: get_credentials(), build_gmail_service(), SCOPES, TOKEN_PATH, CREDENTIALS_PATH
- `gmail_cleanup/gmail_client.py` - Stub: list_messages() raises NotImplementedError (Phase 3)
- `gmail_cleanup/cleaner.py` - Stub: batch_delete() raises NotImplementedError (Phase 4)
- `gmail_cleanup/main.py` - Typer app: main() command authenticates, fetches profile and one message ID

## Decisions Made
- Scope is https://mail.google.com/ (not gmail.modify): batchDelete API requires the broader scope; gmail.modify returns HTTP 403. Documented in comment with upstream issue reference.
- XDG config path for token: ~/.config/gmail-clean/token.json avoids CWD dependency — this CLI will be invoked from many working directories
- Path(__file__) for credentials: ensures credentials.json is always found at project root regardless of where the tool is called from

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. The `VIRTUAL_ENV` warning from pyenv virtualenv conflict appears during all `uv run` commands — this is expected and uv correctly ignores it, using .venv instead.

The `grep -r "gmail.modify"` verification in the plan found the string in a comment line that explicitly warns NOT to use that scope. The functional SCOPES list was verified via Python import assertion — gmail.modify is not present in any functional code.

## User Setup Required

None at this stage. The OAuth flow requires credentials.json to exist at the project root (already protected by .gitignore from Plan 01-01). The first invocation of `uv run gmail-clean` will trigger the browser OAuth flow — credentials.json must exist before that run.

## Next Phase Readiness
- Full OAuth auth module ready: all downstream phases import `from gmail_cleanup.auth import build_gmail_service`
- Token caching functional: first run prompts browser, subsequent runs are silent
- CLI entry point (`uv run gmail-clean`) wired and verified via --help
- Blocker to note: GCP consent screen must be "Internal" or "Production" (not "Testing") before running OAuth flow — Testing mode tokens expire silently after 7 days

## Self-Check: PASSED

- gmail_cleanup/auth.py: FOUND
- gmail_cleanup/gmail_client.py: FOUND
- gmail_cleanup/cleaner.py: FOUND
- gmail_cleanup/main.py: FOUND
- .planning/phases/01-foundation/01-02-SUMMARY.md: FOUND
- Commit 1abdb14 (Task 1): FOUND
- Commit 67f72d2 (Task 2): FOUND

---
*Phase: 01-foundation*
*Completed: 2026-02-18*
