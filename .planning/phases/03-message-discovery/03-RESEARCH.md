# Phase 3: Message Discovery - Research

**Researched:** 2026-02-19
**Domain:** Gmail API pagination, Python timezone/epoch conversion, Rich terminal spinner
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### A: Count display output
- Use **Rich library** for dry-run output formatting (bold count, styled label)
- Display **count only** — no query string, no per-email preview
- Keep the existing "Run with --execute to delete permanently." follow-up line (already clear)
- Remove Phase 2's `~` prefix and `(approximate, up to 500 shown)` qualifier — output is now exact

#### B: Pagination progress
- Show a **Rich spinner with running counter** during the paginated fetch: e.g., `Scanning... 1,234 emails found`
- Counter updates **in-place** (single line, overwritten as each page arrives)
- Appears for **all fetches** including single-page — consistent UX, no branching logic
- When fetch completes, the spinner/counter line is **replaced** by the final Rich-formatted count line

#### C: Timezone semantics
- `--before YYYY-MM-DD` resolves to **end of that day in local timezone** (23:59:59 local time)
- `--older-than N` resolves "now" to **local time** (consistent with --before)
- Both are converted to Unix epoch timestamps before building the Gmail query
- Dry-run output **shows the resolved timestamp with timezone**: e.g., `Found 247 emails before 2024-01-01 23:59:59 PST`
- UTC system timezone: identical behavior, no special casing required

#### D: Mid-pagination error handling (Claude's decision)
- If an API or network error occurs mid-pagination, **fail cleanly** — exit code 1 with an error message
- No partial count is shown: a partial count would be dangerous if later used to confirm deletion
- Error message format: `Error: Failed to fetch page N of results. [API error detail]. Try again.`

### Claude's Discretion

None listed — all areas covered by locked decisions.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DISC-01 | Tool fetches all matching email IDs using paginated API calls (nextPageToken loop, maxResults=500) — no silent truncation at 500 emails | Gmail API pagination pattern: `list()` → check `nextPageToken` → loop with `pageToken` param; `list_next()` helper also available |
| DISC-02 | Date cutoff is translated to a Unix epoch timestamp for the Gmail query (avoids PST/UTC timezone edge cases) | Python `datetime.now().astimezone()` captures local-tz-aware datetime; `.replace(hour=23, minute=59, second=59)` for end-of-day; `int(dt.timestamp())` for epoch; Gmail query `before:EPOCH` format confirmed |
</phase_requirements>

---

## Summary

Phase 3 makes two targeted upgrades to an existing working tool: (1) replace the single-call 500-email cap with a nextPageToken pagination loop, and (2) replace the `before:YYYY/MM/DD` Gmail query with a Unix epoch timestamp. Both changes are localized — `gmail_client.py` for pagination, `date_utils.py` for epoch conversion, and `main.py` for wiring + Rich output.

The Gmail API's `users.messages.list` response includes a `nextPageToken` field when more pages exist. Passing it as `pageToken` in the next call retrieves the next page. The loop terminates when `nextPageToken` is absent. Each page can return up to 500 results (`maxResults=500`). The `resultSizeEstimate` field in the response is explicitly an estimate and must NOT be used instead of counting — pagination is required for accuracy.

Python's `datetime.now().astimezone()` returns a local-timezone-aware datetime. Chaining `.replace(hour=23, minute=59, second=59)` on a parsed date produces end-of-day in local time. `int(dt.timestamp())` converts any tz-aware datetime to a UTC-correct Unix epoch. Gmail accepts `before:EPOCH` (integer) format. Rich's `console.status()` / `status.update()` provides the in-place spinner with updating text; no custom terminal manipulation is needed.

**Primary recommendation:** Implement `list_message_ids()` as a generator in `gmail_client.py` using a `while True` / `break` loop over `nextPageToken`; update `date_utils.py` to return local-tz end-of-day datetimes and emit epoch timestamps; wire the spinner in `main.py` using `with console.status(...) as status:` + `status.update(...)` per page.

