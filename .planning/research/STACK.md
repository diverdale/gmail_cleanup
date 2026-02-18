# Stack Research

**Domain:** Gmail management CLI tool (Python)
**Researched:** 2026-02-18
**Confidence:** HIGH — all versions verified against PyPI as of February 2026; OAuth scope requirements verified against official Gmail API reference docs

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | >=3.10 | Runtime | Required by Typer 0.24.0; 3.10+ is now the de-facto floor for new Python tooling. Use 3.12 for best performance. |
| google-api-python-client | 2.190.0 | Gmail API client | Google's official Python client. Provides `googleapiclient.discovery.build()` which generates a typed service object for the entire Gmail REST API. The only fully supported path for the Gmail API. |
| google-auth | 2.48.0 | Credential management and token refresh | Handles credential objects, automatic token refresh via `creds.refresh(Request())`. The successor to the deprecated `oauth2client`. |
| google-auth-oauthlib | 1.2.4 | OAuth 2.0 flow for installed apps | Provides `InstalledAppFlow.from_client_secrets_file()` which reads the existing `credentials.json` ("installed" app type) and drives the browser-based consent flow on first run. Saves resulting tokens to `token.json`. |
| Typer | 0.24.0 | CLI framework | Built on Click by FastAPI's creator. Type hint-driven: function signatures become CLI argument/option definitions automatically. Less boilerplate than Click, modern Python. Requires Python >=3.10. |
| Rich | 14.1.0 | Terminal output, progress bars | Integrates natively with Typer. Provides `rich.progress.track()` for indeterminate iteration progress and `rich.console.Console` for styled summary output. Required for the progress display and summary count requirements. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dateutil | 2.9.x | Human-friendly date arithmetic | Use for computing the cutoff date from "X months ago". `relativedelta(months=-X)` handles month-boundary edge cases correctly (e.g., March minus 1 month = February 28, not February 30). `datetime` stdlib alone cannot do this correctly. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Package manager and virtualenv | Replaces pip + venv. 10-100x faster than pip. Use `uv init`, `uv add`, `uv run`. Produces `uv.lock` for reproducible installs. Widely adopted in 2025. |
| pytest | Test runner | Standard for Python unit tests. Use for testing dry-run logic, date calculation, and batch chunking without hitting the real API. |

---

## Installation

```bash
# Using uv (recommended)
uv init gmail-cleanup
uv add google-api-python-client google-auth google-auth-oauthlib typer rich python-dateutil

# Or using pip with venv
python3 -m venv .venv
source .venv/bin/activate
pip install google-api-python-client==2.190.0 google-auth==2.48.0 google-auth-oauthlib==1.2.4 typer==0.24.0 rich==14.1.0 python-dateutil
```

---

## Credential Handling: How the Existing credentials.json Works

The existing `credentials.json` is in Google's "installed application" format (confirmed: `{"installed": {...}}`). This is the standard format for desktop/CLI apps.

**Standard pattern:**

```python
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
TOKEN_PATH = "token.json"
CREDENTIALS_PATH = "credentials.json"

def get_credentials() -> Credentials:
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds
```

First run opens browser for user consent, creates `token.json`. Subsequent runs use `token.json` and auto-refresh. **Never delete `token.json` between runs.**

---

## Batch Deletion: The Critical Decision

### The Scope Requirement

This is the most important implementation decision. Two deletion strategies exist, requiring different OAuth scopes:

| Strategy | Method | OAuth Scope Required | Recoverable? | Quota Cost |
|----------|--------|---------------------|--------------|------------|
| Move to Trash | `messages.batchModify` with `TRASH` label OR individual `messages.trash` | `gmail.modify` | Yes (30 days) | 5 units/msg |
| Permanent Delete | `messages.batchDelete` | `https://mail.google.com/` (full access) | No | 50 units/batch |

**Recommendation: Use `messages.trash` + `gmail.modify` scope as the default, with `--permanent` flag for hard delete.**

Rationale:
1. `gmail.modify` scope is less sensitive than `mail.google.com/` — Google's own docs say permanent delete bypasses trash and is what the wider scope is needed for
2. `batchDelete` requires `https://mail.google.com/` (confirmed via official API reference AND a real-world GitHub issue where `gmail.modify` returned 403)
3. Google explicitly recommends `messages.trash` over `messages.delete` in the API docs
4. For a personal cleanup tool, trash is safer — protects against date miscalculations

**If the user wants permanent delete:** Add a `--permanent` / `--no-trash` flag, change scope to `https://mail.google.com/`, delete `token.json` so they get a new consent flow for the broader scope.

### Batch Size

`batchDelete` has no documented per-call ID limit. Community implementations use up to 1000 IDs per call safely. Use chunks of **500** to stay well within limits while remaining efficient.

### Quota Math

- `messages.list` (paginated, 500/page): 5 units per page
- `messages.batchDelete`: 50 units per call regardless of how many IDs
- `messages.trash`: 5 units per message (expensive for large mailboxes — use batchModify instead)
- Per-user rate limit: **15,000 quota units per minute**

At 500 IDs per batchDelete call: 50 quota units. Can delete ~1,500 batches/minute before hitting rate limits = 750,000 messages/minute theoretical max. In practice, add a small sleep between batches (0.1s) to avoid `userRateLimitExceeded`.

### Searching for Old Messages

Use `messages.list` with the `q` parameter (same syntax as Gmail search bar):

