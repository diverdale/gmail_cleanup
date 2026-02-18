# Architecture Research

**Domain:** Gmail API Python CLI tool — bulk email deletion by age
**Researched:** 2026-02-18
**Confidence:** HIGH (Gmail API docs are authoritative; patterns verified against official sources and multiple real implementations)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Layer                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  main.py (Click entrypoint)                          │   │
│  │  --before DATE  --dry-run  --max-results N           │   │
│  └──────────────────────┬───────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                 Application Layer                            │
│  ┌───────────────┐      │      ┌──────────────────────────┐ │
│  │  auth.py      │      │      │  cleaner.py              │ │
│  │  (OAuth flow, │◄─────┴─────►│  (orchestrates list →    │ │
│  │   token cache)│             │   batch-delete pipeline)  │ │
│  └───────────────┘             └──────────────┬───────────┘ │
└───────────────────────────────────────────────┼─────────────┘
                                                │
┌───────────────────────────────────────────────┼─────────────┐
│                  Service Layer                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  gmail_client.py                                     │   │
│  │  - list_old_messages(query, page_token)              │   │
│  │  - batch_delete(ids[])                               │   │
│  │  - build_service(credentials)                        │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────┼───────────────────────────────────┐
│                  Storage Layer                               │
│  ┌────────────────┐   ┌──────────────┐   ┌───────────────┐  │
│  │ credentials.json│  │  token.json  │   │ Gmail API     │  │
│  │ (OAuth client) │  │  (cached     │   │ (remote store)│  │
│  │                │  │   tokens)    │   │               │  │
│  └────────────────┘   └──────────────┘   └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|----------------|-------------------|
| `main.py` | Parse CLI args, validate inputs, dispatch to cleaner | cleaner.py |
| `auth.py` | OAuth2 flow, token.json read/write/refresh | credentials.json, token.json, Google OAuth endpoints |
| `cleaner.py` | Orchestrate pagination loop, accumulate IDs, trigger batches, render progress/summary | gmail_client.py, auth.py |
| `gmail_client.py` | Wrap Gmail API calls, handle retries/backoff | Gmail REST API via google-api-python-client |

## Recommended Project Structure

```
gmail_cleanup/
├── gmail_cleanup/          # package source
│   ├── __init__.py
│   ├── main.py             # Click entrypoint, argument definitions
│   ├── auth.py             # OAuth2 credential management
│   ├── cleaner.py          # deletion orchestration, dry-run logic
│   └── gmail_client.py     # Gmail API wrapper (list, batchDelete)
├── credentials.json        # OAuth client secrets (already exists)
├── token.json              # cached tokens (auto-created, gitignored)
├── .gitignore
├── pyproject.toml          # or setup.py
└── README.md
```

### Structure Rationale

- **auth.py separate from gmail_client.py:** Authentication is a distinct concern — it reads/writes files and performs browser flows. The API wrapper should receive a ready `service` object, not manage credentials itself.
- **cleaner.py as orchestrator:** Business logic (dry-run decision, progress display, summary) belongs here, not in the API wrapper or CLI layer. This makes the logic independently testable.
- **gmail_client.py as thin wrapper:** Keeps retry logic and API mechanics in one place. Swapping or mocking the API client affects only this module.

## Architectural Patterns

### Pattern 1: Token.json Caching (Official OAuth Pattern)

**What:** Persist tokens to disk after first authorization so subsequent runs skip the browser flow.

**When to use:** Always — this is Google's recommended pattern for installed apps.

**Trade-offs:** Simple and correct for single-user desktop tools. Not appropriate for multi-user server deployments.

**Example:**
```python
# auth.py
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://mail.google.com/"]  # full access required for batchDelete

def get_service(credentials_path="credentials.json", token_path="token.json"):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())          # silent refresh, no browser
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)   # opens browser once
        with open(token_path, "w") as f:
            f.write(creds.to_json())           # persist for next run
    return build("gmail", "v1", credentials=creds)
```

