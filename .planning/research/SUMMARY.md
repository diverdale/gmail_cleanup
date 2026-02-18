# Project Research Summary

**Project:** Gmail Cleanup CLI Tool
**Domain:** Gmail API Python CLI — age-based bulk email deletion
**Researched:** 2026-02-18
**Confidence:** HIGH

## Executive Summary

This is a personal-use command-line tool for bulk-deleting Gmail messages older than a specified age threshold. Expert implementations of this pattern share a consistent shape: a thin CLI layer, a credential/auth module using Google's official OAuth2 installed-app flow, a service wrapper handling pagination and rate-limited batch deletion, and an orchestration layer that threads dry-run mode through the entire pipeline. All four research streams agree on the stack, the architecture, and the critical failure modes — giving this summary unusually high confidence for a greenfield project.

The recommended approach is Python 3.12 with Typer + Rich for the CLI, the official google-api-python-client stack for Gmail access, and a four-module project structure (main.py / auth.py / gmail_client.py / cleaner.py). Deletion must use `messages.batchDelete` in chunks of 500–1000 IDs per call, gated behind the `https://mail.google.com/` OAuth scope — NOT `gmail.modify`. Dry-run mode is not optional; it must be the default behavior to protect against irreversible permanent deletion on a misconfigured date cutoff. Date queries must use Unix epoch timestamps, not formatted date strings, to avoid PST timezone edge cases.

The dominant risk in this project is not technical complexity — the Gmail API patterns are well-documented and the stack is mature — but rather the combination of irreversibility and easy misconfiguration. One wrong scope, one missing pagination loop, or one `before:YYYY/MM/DD` string instead of an epoch timestamp can cause silent data loss at scale. The mitigation strategy is build-order discipline: get OAuth and .gitignore right first, implement and validate dry-run before any live deletion code, and treat the "Looks Done But Isn't" checklist from PITFALLS.md as a mandatory phase exit gate.

---

## Key Findings

### Recommended Stack

The stack is unambiguous. Google's official Python client libraries are the only supported path; all third-party wrappers (simplegmail, etc.) are unmaintained or lack batch delete support. Typer 0.24.0 is the clear CLI choice over Click or argparse for a modern Python 3.12 project, and Rich 14.1.0 handles both progress display and summary output in a single dependency. The one non-obvious library requirement is python-dateutil for `relativedelta` month arithmetic — Python's stdlib `datetime` cannot correctly compute "6 months ago" across month-boundary edge cases.

**Core technologies:**
- Python 3.12: Runtime — required by Typer 0.24.0 (>=3.10 floor); 3.12 for best performance
- google-api-python-client 2.190.0: Gmail API access — Google's only fully supported Python client
- google-auth 2.48.0 + google-auth-oauthlib 1.2.4: Auth — successor to deprecated oauth2client; handles token refresh automatically
- Typer 0.24.0: CLI framework — type-hint-driven, minimal boilerplate, built on Click
- Rich 14.1.0: Terminal output — handles progress bars AND summary tables in one library
- python-dateutil 2.9.x: Date arithmetic — `relativedelta(months=-X)` for correct month-boundary math
- uv: Package manager — replaces pip + venv, 10-100x faster, produces uv.lock

**Critical version/scope facts:**
- `messages.batchDelete` requires `https://mail.google.com/` scope (NOT `gmail.modify`) — confirmed by open GitHub issue #2710
- `google-auth-httplib2` is deprecated as of late 2025 — do not use
- Typer 0.24.0 requires Python >=3.10; do not use with 3.8/3.9

### Expected Features

Research identified a clear MVP boundary. The table-stakes features are all low-complexity individually, but their interdependencies create a strict build order: auth before query construction, pagination before any count display, dry-run before any live deletion.

**Must have (table stakes):**
- OAuth 2.0 with token.json caching — required for all API operations; first run opens browser, subsequent runs are silent
- `--older-than` age argument with Gmail query translation — the core value proposition
- `--dry-run` flag (default on) — non-negotiable for a permanent-deletion tool; all comparable tools implement this
- Paginated email ID fetch via nextPageToken loop — required for correctness; missing this silently under-deletes on real mailboxes
- `messages.batchDelete` in chunks of 500 — performance and quota efficiency over single-delete loops
- Pre-deletion confirmation prompt — "Found N emails. Delete permanently? [y/N]" — no competitor implements this; it is a clear differentiator
- Progress display during deletion — Rich progress bar; silent tools feel broken on large runs
- Final summary: deleted count and elapsed time — completion feedback
- Exponential backoff retry on 429/5xx — required for reliability on large mailboxes

**Should have (competitive differentiators):**
- `--before YYYY-MM-DD` date argument — flexible targeting beyond relative age
- Dry-run sample listing — show first 10–20 matches (sender, subject, date) for targeting verification
- Exit codes (0/1/2) — enables scripting use cases
- `--verbose` flag for debug output and OAuth troubleshooting
- Clear first-run OAuth instructions — print actionable message when credentials.json is missing

