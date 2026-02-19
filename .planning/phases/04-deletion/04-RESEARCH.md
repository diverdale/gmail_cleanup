# Phase 4: Deletion - Research

**Researched:** 2026-02-19
**Domain:** Gmail API bulk deletion, exponential backoff retry, Rich progress bars
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DEL-01 | Emails are deleted permanently in batches of 500 IDs per API call via messages.batchDelete | `service.users().messages().batchDelete(userId='me', body={'ids': chunk}).execute()` — chunking at 500 IDs stays safely under the 1000-ID limit documented for batchModify (same API family) |
| DEL-02 | Tool retries on HTTP 429 and 5xx responses with exponential backoff; raises immediately on 400/401/403 | Official error handling docs confirm: retry 429 + 5xx with exponential backoff; 400/401/403 are non-retriable. Implement via manual sleep loop inspecting `HttpError.resp.status` — no new dependency needed since `tenacity` is not in pyproject.toml |
| DEL-03 | Progress is shown during deletion (current / total emails processed) | `rich.progress.track()` or `Progress()` with `MofNCompleteColumn` — Rich 14.1.0 already in pyproject.toml |
| DEL-04 | After completion, tool prints a summary: count deleted (or would-delete in dry-run) and elapsed time | `time.monotonic()` before/after deletion loop; format seconds as `{elapsed:.1f}s`; print via `console.print()` using existing Console instance |
</phase_requirements>

---

## Summary

Phase 4 implements the deletion loop that replaces the stub in `main.py` ("Deletion not yet implemented. (Phase 4)"). The logic lives in `cleaner.py` as `batch_delete(service, message_ids)`, which is already stubbed with `raise NotImplementedError`. The main.py must call this function after confirmation, wrapping it with a progress display and elapsed-time summary.

The Gmail `messages.batchDelete` API accepts a JSON body `{"ids": [...]}` and returns an empty 200 response on success. No guarantee is given that messages existed — non-existent IDs are silently ignored. The batchModify endpoint (same family) explicitly documents a 1000-ID limit; this project uses 500 per requirement DEL-01, which is safely within that limit and matches the 500 used in the list phase.

Retry logic must be implemented as a manual `while True` loop with `time.sleep(delay)` inside `cleaner.py`. The project does NOT include `tenacity` in pyproject.toml, so a custom retry helper keeps the dependency count stable. Exponential backoff starts at 1 second and doubles (cap at 32 seconds), retrying on 429 and 5xx only. `HttpError` is already re-exported from `gmail_client.py` for callers, so `cleaner.py` can import it from there.

**Primary recommendation:** Implement `batch_delete()` in `cleaner.py` with chunked batchDelete calls, inline exponential backoff retry, and `rich.progress.track()` for per-batch progress. In `main.py`, start a monotonic timer before calling `batch_delete`, then print the summary count + elapsed time using the existing `console` object.

---

## Standard Stack

### Core (already installed — pyproject.toml is authoritative)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | 2.190.0 | `service.users().messages().batchDelete()` | The only official Google API Python client |
| googleapiclient.errors.HttpError | (part of above) | Inspect HTTP status on API errors | Already re-exported in gmail_client.py; all error handling uses it |
| rich | 14.1.0 | Progress display during deletion loop | Already in project; used in main.py for `console.status()` spinner |
| typer | 0.24.0 | CLI scaffolding | Already in project; all output/exit patterns follow typer conventions |

### Supporting (stdlib only — no new dependencies)
| Module | Purpose | When to Use |
|--------|---------|-------------|
| `time` (stdlib) | `time.monotonic()` for elapsed timing, `time.sleep()` for retry delays | Start timer before deletion, end after, format delta as seconds |
| `math` (stdlib) | `min(delay * 2, MAX_DELAY)` for backoff cap | Optional — can inline arithmetic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual retry loop | `tenacity` library | tenacity is cleaner but would add a new dependency not in pyproject.toml; manual loop is ~15 lines and sufficient |
| `rich.progress.track()` | `tqdm` | tqdm not in project; rich already installed and used |
| `time.monotonic()` | `time.perf_counter()` | Both work; monotonic is the standard for elapsed wall-clock durations |

**Installation:** No new packages required. All dependencies are already in pyproject.toml.

---

## Architecture Patterns

### Recommended File Structure (Phase 4 changes)
```
gmail_cleanup/
├── cleaner.py        # batch_delete() implementation goes here (currently stubbed)
├── gmail_client.py   # HttpError re-export stays; no changes needed
└── main.py           # Replace stub "Deletion not yet implemented" with batch_delete() call + summary
tests/
└── test_cleaner.py   # New test file for batch_delete unit tests
```