**Key detail:** Changing SCOPES invalidates cached tokens — delete token.json and re-authenticate.

### Pattern 2: Generator-Based Pagination

**What:** Yield message IDs page by page using `nextPageToken`. Avoids loading all IDs into memory at once.

**When to use:** Any fetch of potentially thousands of messages. Gmail returns 100-500 per page.

**Trade-offs:** Memory-efficient; slightly more complex than collecting a flat list. Correct approach for large mailboxes.

**Example:**
```python
# gmail_client.py
def list_message_ids(service, query: str):
    """Generator yielding message IDs matching query, handling pagination."""
    page_token = None
    while True:
        response = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,          # max allowed per page
            pageToken=page_token
        ).execute()
        for msg in response.get("messages", []):
            yield msg["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            break
```

**Key detail:** `maxResults=500` is the API maximum per page. The query `before:YYYY/MM/DD` is the correct date filter syntax (dates interpreted as midnight PST; use Unix timestamps for timezone precision).

### Pattern 3: Chunked Batch Deletion with Exponential Backoff

**What:** Accumulate IDs from the generator into chunks of ≤1000, call `batchDelete` per chunk, retry on 429/5xx with exponential backoff.

**When to use:** Always for deletion — individual `delete` calls would exhaust quota instantly.

**Trade-offs:** batchDelete costs 50 quota units vs. 5 for messages.list. With a 15,000 unit/minute per-user limit, you can safely run ~300 batchDelete calls/minute. In practice: 1000-message chunks every 200ms is safe.

**Example:**
```python
# gmail_client.py
import time
import random
from googleapiclient.errors import HttpError

BATCH_SIZE = 1000   # Gmail batchDelete maximum

def batch_delete(service, ids: list[str], dry_run: bool = False) -> int:
    """Delete messages in chunks. Returns count deleted."""
    deleted = 0
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i : i + BATCH_SIZE]
        if dry_run:
            deleted += len(chunk)
            continue
        _delete_with_backoff(service, chunk)
        deleted += len(chunk)
    return deleted

def _delete_with_backoff(service, ids: list[str], max_retries: int = 5):
    for attempt in range(max_retries):
        try:
            service.users().messages().batchDelete(
                userId="me",
                body={"ids": ids}
            ).execute()
            return
        except HttpError as e:
            if e.resp.status in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = (2 ** attempt) + random.random()
                time.sleep(wait)
            else:
                raise
```

**Key detail:** 429 and 5xx are retryable. 400, 401, 403 are not — raise immediately.

### Pattern 4: Dry-Run Mode as First-Class Flag

**What:** The `--dry-run` flag passes through the entire pipeline but skips the actual `batchDelete` call. Progress and summary display identically to a real run.

**When to use:** Always implement before deletion logic is complete — it's the safety net during development and for users.

**Trade-offs:** Requires the flag to be threaded from CLI → cleaner → gmail_client. Worth the small coupling.

**Example:**
```python
# cleaner.py
def run_cleanup(service, before_date: str, dry_run: bool):
    query = f"before:{before_date}"
    ids = list(list_message_ids(service, query))   # collect all IDs first
    print(f"Found {len(ids)} messages older than {before_date}")
    if dry_run:
        print("[DRY RUN] No messages will be deleted.")
    deleted = batch_delete(service, ids, dry_run=dry_run)
    print(f"{'Would delete' if dry_run else 'Deleted'}: {deleted} messages")
```

## Data Flow

### Full Execution Flow