---

## Standard Stack

### Core (already installed in project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `rich` | 14.1.0 | Terminal spinner + final count formatting | Already in pyproject.toml; `Console.status()` is the idiomatic in-place spinner API |
| `google-api-python-client` | 2.190.0 | Gmail API pagination | Already installed; `service.users().messages().list()` + `pageToken` is the official pattern |
| `python-dateutil` | (pinned in lock) | relativedelta for month arithmetic | Already used in Phase 2; no new dependency needed |

### No New Dependencies Required

All needed libraries are already present in `pyproject.toml`. Phase 3 adds no new packages.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `console.status()` + `status.update()` | `rich.live.Live` + manual `Spinner` renderable | `status()` is simpler API for this use case; `Live` is for complex multi-line layouts |
| `console.status()` + `status.update()` | Manual `\r` line overwrite with `print(..., end='\r')` | `status()` handles terminal width, spinner animation, and cleanup automatically |
| `int(dt.timestamp())` | `calendar.timegm(dt.timetuple())` | `timestamp()` on an aware datetime is correct and simpler; `timegm` requires UTC timetuple |

---

## Architecture Patterns

### Recommended Change Scope

```
gmail_cleanup/
├── date_utils.py        # Change: parse_date_to_cutoff() → end-of-day local time
│                        # Change: months_ago_to_cutoff() → local time (not UTC)
│                        # Change: build_gmail_query() → before:EPOCH format
├── gmail_client.py      # Replace: count_messages() → list_message_ids() generator
│                        #          full pagination loop, maxResults=500
└── main.py              # Wire: spinner context, status.update() per page
                         # Wire: final Rich print with bold count
                         # Wire: updated dry-run output with timestamp+tz string

tests/
├── test_date_utils.py   # Update: existing tests for parse/months, add epoch tests
└── test_gmail_client.py # Add: pagination tests with mocked service
```

### Pattern 1: Gmail API nextPageToken Pagination Loop

**What:** Loop calling `list()` with `pageToken` until response has no `nextPageToken`.
**When to use:** Any time you need a complete result set from the Gmail API.

```python
# Source: https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html
def list_message_ids(service, query: str) -> list[dict]:
    """Fetch all message IDs matching query via paginated API calls."""
    messages = []
    page_token = None
    page_num = 0

    while True:
        page_num += 1
        kwargs = {"userId": "me", "q": query, "maxResults": 500}
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            result = service.users().messages().list(**kwargs).execute()
        except HttpError as exc:
            raise RuntimeError(
                f"Failed to fetch page {page_num} of results. {exc}. Try again."
            ) from exc

        messages.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return messages
```

Note: `list_next(previous_request, previous_response)` is also available as a helper that returns `None` when pagination is exhausted, but the explicit `while True` / `pageToken` loop is clearer and matches the CONTEXT.md spec for a page counter in error messages.

### Pattern 2: Local-Timezone End-of-Day Epoch Conversion

**What:** Convert a YYYY-MM-DD string or relative-months value to a local-timezone-aware end-of-day datetime, then to Unix epoch integer.
**When to use:** Both `--before` and `--older-than` paths; produces `before:EPOCH` Gmail query.

```python
# Source: https://docs.python.org/3/library/datetime.html
from datetime import datetime

def parse_date_to_cutoff(date_str: str) -> datetime:
    """Parse YYYY-MM-DD to end-of-day in local timezone (23:59:59 local time)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    # astimezone() with no args attaches the OS local timezone
    local_dt = dt.replace(hour=23, minute=59, second=59).astimezone()
    return local_dt

def months_ago_to_cutoff(months: int) -> datetime:
    """Return local-tz-aware datetime N calendar months before now."""
    # datetime.now().astimezone() = current local time, tz-aware
    return datetime.now().astimezone() - relativedelta(months=months)

def build_gmail_query(cutoff: datetime) -> str:
    """Convert cutoff to Gmail epoch query: before:EPOCH."""
    # timestamp() on a tz-aware datetime is always UTC-correct
    epoch = int(cutoff.timestamp())
    return f"before:{epoch}"
```

