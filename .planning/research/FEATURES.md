# Feature Research

**Domain:** Gmail bulk-deletion CLI tool (Python, OAuth, age-based)
**Researched:** 2026-02-18
**Confidence:** HIGH (verified against live repos and Gmail API official docs)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| OAuth 2.0 authentication with token caching | Every Gmail API tool does this; without it users must re-auth every run | LOW | token.json persists refresh token; handle expiry/revocation gracefully. Requires `https://mail.google.com/` scope for batchDelete |
| Age-based filter (`older_than:Xm` or `before:YYYY/MM/DD`) | This is the core value proposition — without it the tool has no targeting | LOW | Gmail API query syntax supports `older_than:6m` and `before:2024/01/01`; pass directly as search query |
| Dry-run mode | Users are terrified of accidental permanent deletion; this is non-negotiable | LOW | List matching emails with count; print summary; take zero destructive actions. All comparable tools (mmta/gmail-cleaner, Grayda/gmail-cleanup) implement this |
| Final count / summary output | Users need to know what happened — how many deleted, how long it took | LOW | Print: "Deleted N emails older than X months." at exit |
| Progress display during deletion | Deleting thousands of emails takes time; silent tools feel broken/hung | LOW | tqdm or rich progress bar; show current/total count as batches process |
| Permanent deletion (not trash) | The explicit goal is to reclaim storage and truly remove emails | LOW | Use `messages.batchDelete` — bypasses trash, permanent. `messages.trash` is wrong for this use case |
| Batch deletion (not one-by-one) | Single-delete of 10,000 emails is painfully slow and quota-wasteful | MEDIUM | `messages.batchDelete` accepts up to 1,000 IDs per call (50 quota units vs 10 per individual delete); chunk list into batches of 500-1000 |
| Graceful error handling with retry | Gmail API returns 429/503 under load; without retry, large jobs fail mid-run | MEDIUM | Exponential backoff with jitter; all comparable tools implement this |
| Help output (`--help`) | Standard CLI contract; absence is jarring | LOW | argparse/click provides this for free |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Human-readable age input (`--older-than 6m`, `--older-than 1y`, `--before 2023-01-01`) | Most tools use Gmail query syntax directly, which leaks implementation; clean UX translates user intent to API query internally | LOW | Parse `6m` → `older_than:6m` or compute `before:` date; validate input clearly |
| Pre-deletion count confirmation prompt | Show "Found 4,823 emails. Delete permanently? [y/N]" before acting — critical for destructive ops | LOW | Standard in well-designed destructive CLI tools; mmta/gmail-cleaner omits this; meaningful safety without dry-run overhead |
| Verbose listing in dry-run (sample of matches) | Dry-run that only shows a count is less useful than showing a sample (sender, subject, date) | LOW | Show first 10-20 matches so user can verify targeting is correct |
| Clear OAuth setup instructions on first run | Many users fail at the GCP console setup step; good first-run UX reduces abandonment | LOW | Print actionable error message when credentials.json is missing or stale |
| Exit code contract (`0` = success, `1` = error, `2` = dry-run-no-op`) | Enables scripting; professional CLI tools follow this; most Gmail scripts ignore it | LOW | Critical if user ever wraps in a shell script |
| Chunked pagination for large mailboxes | Gmail API `messages.list` returns max 500 per page; naively iterating without pagination misses emails | MEDIUM | Must implement `nextPageToken` loop; without it tool silently under-deletes on large mailboxes |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Label/category filtering (Promotions, Social, etc.) | Users want finer control; seems useful | Adds significant complexity, changes the tool's scope from "delete by age" to "delete by age+label"; label IDs vary by account; out of scope for this project | Keep simple: all-mail deletion by age is the stated requirement |
| Scheduler / cron integration | Users want set-and-forget cleanup | Unattended permanent deletion is a liability; OAuth token can expire or be revoked mid-schedule causing silent failure; scheduler state management is a separate problem | Document how to use the tool with system cron manually; don't build the scheduler into the tool |
| Undo / restore from trash | Users panic after deletion and want rollback | `batchDelete` is permanent and irreversible by design; building a "restore" feature is impossible post-delete; a pre-delete export would require massive storage | Implement dry-run + confirmation prompt instead; these prevent accidents |
| Per-sender or subject filtering | More powerful targeting | Dramatically expands scope; turns a focused tool into a generic query runner; most tools that add this become complex to use correctly | Out of scope for v1; Gmail web UI handles ad-hoc filtering well |
| Starred/important email exclusions | Users worry about losing important mail | The project explicitly states no exclusions; adding opt-in exclusion logic complicates CLI surface and filter construction | Clear documentation in --help: "all mail matching the age filter is deleted, including starred and important" |
| GUI or web UI | Lower technical barrier | Completely different product; massive complexity increase; credential storage becomes a security concern in web context | This is a CLI tool for technical users; web UI is a separate project |
| Multi-account support | Power users manage multiple accounts | Token management for N accounts multiplies complexity; out of scope for v1 | Single-account OAuth; users can re-auth with different account by deleting token.json |
| Email preview / read in terminal | Users want to see content before deleting | High complexity (MIME parsing, attachment handling, encoding); TUI implementation is a project unto itself | Dry-run shows sender/subject/date sample — sufficient for targeting verification |

---

## Feature Dependencies

```
OAuth Authentication (token.json caching)
    └──required by──> All Gmail API operations

Age Filter (CLI arg parsing)
    └──required by──> Gmail API query construction
                          └──required by──> Email ID list fetching
                                               └──required by──> Dry-run count display
                                               └──required by──> Batch deletion

Pagination (nextPageToken loop)
    └──required by──> Complete email ID list (large mailboxes)
                          └──required by──> Accurate dry-run count
                          └──required by──> Complete batch deletion

Batch Deletion (batchDelete API)
    └──enhanced by──> Progress display (tqdm/rich)
    └──enhanced by──> Retry logic (exponential backoff)
    └──enhanced by──> Pre-deletion confirmation prompt

Dry-run mode ──conflicts with──> Actual deletion (mutually exclusive execution paths)
```

### Dependency Notes

- **OAuth required by everything:** The first step in every run is obtaining valid credentials. Token refresh must happen before any API call.
- **Pagination required for correctness:** Without iterating `nextPageToken`, `messages.list` returns at most 500 results. A mailbox with 50,000 old emails would silently delete only 500 without this.
- **Age filter required by query construction:** The Gmail API `q=` parameter accepts `older_than:Xm` or `before:YYYY/MM/DD` directly. The CLI must translate user input to one of these forms.
- **Batch deletion enhanced by retry:** `batchDelete` at scale will hit rate limits (15,000 quota units/user/minute at 50 units per batchDelete call = ~300 batch calls/minute theoretical max). Retry logic is not optional for production reliability.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept and safely use the tool.

- [ ] OAuth 2.0 authentication with token.json caching — required for any Gmail API access
- [ ] `--older-than` CLI argument (months) with translation to Gmail query — the core value prop
- [ ] `--dry-run` flag — mandatory safety mechanism for a permanent-deletion tool
- [ ] Paginated email ID fetch (nextPageToken loop) — required for correctness on real mailboxes
- [ ] Batch deletion via `messages.batchDelete` in chunks of 500 — performance and quota efficiency
- [ ] Pre-deletion confirmation prompt (count + y/N) — safety without friction
- [ ] Progress display during deletion — user feedback for long-running operations
- [ ] Final summary: deleted count, elapsed time — completion feedback
- [ ] Retry with exponential backoff — reliability for large jobs
- [ ] `--help` with clear argument documentation — standard CLI contract

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] `--before YYYY-MM-DD` date argument — flexible targeting beyond relative age
- [ ] Dry-run sample output (show first N matches with sender/subject/date) — richer dry-run verification
- [ ] Exit codes (0/1/2) — enables scripting use cases
- [ ] `--verbose` flag for debug output — troubleshooting OAuth and API issues

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Label/category filtering — significant scope expansion; wait for user demand
- [ ] Multi-account support — token management complexity; niche use case
- [ ] Size-based filtering (`larger:5M`) — useful but orthogonal to current scope

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| OAuth + token caching | HIGH | LOW | P1 |
| `--older-than` arg + query translation | HIGH | LOW | P1 |
| Dry-run mode | HIGH | LOW | P1 |
| Paginated ID fetch | HIGH | MEDIUM | P1 |
| Batch deletion (batchDelete) | HIGH | LOW | P1 |
| Pre-deletion confirmation prompt | HIGH | LOW | P1 |
| Progress display | MEDIUM | LOW | P1 |
| Summary count output | MEDIUM | LOW | P1 |
| Retry / exponential backoff | HIGH | MEDIUM | P1 |
| `--before DATE` argument | MEDIUM | LOW | P2 |
| Dry-run sample listing | MEDIUM | LOW | P2 |
| Exit codes | LOW | LOW | P2 |
| `--verbose` flag | LOW | LOW | P2 |
| Label filtering | LOW | HIGH | P3 |
| Multi-account | LOW | HIGH | P3 |
| Size filtering | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | mmta/gmail-cleaner | Grayda/gmail-cleanup | mxngls/Gmail-Cleaner | marin117/Gmail-deleter | This Project |
|---------|-------------------|---------------------|---------------------|----------------------|--------------|
| Dry-run mode | YES (`--dry-run`) | YES (no `--production` = preview mode) | NO | NO | YES (required) |
| Batch deletion | YES (1000/batch) | YES (500/batch) | YES (batch API) | YES | YES (500-1000/batch) |
| Progress display | YES (`--verbose`) | Implicit via log output | YES (real-time) | Minimal | YES (tqdm/rich) |
| Age-based filter | Via Gmail query (`-q`) | Via JSON config (duration field) | NO (sender/label only) | NO (category only) | YES (primary feature) |
| Label/category filter | YES (`--label`) | YES (JSON config) | YES | YES | NO (out of scope v1) |
| Confirmation prompt | NO | NO | NO | NO | YES (differentiator) |
| Paginated fetch | Implied | YES (`--maxresults`) | YES | YES | YES (required) |
| OAuth token caching | YES (token.json) | YES (credentials file) | YES | YES | YES (token.json) |
| Retry / backoff | Implied | Partial (log-level) | YES (explicit) | NO | YES (required) |
| Permanent delete | YES (batchDelete) | YES (trash action) | NO (trash only) | YES (permanent) | YES (batchDelete) |

---

## Sources

- [mmta/gmail-cleaner — dry-run, label filter, batch](https://github.com/mmta/gmail-cleaner)
- [Grayda/gmail-cleanup — production flag, JSON config, age-based](https://github.com/Grayda/gmail-cleanup)
- [mxngls/Gmail-Cleaner — batch API, retry, progress](https://github.com/mxngls/Gmail-Cleaner)
- [marin117/Gmail-deleter — simple permanent delete](https://github.com/marin117/Gmail-deleter)
- [Gmail API: messages.batchDelete reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete)
- [Gmail API quota / rate limits](https://developers.google.com/workspace/gmail/api/reference/quota)
- [Gmail API batching guide](https://developers.google.com/workspace/gmail/api/guides/batch)
- [Google OAuth token.json caching pattern (Python quickstart)](https://developers.google.com/gmail/api/quickstart/python)

---
*Feature research for: Gmail cleanup CLI tool (Python, OAuth, age-based bulk deletion)*
*Researched: 2026-02-18*