```
User invokes: gmail-clean --before 2024/01/01 --dry-run

main.py
  │  parse --before, --dry-run flags
  │  validate date format
  ↓
auth.py.get_service()
  │  check token.json exists?
  │    YES → load Credentials, check valid
  │      expired? → creds.refresh(Request())   [silent, no browser]
  │      invalid? → InstalledAppFlow (browser)
  │    NO  → InstalledAppFlow (browser, first run only)
  │  write updated token.json
  ↓
cleaner.py.run_cleanup(service, before_date, dry_run)
  │
  ├─→ gmail_client.list_message_ids(service, "before:2024/01/01")
  │     │  GET /gmail/v1/users/me/messages?q=before:2024/01/01&maxResults=500
  │     │  yield msg_ids page by page (nextPageToken loop)
  │     ↓  [generator exhausted when no nextPageToken]
  │
  ├─→ collect all IDs into list
  │   print "Found N messages"
  │
  └─→ gmail_client.batch_delete(service, ids, dry_run)
        │  chunk ids into groups of 1000
        │  for each chunk:
        │    dry_run? → skip API call, count += len(chunk)
        │    else    → POST /gmail/v1/users/me/messages/batchDelete
        │              retry on 429/5xx with exponential backoff
        ↓
cleaner.py prints summary:
  "Deleted: N messages" (or "Would delete: N messages")
```

### Token Refresh Flow (Subsequent Runs)

```
Run 2+:
  token.json exists → Credentials.from_authorized_user_file()
  creds.valid?
    YES → use directly, no network call for auth
    NO  → creds.refresh(Request())  [one HTTPS call to Google]
          rewrite token.json with new access token
  proceed to API calls
```

## Scaling Considerations

This is a single-user CLI tool. Scaling is not applicable in the traditional sense. What matters instead is handling large mailboxes:

| Mailbox Size | Concern | Approach |
|---|---|---|
| < 1,000 emails | None | Any approach works |
| 1,000–50,000 emails | Memory (collecting all IDs) | Generator pagination keeps list manageable; a 50K ID list is ~5MB — acceptable |
| 50,000–500,000 emails | API rate limits, runtime | chunk-and-delete as you paginate rather than collect-all-then-delete; add progress bar |
| 500,000+ emails | Runtime (hours) | Resumable state file, but out of scope for this project |

### Quota math for large runs

- `messages.list` at 500/page = 5 quota units per page
- `batchDelete` at 1000/batch = 50 quota units per batch
- 15,000 quota units/minute per user limit
- Safe throughput: ~250 batches/minute = ~250,000 deletions/minute
- 100,000 emails = ~4 minutes at max safe rate (no throttling needed in practice)

## Anti-Patterns

### Anti-Pattern 1: Using `messages.delete` in a Loop

**What people do:** Fetch message IDs then call `service.users().messages().delete()` one at a time in a for loop.

**Why it's wrong:** Each individual delete costs the same quota as a batchDelete of 1000. Deleting 10,000 messages individually is 1000x more expensive than batching. Will exhaust quota within minutes on any meaningful mailbox.

**Do this instead:** Accumulate IDs and call `batchDelete` with up to 1000 IDs per request.

### Anti-Pattern 2: Fetching Full Message Bodies to Filter by Date

**What people do:** Call `messages.get()` on each message to read headers and extract the Date header, then filter client-side.

**Why it's wrong:** `messages.get()` costs 5 quota units per call. For 10,000 messages that is 50,000 units — exhausts the per-minute limit on the first batch. The Gmail API `q` parameter supports `before:YYYY/MM/DD` server-side filtering, which pushes date filtering to Google's servers at zero additional cost.

**Do this instead:** Pass `q=f"before:{date}"` to `messages.list()`. Let the API filter.

### Anti-Pattern 3: Hardcoding token.json Path

**What people do:** `Credentials.from_authorized_user_file("token.json", SCOPES)` with a bare filename, relying on CWD.

**Why it's wrong:** Running the tool from a different directory silently creates a second token.json or fails to find the existing one, triggering a new OAuth browser flow unexpectedly.

**Do this instead:** Resolve the token path relative to the script file or an explicit config directory (`~/.config/gmail-clean/token.json`).

### Anti-Pattern 4: No Retry on 429

**What people do:** Single try/except that raises immediately on any HttpError.

**Why it's wrong:** Gmail API returns 429 under normal operation for large deletion runs. Without retry, the tool fails partway through and leaves partial cleanup with no resumption.