Key: `datetime.now().astimezone()` is the Python docs-recommended pattern. `dt.timestamp()` on a tz-aware datetime computes `(dt - 1970-01-01 UTC).total_seconds()` — always correct regardless of local timezone.

### Pattern 3: Rich Spinner with In-Place Counter

**What:** `console.status()` context manager with `status.update()` called per page.
**When to use:** During the paginated fetch to show live progress.

```python
# Source: https://rich.readthedocs.io/en/stable/reference/status.html
from rich.console import Console

console = Console()

def count_all_messages(service, query: str) -> int:
    """Fetch all messages with spinner progress. Returns exact count."""
    total = 0
    page_num = 0

    with console.status("Scanning... 0 emails found", spinner="dots") as status:
        # list_message_ids() is called page by page (or caller loops)
        # For spinner integration, pagination lives here or is called here:
        page_token = None
        while True:
            page_num += 1
            kwargs = {"userId": "me", "q": query, "maxResults": 500}
            if page_token:
                kwargs["pageToken"] = page_token
            try:
                result = service.users().messages().list(**kwargs).execute()
            except HttpError as exc:
                raise RuntimeError(
                    f"Error: Failed to fetch page {page_num} of results. {exc}. Try again."
                ) from exc
            batch = result.get("messages", [])
            total += len(batch)
            status.update(f"Scanning... {total:,} emails found")
            page_token = result.get("nextPageToken")
            if not page_token:
                break
    # After `with` block exits, spinner line is replaced by return value display
    return total
```

`status.update(status=...)` accepts a string; the spinner animation continues while text updates in-place. The context manager's `__exit__` clears the spinner line automatically — `main.py` then prints the final Rich-formatted count below it.

### Pattern 4: Final Rich-Formatted Count Output

**What:** Replace `typer.echo` dry-run output with `console.print` using Rich markup.
**When to use:** After the spinner completes, display the exact count.

```python
# Source: https://rich.readthedocs.io/en/stable/console.html
from rich.console import Console

console = Console()

# After spinner completes and count is known:
console.print(f"[bold]Found {count:,} emails[/bold] before {cutoff_str}.")
console.print("Run with --execute to delete permanently.")
```

`cutoff_str` is formatted as `YYYY-MM-DD HH:MM:SS TZ` from the tz-aware cutoff datetime.

### Anti-Patterns to Avoid

- **Using `resultSizeEstimate`:** The Gmail API response includes `resultSizeEstimate` but it is explicitly documented as an estimate. Do not use it as the count — paginate and count IDs.
- **Mixing naive and aware datetimes:** `datetime.strptime(...)` returns a naive datetime. Call `.astimezone()` immediately after any manipulation (e.g., `.replace(hour=23, ...)`) to attach local timezone before calling `.timestamp()`.
- **Passing a naive datetime to `.timestamp()`:** Python docs state naive datetimes are assumed local time by `mktime()`, which is platform-dependent and can be wrong on systems with unusual timezone configs. Always use tz-aware datetimes.
- **Showing partial count on pagination error:** Decision D locks this: fail cleanly, show no count, exit code 1.
- **Branching spinner logic for single vs. multi-page:** Decision B locks this: spinner always appears. No `if page_count > 1:` branching.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-place terminal spinner | Manual `\r` + ANSI escape codes | `rich.console.Console.status()` | Handles terminal width, Windows compat, cleanup on exit |
| Epoch timestamp from local date | Manual UTC offset arithmetic | `dt.astimezone()` + `int(dt.timestamp())` | Python stdlib handles DST, historical offsets, platform differences |
| Pagination helper | Custom retry/loop with state machine | Simple `while True` + `nextPageToken` check | The API contract is simple; no helper library needed |

**Key insight:** The Python datetime stdlib handles all local-timezone-to-epoch edge cases correctly via `astimezone()` + `timestamp()`. Custom UTC offset math will break on DST boundaries.