### Pattern 1: Chunked batchDelete in cleaner.py
**What:** Split the full message ID list into 500-ID chunks; call batchDelete once per chunk with retry; advance progress bar per chunk.
**When to use:** Always — batchDelete requires a finite list, and 500 matches the list page size already established in Phases 2-3.

```python
# Source: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete
# Source: https://rich.readthedocs.io/en/latest/progress.html
import time
from rich.progress import track
from gmail_cleanup.gmail_client import HttpError

BATCH_SIZE = 500
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_DELAY = 32  # seconds


def _delete_chunk_with_retry(service, chunk: list[str]) -> None:
    """Call batchDelete for one chunk; retry on 429/5xx with exponential backoff."""
    delay = 1
    while True:
        try:
            service.users().messages().batchDelete(
                userId="me",
                body={"ids": chunk},
            ).execute()
            return
        except HttpError as exc:
            status = int(exc.resp.status)
            if status not in _RETRY_STATUSES:
                raise  # 400/401/403 — not retriable, propagate immediately
            time.sleep(delay)
            delay = min(delay * 2, _MAX_DELAY)


def batch_delete(service, message_ids: list[str]) -> int:
    """Permanently delete all message_ids in batches of 500 with retry.

    Returns the count of deleted messages (len(message_ids)).
    Raises HttpError immediately on 400/401/403.
    Retries with exponential backoff on 429/5xx.
    """
    chunks = [
        message_ids[i : i + BATCH_SIZE]
        for i in range(0, len(message_ids), BATCH_SIZE)
    ]
    for chunk in track(chunks, description="Deleting..."):
        _delete_chunk_with_retry(service, chunk)
    return len(message_ids)
```

### Pattern 2: Elapsed time + summary in main.py
**What:** Capture `time.monotonic()` before the deletion call; compute delta after; print with count.
**When to use:** After confirmed deletion (`--execute` path).

```python
# Source: Python stdlib time.monotonic() — standard pattern for CLI elapsed display
import time

start = time.monotonic()
deleted = batch_delete(service, message_ids)
elapsed = time.monotonic() - start
console.print(
    f"[bold green]Deleted {deleted:,} emails[/bold green] in {elapsed:.1f}s."
)
```

### Pattern 3: Dry-run summary in main.py
**What:** DEL-04 requires the dry-run path also prints a count summary. The dry-run path already prints count — update it to match the summary format with elapsed time.
**When to use:** When `--execute` is NOT passed.

```python
# Current dry-run output (Phase 3):
console.print(f"[bold]Found {count:,} emails[/bold] before {cutoff_display}.")
typer.echo("Run with --execute to delete permanently.")

# Phase 4 dry-run adds elapsed (scan time):
console.print(
    f"[bold]Would delete {count:,} emails[/bold] before {cutoff_display}. "
    f"(Scanned in {elapsed:.1f}s.)"
)
```

### Pattern 4: rich.progress with MofNCompleteColumn (alternative to track())
**What:** Use `Progress()` context manager with explicit columns when you need "X/Y" format instead of percentage.
**When to use:** If the requirement's "current / total" language mandates showing the ratio explicitly rather than a percentage bar.

```python
# Source: https://rich.readthedocs.io/en/latest/progress.html
from rich.progress import Progress, MofNCompleteColumn, BarColumn, TextColumn, TimeElapsedColumn

with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Deleting...", total=len(chunks))
    for chunk in chunks:
        _delete_chunk_with_retry(service, chunk)
        progress.advance(task)
```

`track()` is simpler and sufficient; use `Progress()` only if the planner decides "current / total" display is required.

### Anti-Patterns to Avoid
- **Passing all IDs in one call:** The batchDelete body has no chunking built in. The API will accept the call, but at 1000+ IDs the documented limit for the batchModify sibling is hit. Chunk at 500 per DEL-01.
- **Retrying on 400/401/403:** These indicate a bug or auth failure. Retrying wastes time and can exhaust retry budgets. Raise immediately.
- **Using `time.time()` for elapsed:** System clock can jump backward (NTP sync). Use `time.monotonic()` for durations.
- **Catching bare `Exception` in retry loop:** Only `HttpError` needs status inspection. Other exceptions (network, auth) should propagate normally.
- **Sleeping before the first attempt:** Sleep only AFTER a failure, not before the first try.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress display | Custom `\r` print loop | `rich.progress.track()` | Rich handles terminal width, newlines, CI detection, and cleanup on exception |
| Exponential backoff calculation | Complex state machine | `delay = min(delay * 2, MAX_DELAY)` inline | The Gmail error handling guide gives this exact pattern; 15 lines total |
| HTTP status extraction from HttpError | Parsing exception strings | `int(exc.resp.status)` | `resp.status` is a documented attribute on the HttpResponse object |