**Defer (v2+):**
- Label/category filtering — significant scope expansion; wait for demonstrated user demand
- Multi-account support — token management complexity; niche use case for a personal tool
- Size-based filtering (`larger:5M`) — useful but orthogonal to stated scope

**Anti-features to reject:**
- Scheduler/cron integration — unattended permanent deletion is a liability; document manual cron use instead
- Undo/restore — batchDelete is irreversible; dry-run + confirmation is the correct prevention, not recovery
- GUI or web UI — different product; out of scope

### Architecture Approach

The project cleanly separates into four modules with a strict dependency chain. Authentication is isolated in auth.py so the rest of the codebase receives a ready service object and never touches credential files. The Gmail API wrapper (gmail_client.py) owns all retry logic and pagination mechanics, presenting a clean interface to the orchestration layer (cleaner.py). The CLI layer (main.py) is a thin shell — it parses arguments, validates inputs, and delegates everything to cleaner.py. This structure makes each component independently testable and keeps API mechanics isolated from business logic.

**Major components:**
1. `main.py` — CLI entrypoint (Typer); argument parsing, input validation, dispatch to cleaner
2. `auth.py` — OAuth2 flow, token.json read/write/refresh; the only module touching credential files
3. `gmail_client.py` — Gmail API wrapper; pagination generator, batchDelete with exponential backoff
4. `cleaner.py` — Orchestration; wires pagination into batch accumulator, owns dry-run logic, progress display, and summary output

**Key patterns:**
- Generator-based pagination: `list_message_ids()` yields IDs page by page — memory-efficient for large mailboxes
- Chunked batch deletion: accumulate IDs into groups of 500–1000 before calling batchDelete
- Dry-run as first-class flag: threads from CLI through cleaner through gmail_client; skip the batchDelete call but run everything else identically
- Token path resolution: resolve token.json relative to script file or `~/.config/gmail-clean/` — not bare filename (CWD-relative paths cause silent re-auth failures)

### Critical Pitfalls

Seven pitfalls were identified, three of which are project-killers if hit during development. They are listed in prevention-priority order, not severity order.

1. **Credentials committed to git before .gitignore exists** — The project already has credentials.json, client_id, and client_secret files present. Create .gitignore first, before `git init` or any commit. Add credentials.json, token.json, token.pickle, client_id, client_secret. Set `chmod 600` on all credential files.

2. **Wrong OAuth scope for batchDelete (403 error)** — Using `gmail.modify` returns 403 on every batchDelete call, even though it works for list and modify operations. Use `https://mail.google.com/` from day one. Delete token.json whenever SCOPES changes.

3. **7-day refresh token expiry in Testing mode** — If the GCP OAuth consent screen is "External" and "Testing", refresh tokens expire after 7 days silently. Fix this before first auth: set to "Internal" (Workspace) or publish to "Production". After fixing, delete token.json and re-auth.

4. **Permanent deletion is irreversible** — `messages.batchDelete` bypasses Trash entirely. Default to dry-run mode; require explicit `--execute` or `--confirm` flag for live deletion. Show count and require "y/N" confirmation before any destructive action.

5. **Pagination stops at first page** — `messages.list` returns max 500 per page; without a nextPageToken loop the tool silently processes only the first page. Always loop on nextPageToken with maxResults=500. Do not trust resultSizeEstimate.

6. **Date timezone ambiguity** — `before:YYYY/MM/DD` queries are interpreted as midnight PST, not UTC or local time. Use Unix epoch timestamps in queries instead: convert cutoff date to UTC epoch with `calendar.timegm(cutoff_date.timetuple())`.

7. **No retry on 429/503** — Gmail returns rate-limit errors under normal load on large deletion runs. Implement exponential backoff (2^attempt + random.uniform(0,1)) for 429 and 5xx responses before any production use.

---

## Implications for Roadmap

Based on the strict dependency chain identified across all four research files, a 4-phase structure is recommended. The order is not arbitrary — it reflects the build-order dependencies in ARCHITECTURE.md and the phase-to-pitfall mappings in PITFALLS.md.

### Phase 1: Foundation — Project Setup, OAuth, and Credentials

**Rationale:** Nothing else works without a valid authenticated service object. Getting OAuth wrong cascades into failures everywhere. Credential security must be established before the first commit. Both pitfalls that are hardest to recover from (credentials in git, wrong OAuth scope) must be addressed here.

**Delivers:**
- .gitignore covering all credential files (credentials.json, token.json, client_id, client_secret)
- Working OAuth flow via auth.py: InstalledAppFlow on first run, silent token refresh on subsequent runs
- Verified `https://mail.google.com/` scope (test by actually calling batchDelete with one ID)
- GCP consent screen status confirmed as Internal or Production (not Testing)
- Project skeleton: pyproject.toml, uv environment, four-module structure