---

## Common Pitfalls

### Pitfall 1: Naive Datetime Passed to `.timestamp()`

**What goes wrong:** `datetime.strptime("2024-01-01", "%Y-%m-%d").timestamp()` returns an epoch value relative to the local timezone's midnight, not necessarily the intended cutoff.
**Why it happens:** `strptime` returns a naive datetime; `timestamp()` on a naive datetime assumes local time (via `mktime()`), which is correct — but only if you intended local time. The bug is subtle: if the intent was UTC midnight, the value is wrong.
**How to avoid:** Always call `.astimezone()` after constructing the datetime to make it explicitly tz-aware. Then `.timestamp()` is unambiguous.
**Warning signs:** Tests passing on a UTC machine but failing when run by a user in PST/EST.

### Pitfall 2: `resultSizeEstimate` Treated as Exact Count

**What goes wrong:** Using `result.get("resultSizeEstimate", 0)` from the first page as the total count — skipping pagination entirely.
**Why it happens:** The field is present in the first page response and looks like a total count.
**How to avoid:** Ignore `resultSizeEstimate`. Count IDs by paginating all pages.
**Warning signs:** Count doesn't match Gmail web UI for mailboxes with >500 emails.

### Pitfall 3: Empty `messages` Key on Last Page

**What goes wrong:** Calling `result["messages"]` raises `KeyError` when the last page has no messages (e.g., query returns exactly a multiple of 500 results on a prior page).
**Why it happens:** Gmail API omits the `messages` key entirely (rather than returning `[]`) when a page has zero results.
**How to avoid:** Always use `result.get("messages", [])`.
**Warning signs:** `KeyError: 'messages'` exception during pagination of large exact-multiple-of-500 mailboxes.

### Pitfall 4: End-of-Day Calculation Before `astimezone()`

**What goes wrong:** `datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59).astimezone()` — order matters. `.replace()` on a naive datetime then `.astimezone()` is correct. But `.astimezone()` then `.replace(hour=23, ...)` would set 23:59:59 in the original timezone (UTC) not local time.
**Why it happens:** Confusion about whether `.replace()` mutates the timezone component.
**How to avoid:** Sequence is: `strptime` → `replace(hour=23, minute=59, second=59)` → `astimezone()`. Set the time components first on the naive datetime, then attach local timezone.
**Warning signs:** Cutoff is off by the UTC offset hours (e.g., 8 hours off for PST).

### Pitfall 5: Existing Tests Break on Updated `parse_date_to_cutoff`

**What goes wrong:** Phase 2 tests assert `parse_date_to_cutoff("2024-01-01") == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)`. Phase 3 changes this function to return end-of-day local time — the UTC-midnight assertion is now wrong.
**Why it happens:** The function contract changes fundamentally in Phase 3.
**How to avoid:** Update `test_date_utils.py` alongside `date_utils.py`. New assertion: result is tz-aware, has `hour=23, minute=59, second=59`, and `tzinfo` is the local timezone (not `timezone.utc`).
**Warning signs:** `test_valid_date_returns_utc_midnight` fails after Phase 3 changes.

### Pitfall 6: `build_gmail_query` Tests Assert Old Format

**What goes wrong:** Existing tests assert `result == "before:2024/01/01"`. Phase 3 changes to `before:EPOCH` — string format tests break.
**Why it happens:** Same — function contract changes.
**How to avoid:** Replace old format tests with epoch-format assertions. Test that the returned string starts with `before:` followed by an integer, and that the integer is within a small window of the expected epoch value.
**Warning signs:** `test_formats_with_slashes_not_hyphens` fails after Phase 3 changes.

---

## Code Examples

Verified patterns from official sources:

### Gmail API: nextPageToken Pagination