**Key insight:** The retry loop is genuinely simple here (one integer, one multiply, one min). Using tenacity would add a dependency for code that fits in 10 lines.

---

## Common Pitfalls

### Pitfall 1: Forgetting that batchDelete returns None (empty body)
**What goes wrong:** Code checks the return value of `.execute()` for success indicators, gets `None`, and incorrectly treats it as a failure or skips counting.
**Why it happens:** Other Gmail API calls return dicts; batchDelete's 200 response has an empty body.
**How to avoid:** Do not inspect the return of `.execute()` for batchDelete. Count is derived from `len(message_ids)`, not from the API response.
**Warning signs:** `NoneType` errors when accessing return value attributes.

### Pitfall 2: HttpError status is a string, not an int
**What goes wrong:** `exc.resp.status` returns a string like `"429"`, not an integer. Code like `if exc.resp.status == 429:` silently never matches.
**Why it happens:** `httplib2` (underlying transport) stores response headers as strings.
**How to avoid:** Always cast: `status = int(exc.resp.status)` before comparison.
**Warning signs:** Retry logic never triggers even on rate-limit errors.

### Pitfall 3: rich.progress.track() prints after the loop ends
**What goes wrong:** When iterating chunks with `track()`, the progress bar stays visible during iteration but may leave a stale line if the loop is interrupted.
**Why it happens:** Rich auto-cleans on normal exit but not on unhandled exception inside the loop.
**How to avoid:** Let `HttpError` propagate out of the loop rather than swallowing it. Rich will clean up on exception exit too. Don't catch exceptions inside the `track()` loop body unless re-raising.
**Warning signs:** Duplicate progress bar lines after an error.

### Pitfall 4: Dry-run count vs. deleted count mismatch (DEL-04 requirement)
**What goes wrong:** Phase 3 list uses `maxResults=500` with pagination; Phase 4 deletes the same list. If Phase 4 re-fetches the list independently, race conditions can cause counts to differ.
**Why it happens:** New emails could match the query between dry-run and execute; or the ID list is re-fetched rather than reused.
**How to avoid:** Phase 4 uses the ID list already collected in Phase 3's scan loop (the `message_ids` list in `main.py`). Do NOT re-fetch inside `batch_delete()`. Pass the list in.
**Warning signs:** DEL-04 acceptance test fails with "count mismatch."

### Pitfall 5: 403 errors — scope vs. rate limit
**What goes wrong:** A 403 `rateLimitExceeded` subtype actually should be retried, but a 403 `insufficientPermissions` should not.
**Why it happens:** Google overloads HTTP 403 for both permission errors AND some rate limit errors depending on the error reason field.
**How to avoid:** The requirement says "raises immediately on 400/401/403." Honor this — the project uses `https://mail.google.com/` scope (confirmed in Phase 1-2), so 403 means a genuine permission problem, not a rate limit. A rate limit on this scope appears as 429, not 403.
**Warning signs:** Infinite retry loop on a 403.

---

## Code Examples

Verified patterns from official sources:

### batchDelete API call
```python
# Source: https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html
service.users().messages().batchDelete(
    userId="me",
    body={"ids": list_of_up_to_500_ids},
).execute()
# Returns: None (empty 200 response)
```

### HttpError status extraction
```python
# Source: googleapiclient.errors.HttpError — resp.status is the HTTP status code (as string)
try:
    service.users().messages().batchDelete(userId="me", body={"ids": chunk}).execute()
except HttpError as exc:
    status = int(exc.resp.status)  # cast to int — stored as string by httplib2
    if status in {429, 500, 502, 503, 504}:
        # retry
    else:
        raise  # 400/401/403 — propagate immediately
```

### Rich progress track() — simplest form
```python
# Source: https://rich.readthedocs.io/en/latest/progress.html
from rich.progress import track

for chunk in track(chunks, description="Deleting..."):
    _delete_chunk_with_retry(service, chunk)
```

### Rich progress with MofNCompleteColumn — explicit current/total
```python
# Source: https://rich.readthedocs.io/en/latest/progress.html
from rich.progress import Progress, MofNCompleteColumn, BarColumn, TextColumn, TimeElapsedColumn

with Progress(
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    MofNCompleteColumn(),  # renders as "3/10"
    TimeElapsedColumn(),
) as progress:
    task = progress.add_task("Deleting...", total=len(chunks))
    for chunk in chunks:
        _delete_chunk_with_retry(service, chunk)
        progress.advance(task)
```

### Monotonic elapsed time
```python
# Source: Python stdlib — time.monotonic() is the correct tool for CLI elapsed display
import time

start = time.monotonic()
# ... do work ...
elapsed = time.monotonic() - start
print(f"Done in {elapsed:.1f}s")
```