**Addresses features:** OAuth 2.0 with token.json caching

**Avoids pitfalls:** Credentials committed to git; wrong OAuth scope (403); 7-day token expiry

**Exit gate:** `batchDelete` called successfully with one test message ID; token.json reused silently on second run; git status shows credential files as ignored

---

### Phase 2: CLI Layer and Dry-Run Mode

**Rationale:** Dry-run must exist and be validated before any live deletion code is written. PITFALLS.md is explicit: implement dry-run first, make it the default. The CLI surface is also where the pre-deletion confirmation prompt (a key differentiator) is defined. Implementing the full CLI contract before building deletion logic prevents the temptation to skip safety features under time pressure.

**Delivers:**
- Typer-based CLI: `--older-than`, `--before`, `--dry-run` (default), `--execute`/`--confirm`, `--help`
- Pre-deletion confirmation prompt: "Found N emails. Permanently delete? [y/N]"
- Dry-run output: count of matching emails with clear "[DRY RUN] No deletions performed" message
- Exit code contract: 0 = success, 1 = error, 2 = dry-run no-op

**Uses:** Typer 0.24.0, Rich 14.1.0

**Implements:** main.py (CLI layer), skeletal cleaner.py (dry-run path only)

**Avoids pitfalls:** Permanent delete irreversibility; silent dry-run (show counts, not just skip)

**Exit gate:** `--dry-run` flag makes zero write calls (verified with API request logging); confirmation prompt cancels cleanly on Ctrl-C

---

### Phase 3: Message Discovery — Query Construction and Pagination

**Rationale:** Pagination is required for correctness on any real mailbox. Date query construction determines which emails are targeted — getting it wrong means deleting wrong emails permanently. Both of these must be correct and verified before live deletion is wired in. This phase makes dry-run output accurate, which is also the validation step before enabling live deletion.

**Delivers:**
- `list_message_ids()` generator in gmail_client.py with full nextPageToken loop and maxResults=500
- Date-to-query translation: `--older-than 6m` → UTC epoch timestamp → `before:{epoch}` query parameter
- python-dateutil `relativedelta` for correct month arithmetic
- Accurate dry-run count verified against Gmail web UI count for same query

**Uses:** google-api-python-client, python-dateutil

**Implements:** gmail_client.py (list_message_ids), cleaner.py (pagination wiring)

**Avoids pitfalls:** Pagination stops at first page; date timezone ambiguity (use epoch, not date string)

**Exit gate:** Unit tests pass for date-to-epoch conversion at UTC boundaries; integration test against account with >500 matching emails shows count matching Gmail web UI

---

### Phase 4: Deletion Execution — Batch Delete, Retry, and Progress

**Rationale:** With auth, dry-run, and correct message discovery in place, live deletion is the final addition. Rate limiting and retry are required — not optional polish — because Gmail returns 429 under normal operation on large runs. Rich progress display is also required to prevent users from Ctrl-C'ing what looks like a hung process. This phase completes the MVP.

**Delivers:**
- `batch_delete()` in gmail_client.py: chunks IDs into groups of 500, calls batchDelete per chunk
- Exponential backoff retry: 2^attempt + jitter for 429 and 5xx; raises immediately on 400/401/403
- Rich progress bar showing current/total during deletion
- Final summary: "Deleted N emails in Xs" (or "Would delete N emails" in dry-run)
- Graceful Ctrl-C handling: progress bar closes cleanly, no traceback

**Uses:** google-api-python-client batchDelete, Rich progress, time/random for backoff

**Implements:** gmail_client.py (batch_delete, _delete_with_backoff), cleaner.py (progress + summary)

**Avoids pitfalls:** No retry on 429; messages.delete in a loop (use batchDelete); no progress indicator

**Exit gate:** Run against >100-email mailbox; observe progress bar; simulate 429 and verify retry fires; final count matches dry-run count

---

### Suggested v1.x Additions (Post-Validation)

After the core tool is working and validated on a real mailbox:

- `--before YYYY-MM-DD` flexible date argument
- Dry-run sample listing: show first 10–20 matches with sender/subject/date
- `--verbose` flag for OAuth and API debug output
- Clear first-run instructions when credentials.json is missing

---

### Phase Ordering Rationale

- **Auth before everything:** auth.py is a hard dependency for all API operations. No other phase can be validated without it.
- **Dry-run before live deletion:** PITFALLS.md is unambiguous — permanent deletion is irreversible. Dry-run must be implemented and verified before any code that calls batchDelete is written.
- **Pagination before deletion:** Without correct pagination, dry-run counts are wrong. Wrong dry-run counts means wrong deletion counts. Fix discovery first.
- **Rate limiting as part of deletion, not afterthought:** Building batchDelete without retry and immediately testing on a large mailbox produces 429 failures that corrupt the mental model of "is the tool working." Retry belongs in Phase 4, not v1.1.