```python
# Source: https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html
# Pattern: loop until nextPageToken absent

page_token = None
all_messages = []
page_num = 0

while True:
    page_num += 1
    request_kwargs = {"userId": "me", "q": query, "maxResults": 500}
    if page_token:
        request_kwargs["pageToken"] = page_token

    result = service.users().messages().list(**request_kwargs).execute()
    all_messages.extend(result.get("messages", []))

    page_token = result.get("nextPageToken")
    if not page_token:
        break
```

### Python: Local Timezone End-of-Day to Epoch

```python
# Source: https://docs.python.org/3/library/datetime.html
from datetime import datetime

# For --before YYYY-MM-DD: end of that day in local timezone
dt_naive = datetime.strptime("2024-01-01", "%Y-%m-%d")
dt_end_of_day_local = dt_naive.replace(hour=23, minute=59, second=59).astimezone()
epoch = int(dt_end_of_day_local.timestamp())
# epoch is now UTC-correct regardless of system timezone

# For --older-than N: N months ago in local time
from dateutil.relativedelta import relativedelta
cutoff = datetime.now().astimezone() - relativedelta(months=6)
epoch = int(cutoff.timestamp())

# Gmail query:
query = f"before:{epoch}"
```

### Rich: Spinner with In-Place Counter

```python
# Source: https://rich.readthedocs.io/en/stable/reference/status.html
from rich.console import Console

console = Console()

with console.status("Scanning... 0 emails found", spinner="dots") as status:
    total = 0
    # ... pagination loop ...
    for each_page_batch in ...:
        total += len(each_page_batch)
        status.update(f"Scanning... {total:,} emails found")
# Spinner line cleared on context manager exit

# Final output (after with block):
console.print(f"[bold]Found {total:,} emails[/bold] before {cutoff_str}.")
console.print("Run with --execute to delete permanently.")
```

### Formatting Cutoff for Display

```python
# cutoff is a tz-aware local datetime
# Format: "2024-01-01 23:59:59 PST"
cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S %Z")
# %Z gives abbreviated timezone name (PST, EST, UTC, etc.)
```

### Testing the Updated `parse_date_to_cutoff`

```python
# Replacement test assertions for Phase 3 behavior
def test_returns_local_end_of_day():
    result = parse_date_to_cutoff("2024-01-01")
    assert result.tzinfo is not None          # tz-aware
    assert result.hour == 23
    assert result.minute == 59
    assert result.second == 59
    # Not UTC necessarily — local tz
    # Epoch value should be deterministic for a given machine

def test_epoch_is_integer():
    result = parse_date_to_cutoff("2024-01-01")
    epoch = int(result.timestamp())
    assert isinstance(epoch, int)
    assert epoch > 0
```

### Testing Gmail Pagination with Mock

```python
# Source: Python unittest.mock pattern for paginated API
from unittest.mock import MagicMock

def make_mock_service(pages):
    """pages: list of (messages_list, has_next_token)"""
    mock_service = MagicMock()
    list_method = mock_service.users.return_value.messages.return_value.list
    execute_method = list_method.return_value.execute

    responses = []
    for i, (msgs, has_next) in enumerate(pages):
        resp = {"messages": [{"id": m} for m in msgs]}
        if has_next:
            resp["nextPageToken"] = f"token_{i+1}"
        responses.append(resp)

    execute_method.side_effect = responses
    return mock_service

def test_pagination_fetches_all_pages():
    service = make_mock_service([
        (["id1", "id2"], True),   # page 1: 2 messages, has next
        (["id3"], False),          # page 2: 1 message, done
    ])
    result = list_message_ids(service, query="before:12345")
    assert len(result) == 3
```

---

## State of the Art

| Old Approach (Phase 2) | Phase 3 Approach | Impact |
|------------------------|------------------|--------|
| `before:YYYY/MM/DD` in Gmail query | `before:EPOCH` (Unix timestamp integer) | Timezone-precise; `before:2024/01/01` is ambiguous (Gmail interprets as midnight of which timezone?) |
| `count_messages()` single call, `maxResults=500` | `list_message_ids()` paginated loop | Exact count for any mailbox size |
| UTC midnight for `--before` date | End-of-day local time (23:59:59 local) | Matches user expectation: "before Jan 1" means through all of Dec 31 |
| UTC "now" for `--older-than` | Local "now" | Consistent with --before semantics |
| `typer.echo` with `~` prefix and approximate qualifier | `console.print` with bold, no qualifier | Communicates precision; Rich markup |