### Exponential backoff retry loop
```python
# Source: https://developers.google.com/workspace/gmail/api/guides/handle-errors
# Pattern: start at 1s, double each retry, cap at 32s
_RETRY_STATUSES = {429, 500, 502, 503, 504}
_MAX_DELAY = 32

delay = 1
while True:
    try:
        # API call
        return
    except HttpError as exc:
        if int(exc.resp.status) not in _RETRY_STATUSES:
            raise
        time.sleep(delay)
        delay = min(delay * 2, _MAX_DELAY)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Delete one message at a time via `messages.delete` | Batch 500 IDs per call via `messages.batchDelete` | Gmail API v1 (current) | 500x fewer API calls for large deletions |
| `tqdm` for CLI progress | `rich.progress.track()` | rich became standard ~2022 | Rich already in project; no tqdm needed |
| `time.time()` for elapsed | `time.monotonic()` | Python 3.3+ | Monotonic is immune to system clock adjustments |

**Deprecated/outdated:**
- Single-message `messages.delete` in a loop: Too slow, too many quota units consumed. batchDelete is the right tool.
- `googleapiclient.http.BatchHttpRequest` (the HTTP-level batch wrapper): This is the HTTP batching API, not the same as `messages.batchDelete`. Do not confuse them. batchDelete is a single endpoint that accepts many IDs; BatchHttpRequest bundles multiple HTTP requests. Use batchDelete only.

---

## Open Questions

1. **Exact batchDelete ID limit**
   - What we know: `batchModify` explicitly documents 1000 IDs per request. `batchDelete` documentation does not specify a limit on its own page.
   - What's unclear: Whether batchDelete enforces the same 1000-ID limit or a different one.
   - Recommendation: Use 500 per DEL-01 (the requirement is explicit). This is safe regardless of the actual limit and matches the list page size from Phase 3.

2. **Whether to add a jitter component to backoff**
   - What we know: Google's error handling guide recommends exponential backoff starting at 1 second. It does not mention jitter in the docs fetched.
   - What's unclear: Whether thundering-herd is a concern for a single-user CLI tool.
   - Recommendation: Skip jitter. This is a single-user tool, not a distributed system. Plain `delay * 2` is sufficient.

3. **dry-run elapsed time in DEL-04**
   - What we know: DEL-04 says "count deleted (or would-delete in dry-run) and elapsed time." The dry-run path currently prints count but not elapsed time.
   - What's unclear: Whether "elapsed time" in dry-run means scan time (Phase 3 listing) or is omitted for dry-run.
   - Recommendation: Start `time.monotonic()` before the scan loop, end after dry-run output. Print elapsed scan time in both dry-run and execute paths for consistent UX.

---

## Sources

### Primary (HIGH confidence)
- `https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete` — endpoint, request body format, response (empty), auth scope, "no guarantee messages exist" behavior
- `https://googleapis.github.io/google-api-python-client/docs/dyn/gmail_v1.users.messages.html` — Python client batchDelete signature: `batchDelete(userId, body=None)`; batchModify 1000-ID limit
- `https://developers.google.com/workspace/gmail/api/guides/handle-errors` — retry on 429 and 5xx; no retry on 400/401/403; exponential backoff starting at 1s
- `https://developers.google.com/workspace/gmail/api/reference/quota` — batchDelete costs 50 quota units; per-user limit 15,000 units/min; per-project 1,200,000 units/min
- `https://rich.readthedocs.io/en/latest/progress.html` — `track()`, `Progress()`, `MofNCompleteColumn`, `TimeElapsedColumn` API
- `/Users/dalwrigh/dev/gmail_cleanup/pyproject.toml` — authoritative version pins: rich==14.1.0, typer==0.24.0, google-api-python-client==2.190.0

### Secondary (MEDIUM confidence)
- `https://tenacity.readthedocs.io/` — tenacity retry patterns; NOT used in this project (not in pyproject.toml), documented here for reference only
- WebSearch + cross-verification with official docs: 500/1000 ID limit for batchDelete; community consensus uses 1000 max but 500 is documented in requirement DEL-01

### Tertiary (LOW confidence)
- Community examples on GitHub (qualman/gmail_delete_by_filter): Use 1000 as batch size. Unverified by official docs for batchDelete specifically; trust the DEL-01 requirement of 500 instead.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries pinned in pyproject.toml; no new dependencies needed
- Architecture: HIGH — batchDelete API signature verified from official Python client docs; retry pattern verified from official error handling guide
- Pitfalls: HIGH — HttpError.resp.status string behavior verified against httplib2 behavior; batchDelete empty-response behavior from official docs
- Dry-run elapsed time: MEDIUM — interpretation of DEL-04 "elapsed time" for dry-run path is inferred from requirement wording, not explicitly specified

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (stable Gmail API — 30-day window)
