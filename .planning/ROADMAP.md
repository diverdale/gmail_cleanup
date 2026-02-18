# Roadmap: Gmail Cleanup Tool

## Overview

Four phases, each unblocking the next. Phase 1 establishes secure OAuth before any API calls are made. Phase 2 builds the CLI surface and dry-run mode before any deletion code exists. Phase 3 makes discovery correct (pagination and date queries) so dry-run output is trustworthy. Phase 4 adds live deletion with retry and progress. The build order is not arbitrary — it reflects hard API dependencies and the irreversibility of batchDelete.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Secure project setup with working OAuth authentication
- [ ] **Phase 2: CLI and Dry-run** - Full CLI surface with dry-run as default and confirmation gate
- [ ] **Phase 3: Message Discovery** - Correct pagination and date-to-query translation
- [ ] **Phase 4: Deletion** - Live batch deletion with retry, progress display, and summary

## Phase Details

### Phase 1: Foundation
**Goal**: User can authenticate with Gmail securely, credentials are never committed, and the project skeleton is ready to build on
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03
**Success Criteria** (what must be TRUE):
  1. Running `git status` shows credentials.json, token.json, client_id, and client_secret as ignored — they never appear as untracked files
  2. First run opens a browser OAuth prompt; second run completes silently (token reused from token.json)
  3. The authenticated service object can successfully call a Gmail API endpoint (confirmed by listing one message)
  4. The project has a working uv environment with dependencies installable from pyproject.toml
**Plans**: TBD

### Phase 2: CLI and Dry-run
**Goal**: User can invoke the tool with age or date arguments and see what would be deleted — without any deletion occurring by default
**Depends on**: Phase 1
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04
**Success Criteria** (what must be TRUE):
  1. `gmail-clean --older-than 6` runs without error and reports how many emails match (dry-run output)
  2. `gmail-clean --before 2024-01-01` runs without error and reports how many emails match (dry-run output)
  3. Running the tool without `--execute` makes zero write/delete API calls (verifiable via API request logging)
  4. Passing `--execute` displays "Found N emails. Delete permanently? [y/N]" and cancels cleanly on "N" or Ctrl-C
**Plans**: TBD

### Phase 3: Message Discovery
**Goal**: The tool finds every email matching the filter — no silent truncation — and the date cutoff is timezone-correct
**Depends on**: Phase 2
**Requirements**: DISC-01, DISC-02
**Success Criteria** (what must be TRUE):
  1. Dry-run count for a mailbox with >500 matching emails matches the count shown in Gmail web UI for the same query
  2. `--older-than 6` and `--before YYYY-MM-DD` produce a Gmail query using a Unix epoch timestamp (not a formatted date string)
**Plans**: TBD

### Phase 4: Deletion
**Goal**: User can permanently delete matched emails in bulk, with progress shown during the run and a count summary at the end
**Depends on**: Phase 3
**Requirements**: DEL-01, DEL-02, DEL-03, DEL-04
**Success Criteria** (what must be TRUE):
  1. After confirming deletion, emails are removed from Gmail in batches (progress bar shows current/total)
  2. A 429 or 5xx response triggers automatic retry with exponential backoff — the run does not fail
  3. After completion, tool prints count of deleted emails and elapsed time
  4. Final deleted count matches the count shown during the pre-deletion dry-run for the same query
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/TBD | Not started | - |
| 2. CLI and Dry-run | 0/TBD | Not started | - |
| 3. Message Discovery | 0/TBD | Not started | - |
| 4. Deletion | 0/TBD | Not started | - |
