# Requirements: Gmail Cleanup Tool

**Defined:** 2026-02-18
**Core Value:** Delete old Gmail messages reliably from the command line — with a dry-run preview before committing to deletion.

## v1 Requirements

### Auth & Setup

- [ ] **AUTH-01**: Project is initialized with .gitignore covering all credential files (credentials.json, token.json, client_id, client_secret) before any commit
- [ ] **AUTH-02**: User can authenticate with Gmail via OAuth on first run (browser prompt) with silent token refresh on subsequent runs
- [ ] **AUTH-03**: Tool uses `https://mail.google.com/` scope to enable permanent batch deletion

### CLI

- [ ] **CLI-01**: User can run `gmail-clean --older-than N` to target emails older than N months
- [ ] **CLI-02**: User can run `gmail-clean --before YYYY-MM-DD` to target emails older than a specific date
- [ ] **CLI-03**: Tool runs in dry-run mode by default; user must pass `--execute` (or equivalent) to perform live deletion
- [ ] **CLI-04**: Before live deletion, tool shows count of matching emails and prompts "Delete permanently? [y/N]" requiring explicit confirmation

### Message Discovery

- [ ] **DISC-01**: Tool fetches all matching email IDs using paginated API calls (nextPageToken loop, maxResults=500) — no silent truncation at 500 emails
- [ ] **DISC-02**: Date cutoff is translated to a Unix epoch timestamp for the Gmail query (avoids PST/UTC timezone edge cases)

### Deletion

- [ ] **DEL-01**: Emails are deleted permanently in batches of 500 IDs per API call via messages.batchDelete
- [ ] **DEL-02**: Tool retries on HTTP 429 and 5xx responses with exponential backoff; raises immediately on 400/401/403
- [ ] **DEL-03**: Progress is shown during deletion (current / total emails processed)
- [ ] **DEL-04**: After completion, tool prints a summary: count deleted (or would-delete in dry-run) and elapsed time

## v2 Requirements

### CLI Enhancements

- **CLI-V2-01**: `--verbose` flag for OAuth and Gmail API debug output
- **CLI-V2-02**: Exit codes: 0 = success, 1 = error, 2 = dry-run no-op (enables scripting)
- **CLI-V2-03**: Clear first-run error message when credentials.json is missing

### Discovery Enhancements

- **DISC-V2-01**: Dry-run sample listing: show first 10–20 matches (sender, subject, date) for targeting verification

## Out of Scope

| Feature | Reason |
|---------|--------|
| Label/category filtering | Scope expansion; user explicitly targets all email by age |
| Scheduler / cron integration | Unattended permanent deletion is a liability; user runs CLI manually |
| Multi-account support | Personal tool; token management complexity not warranted |
| Archive instead of delete | User wants deletion only |
| Undo / restore | batchDelete is irreversible by design; dry-run + confirmation is the prevention strategy |
| GUI or web UI | Different product |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| AUTH-03 | Phase 1 | Pending |
| CLI-01 | Phase 2 | Pending |
| CLI-02 | Phase 2 | Pending |
| CLI-03 | Phase 2 | Pending |
| CLI-04 | Phase 2 | Pending |
| DISC-01 | Phase 3 | Pending |
| DISC-02 | Phase 3 | Pending |
| DEL-01 | Phase 4 | Pending |
| DEL-02 | Phase 4 | Pending |
| DEL-03 | Phase 4 | Pending |
| DEL-04 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 after roadmap creation*