**Deprecated/outdated in Phase 3:**
- `count_messages()` function: replaced entirely by paginated approach; can be deleted
- `before:YYYY/MM/DD` format in `build_gmail_query()`: replaced by `before:EPOCH`
- `parse_date_to_cutoff()` returning UTC midnight: now returns local end-of-day

---

## Open Questions

1. **Does `before:EPOCH` Gmail query behave identically to `before:YYYY/MM/DD` in terms of inclusivity?**
   - What we know: Gmail API reference confirms `before:EPOCH` is a valid query format (integer Unix timestamp)
   - What's unclear: Whether Gmail treats `before:EPOCH` as strictly less-than or less-than-or-equal to the timestamp
   - Recommendation: Use `23:59:59` end-of-day as the cutoff (Decision C) which provides a safe 1-second buffer. The practical difference is negligible for the use case (targeting emails days/months old).

2. **`%Z` strftime format on Windows vs. macOS/Linux**
   - What we know: `%Z` returns the abbreviated timezone name from the OS; on macOS/Linux this gives "PST", "EST", "UTC" etc.
   - What's unclear: On Windows, `%Z` may return longer strings or behave differently
   - Recommendation: The tool targets macOS/Linux (per project context). If cross-platform support becomes a requirement, use `cutoff.strftime("%z")` which returns `+HHMM` numeric offset, universally reliable.

3. **Rich `console.status()` interaction with `typer.echo` on the same console**
   - What we know: Rich docs state status "won't interfere with regular console output" when using `console.print()` within the status context
   - What's unclear: Whether `typer.echo` (which calls `click.echo` / `print`) mixed inside a Rich `status` context causes display artifacts
   - Recommendation: Within the pagination loop, use `console.print()` for any debug/error output rather than `typer.echo`. Final output after the `with` block can use either.

---

## Sources

### Primary (HIGH confidence)
- https://rich.readthedocs.io/en/stable/reference/status.html — Status class constructor, `update()` method parameters
- https://rich.readthedocs.io/en/latest/live.html — Live class constructor, `update()` method
- https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html — `list()` method signature, `list_next()` helper, `pageToken` parameter, response format
- https://developers.google.com/gmail/api/reference/rest/v1/users.messages/list — REST API reference: `maxResults` default 100 / max 500, `nextPageToken` semantics, `resultSizeEstimate` described as estimate
- https://docs.python.org/3/library/datetime.html — `astimezone()` uses OS local timezone when called without args; `timestamp()` on tz-aware datetime computes `(dt - epoch_utc).total_seconds()`

### Secondary (MEDIUM confidence)
- https://developers.google.com/workspace/gmail/api/guides/list-messages — Official Gmail API list guide confirming pagination pattern; `resultSizeEstimate` is an estimate

### Tertiary (LOW confidence)
- https://rich.readthedocs.io/en/stable/console.html — `console.status()` basic usage (context manager, spinner param); confirmed `status.update()` exists but full update-in-loop example not shown in fetched content

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, versions confirmed in pyproject.toml
- Gmail API pagination: HIGH — official Python client docs confirm `list()` + `pageToken` + `nextPageToken` loop; `list_next()` helper confirmed
- Rich spinner/status: HIGH — `Status.update()` params confirmed from official reference docs; spinner context manager pattern confirmed
- Python epoch/timezone: HIGH — Python stdlib docs confirm `astimezone()` → OS local tz; `timestamp()` on aware datetime is UTC-correct
- Pitfalls: HIGH — all pitfalls derived from direct reading of existing codebase + API docs

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (stable APIs; Rich, Gmail API, Python stdlib change slowly)