### Research Flags

Phases with well-documented patterns — standard implementation, skip `/gsd:research-phase`:
- **Phase 1 (OAuth):** InstalledAppFlow pattern is canonical; STACK.md includes complete reference implementation
- **Phase 2 (CLI):** Typer patterns are standard; no novel integration challenges
- **Phase 3 (Pagination):** Generator pattern is documented and verified across multiple implementations
- **Phase 4 (Batch delete + retry):** Exponential backoff pattern is standard; quota math is confirmed

No phases require deeper research — all implementation patterns are fully documented across official Google API docs and verified open-source implementations. The primary execution risk is correctness (testing each phase gate properly), not research gaps.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI as of Feb 2026; OAuth scope requirement confirmed via official docs AND real-world GitHub issue |
| Features | HIGH | Verified against 4 comparable open-source tools; Gmail API docs confirm technical feasibility of all P1 features |
| Architecture | HIGH | Patterns sourced from official Gmail API Python quickstart and multiple community implementations; build order verified against API dependency chain |
| Pitfalls | HIGH | Critical pitfalls confirmed via official docs, open GitHub issues (issue #2710), and community sources; scope 403 bug is verified open as of Jan 2026 |

**Overall confidence: HIGH**

All four research streams used official Google API documentation as primary sources. The key technical decisions (scope, batch size, pagination pattern, date query format) are confirmed by multiple independent sources. This is unusually high confidence for a greenfield project.

### Gaps to Address

- **batchDelete ID limit:** Official docs do not state a maximum ID count per batchDelete call. Community implementations use up to 1000 safely; STACK.md recommends 500 as a conservative limit. Use 500 in implementation; monitor for errors if increased.

- **Token path convention:** ARCHITECTURE.md flags the CWD-relative token.json anti-pattern but doesn't prescribe a specific config directory. Options: path relative to script file, or `~/.config/gmail-clean/token.json`. Decide during Phase 1 setup. Recommend `~/.config/gmail-clean/` for cleaner UX across invocation contexts.

- **`--older-than` vs Gmail's `older_than` operator:** Gmail supports `older_than:6m` natively, but STACK.md notes it is "less precise, rounded to days." The epoch timestamp approach in PITFALLS.md is strictly more correct. Use epoch approach; document the precision difference in --help.

---

## Sources

### Primary (HIGH confidence)
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — OAuth installed-app flow pattern, token.json caching
- [messages.batchDelete reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete) — scope requirement (`https://mail.google.com/`), permanent deletion behavior
- [Gmail API Usage Limits](https://developers.google.com/workspace/gmail/api/reference/quota) — quota units per method, 15,000 units/user/minute limit
- [Gmail API Error Handling](https://developers.google.com/workspace/gmail/api/guides/handle-errors) — 429/5xx retryable; 400/401/403 not retryable
- [Gmail API Filtering/Search](https://developers.google.com/workspace/gmail/api/guides/filtering) — before: date syntax, PST timezone behavior
- [Gmail API List Messages](https://developers.google.com/workspace/gmail/api/guides/list-messages) — maxResults max=500, nextPageToken pattern
- [google-api-python-client on PyPI](https://pypi.org/project/google-api-python-client/) — version 2.190.0 confirmed
- [google-auth on PyPI](https://pypi.org/project/google-auth/) — version 2.48.0 confirmed
- [Typer on PyPI](https://pypi.org/project/typer/) — version 0.24.0, Python >=3.10 requirement confirmed
- [googleapis/google-api-python-client issue #2710](https://github.com/googleapis/google-api-python-client/issues/2710) — batchDelete 403 with gmail.modify scope; open as of Jan 2026

### Secondary (MEDIUM confidence)
- [mmta/gmail-cleaner](https://github.com/mmta/gmail-cleaner) — dry-run pattern, label filter, batch size reference
- [Grayda/gmail-cleanup](https://github.com/Grayda/gmail-cleanup) — production flag, age-based filter via JSON config
- [mxngls/Gmail-Cleaner](https://github.com/mxngls/Gmail-Cleaner) — batch API, retry logic, progress display
- [qualman/gmail_delete_by_filter](https://github.com/qualman/gmail_delete_by_filter) — confirms 1000 as practical batchDelete limit
- [Nango blog: Google OAuth invalid_grant](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked) — refresh token expiry patterns
- [Google Groups: 7-day refresh token limit](https://groups.google.com/g/adwords-api/c/Z_kihrf6VCE) — Testing mode token expiry community verification

---
*Research completed: 2026-02-18*
*Ready for roadmap: yes*