**Do this instead:** Implement exponential backoff for 429 and 5xx errors: `wait = (2^attempt) + random.random()` seconds, up to 5 retries.

### Anti-Pattern 5: Skipping Deletion in Dry-Run but Not Progress

**What people do:** Add `if not dry_run: batch_delete(...)` but show no output in dry-run mode, leaving users uncertain what would have been deleted.

**Why it's wrong:** Dry-run is only useful if it shows what *would* happen. Silent dry-run is indistinguishable from a bug.

**Do this instead:** In dry-run, print "Found N messages — dry run, no deletions performed" with the same count logic as a real run.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google OAuth2 | `InstalledAppFlow.run_local_server(port=0)` opens browser; binds a local HTTP server to capture the redirect | First run only; requires user to grant access in browser |
| Gmail REST API | `googleapiclient.discovery.build("gmail", "v1", credentials=creds)` | All calls go through the built service object; credentials auto-refresh via `google-auth` library |
| Google Token Endpoint | Called implicitly by `creds.refresh(Request())` | Happens transparently when access token expires (~1 hour TTL) |

### Internal Boundaries

| Boundary | Communication Pattern | Notes |
|---|---|---|
| main.py → auth.py | Direct function call: `get_service(credentials_path, token_path)` returns service object | auth.py owns all file I/O for credentials |
| main.py → cleaner.py | Direct function call: `run_cleanup(service, before_date, dry_run)` | Service object passed as dependency |
| cleaner.py → gmail_client.py | Generator consumption + function calls | cleaner consumes the ID generator; calls batch_delete |
| gmail_client.py → Gmail API | HTTP via google-api-python-client | All retries handled inside gmail_client; caller sees clean results or raises |

## Build Order (Phase Dependencies)

The components have a strict dependency chain. Build in this order:

1. **auth.py** — No other component works without a valid service object. Implement OAuth flow and token caching first. Verifiable in isolation: run it and check token.json is created.

2. **gmail_client.py** — Depends on auth.py providing a service object. Build `list_message_ids` (pagination) first; verify it yields correct IDs for a known query. Then add `batch_delete` with dry-run pass-through and backoff.

3. **cleaner.py** — Depends on both above. Wires the generator into the batch accumulator. Add dry-run flag, progress display, and summary here.

4. **main.py** — Depends on all above. Add Click decorators, date input parsing/validation, `--dry-run` flag. This is the thin shell around cleaner.py.

## Sources

- [Gmail API Python Quickstart — official OAuth pattern](https://developers.google.com/workspace/gmail/api/quickstart/python) — HIGH confidence
- [Gmail API: messages.batchDelete reference](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/batchDelete) — HIGH confidence (max 1000 IDs/request confirmed by multiple implementations)
- [Gmail API: Usage Limits & Quota Units](https://developers.google.com/workspace/gmail/api/reference/quota) — HIGH confidence (messages.list = 5 units, batchDelete = 50 units, 15,000 units/user/minute)
- [Gmail API: Filtering/Search query syntax](https://developers.google.com/workspace/gmail/api/guides/filtering) — HIGH confidence (before:YYYY/MM/DD, epoch timestamps supported)
- [Gmail API: Listing messages with pagination](https://developers.google.com/workspace/gmail/api/guides/list-messages) — HIGH confidence (maxResults max=500, nextPageToken pattern)
- [Gmail API: Error handling and retry guidance](https://developers.google.com/workspace/gmail/api/guides/handle-errors) — HIGH confidence (429/5xx retryable, 400/401/403 not)
- [scipython.com: Deleting Gmail messages by label](https://scipython.com/blog/deleting-gmail-messages-by-label-with-the-google-api/) — MEDIUM confidence (real implementation confirming generator + batch pattern)
- [qualman/gmail_delete_by_filter on GitHub](https://github.com/qualman/gmail_delete_by_filter) — MEDIUM confidence (confirms 1000 as batchDelete practical limit)

---
*Architecture research for: Gmail API Python CLI bulk email deletion tool*
*Researched: 2026-02-18*