```python
# Messages older than X months
query = f"before:{cutoff_date.strftime('%Y/%m/%d')}"

# Or use Gmail's older_than operator (less precise, rounded to days)
query = "older_than:6m"

# Paginate through all results
results = service.users().messages().list(
    userId="me",
    q=query,
    maxResults=500  # max is 500 per page
).execute()
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Typer | Click | When you need Python 3.7/3.8 support, or the team is already deeply familiar with Click's decorator style |
| Typer | argparse | Never for new projects — argparse is stdlib but produces more code for less functionality |
| google-api-python-client | simplegmail | Never — simplegmail is a thin wrapper with sparse maintenance, unmaintained since 2022 for complex operations |
| google-auth-oauthlib | oauth2client | Never — oauth2client is officially deprecated and abandoned; google-auth is the replacement |
| Rich | tqdm | Rich is strictly better for this use case: handles table output for summary, styled console messages, and progress. tqdm is progress-only. |
| python-dateutil | arrow | Either works; dateutil is lighter and already in many dependency trees |
| uv | pip + venv | If the target deployment environment doesn't support uv (rare); standard pip is always the fallback |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `oauth2client` | Officially deprecated since 2019; Google no longer maintains it; will break on Python 3.12+ | `google-auth` + `google-auth-oauthlib` |
| `google-auth-httplib2` | No longer maintained as of late 2025; httplib2 is not thread-safe and has insecure TLS handling; the library itself says "no longer maintained" on PyPI | Use the default transport in `google-api-python-client` (uses httpx/requests internally) |
| `simplegmail` | Third-party wrapper, not maintained for complex operations, limited to basic send/read. No batch delete support | `google-api-python-client` directly |
| `gmail.modify` scope for batchDelete | Returns 403 in practice despite what some docs imply. Confirmed in real-world usage (googleapis/google-api-python-client issue #2710) | Use `https://mail.google.com/` scope when permanent delete is needed |
| `messages.delete` (single) in a loop | 10 quota units per call, slow, not atomic. 1000 messages = 10,000 quota units + 1000 HTTP round trips | `messages.batchDelete` (50 units per batch call, regardless of ID count) |

---

## Stack Patterns by Variant

**Default mode (safe, recommended):**
- Scope: `https://www.googleapis.com/auth/gmail.modify`
- Deletion: `messages.trash` via batch modify
- Recovery: Emails sit in Trash for 30 days before auto-purge

**Permanent delete mode (`--permanent` flag):**
- Scope: `https://mail.google.com/`
- Deletion: `messages.batchDelete` in chunks of 500
- Recovery: None — warn the user explicitly before execution

**Dry-run mode:**
- Scope: `https://www.googleapis.com/auth/gmail.readonly` (narrowest possible)
- Action: List and count matching messages, print summary, make zero mutations
- Implementation: Skip the delete/trash call, print what WOULD be deleted

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| google-api-python-client 2.190.0 | google-auth >=2.14.1 | google-api-python-client declares this minimum; 2.48.0 is well within range |
| google-auth-oauthlib 1.2.4 | google-auth >=2.15.0 | Compatible with google-auth 2.48.0 |
| Typer 0.24.0 | Python >=3.10 | Breaking change from older Typer — do not use Python 3.8/3.9 |
| Rich 14.1.0 | Python >=3.8 | No conflicts with above stack |

---

## Sources

- [google-api-python-client on PyPI](https://pypi.org/project/google-api-python-client/) — Version 2.190.0 confirmed, released February 12, 2026
- [google-auth on PyPI](https://pypi.org/project/google-auth/) — Version 2.48.0 confirmed, released January 26, 2026
- [google-auth-oauthlib on PyPI](https://pypi.org/project/google-auth-oauthlib/) — Version 1.2.4 confirmed, released January 15, 2026
- [google-auth-httplib2 on PyPI](https://pypi.org/project/google-auth-httplib2/) — Confirmed "no longer maintained" in library's own documentation
- [Typer on PyPI](https://pypi.org/project/typer/) — Version 0.24.0 confirmed, released February 16, 2026, requires Python >=3.10
- [Rich documentation](https://rich.readthedocs.io/en/stable/progress.html) — Version 14.1.0 current
- [Gmail API Python Quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) — Canonical install command and InstalledAppFlow pattern
- [messages.batchDelete reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete) — Scope confirmed as `https://mail.google.com/` only
- [messages.trash reference](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/trash) — Scope confirmed as `gmail.modify` OR `mail.google.com/`
- [Gmail API quota reference](https://developers.google.com/workspace/gmail/api/reference/quota) — Quota units per method, 15,000 units/user/minute limit
- [Gmail API scopes reference](https://developers.google.com/workspace/gmail/api/auth/scopes) — Scope descriptions confirmed
- [google-api-python-client issue #2710](https://github.com/googleapis/google-api-python-client/issues/2710) — Real-world confirmation that batchDelete returns 403 with `gmail.modify`; requires `mail.google.com/`
- [List Messages guide](https://developers.google.com/workspace/gmail/api/guides/list-messages) — maxResults max 500, nextPageToken pagination confirmed
- [uv documentation](https://docs.astral.sh/uv/) — Production-stable, recommended for new Python projects in 2025/2026

---
*Stack research for: Gmail cleanup CLI tool (Python)*
*Researched: 2026-02-18*
