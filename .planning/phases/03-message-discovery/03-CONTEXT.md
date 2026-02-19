# Phase 3: Message Discovery - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Full paginated email discovery with correct timezone-aware date cutoffs. Replaces Phase 2's approximate 500-email cap with an exact count via nextPageToken loop, and upgrades date queries from formatted strings to Unix epoch timestamps. No CLI flag changes, no deletion code — discovery accuracy only.

</domain>

<decisions>
## Implementation Decisions

### A: Count display output
- Use **Rich library** for dry-run output formatting (bold count, styled label)
- Display **count only** — no query string, no per-email preview
- Keep the existing "Run with --execute to delete permanently." follow-up line (already clear)
- Remove Phase 2's `~` prefix and `(approximate, up to 500 shown)` qualifier — output is now exact

### B: Pagination progress
- Show a **Rich spinner with running counter** during the paginated fetch: e.g., `⠸ Scanning... 1,234 emails found`
- Counter updates **in-place** (single line, overwritten as each page arrives)
- Appears for **all fetches** including single-page — consistent UX, no branching logic
- When fetch completes, the spinner/counter line is **replaced** by the final Rich-formatted count line

### C: Timezone semantics
- `--before YYYY-MM-DD` resolves to **end of that day in local timezone** (23:59:59 local time)
- `--older-than N` resolves "now" to **local time** (consistent with --before)
- Both are converted to Unix epoch timestamps before building the Gmail query
- Dry-run output **shows the resolved timestamp with timezone**: e.g., `Found 247 emails before 2024-01-01 23:59:59 PST`
- UTC system timezone: identical behavior, no special casing required

### D: Mid-pagination error handling (Claude's decision)
- If an API or network error occurs mid-pagination, **fail cleanly** — exit code 1 with an error message
- No partial count is shown: a partial count would be dangerous if later used to confirm deletion
- Error message format: `Error: Failed to fetch page N of results. [API error detail]. Try again.`

</decisions>

<specifics>
## Specific Ideas

- Rich spinner pattern: `rich.console.Console` with a `Live` context or manual `\r` line overwrite
- Epoch conversion: `cutoff.timestamp()` returns float Unix epoch; Gmail query format is `before:EPOCH` (integer)
- Local timezone: `datetime.now().astimezone()` captures local tz-aware datetime; `int(dt.timestamp())` for the epoch value
- `list_message_ids()` replaces Phase 2's `count_messages()` as a generator — yields all message IDs via nextPageToken loop; caller measures `len()`

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-message-discovery*
*Context gathered: 2026-02-19*
