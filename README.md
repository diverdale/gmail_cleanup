# gmail-clean

Delete old Gmail messages reliably from the command line — with a dry-run preview before committing to deletion.

## Features

- **Dry-run by default** — see exactly what would be deleted before anything happens
- **Two targeting modes** — by age (`--older-than 6`) or by date (`--before 2023-01-01`)
- **Full pagination** — finds every matching email, not just the first 500
- **Timezone-correct date queries** — cutoffs resolve to end-of-day in your local timezone
- **Bulk deletion** — permanently deletes in batches of 500 via `messages.batchDelete`
- **Automatic retry** — exponential backoff on rate limits (429) and server errors (5xx)
- **Live progress** — spinner during scan, progress bar during deletion
- **Elapsed time** — shown on both dry-run and execute paths

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (package manager)
- A Google Cloud project with the Gmail API enabled and OAuth credentials

## Setup

### 1. Get OAuth credentials from Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Gmail API** under *APIs & Services → Library*
4. Create **OAuth 2.0 credentials**: *APIs & Services → Credentials → Create Credentials → OAuth client ID*
   - Application type: **Desktop app**
5. Download the credentials JSON and save it as `credentials.json` in the project root
6. Set the OAuth consent screen to **Production** (not Testing) — Testing tokens expire silently after 7 days

### 2. Install the tool

```bash
git clone <repo-url>
cd gmail_cleanup
uv sync
```

### 3. Authenticate

Run any command — on the first run, a browser window will open for Gmail authorization:

```bash
uv run gmail-clean --older-than 6
```

Grant access, then close the browser tab. The token is cached at `~/.config/gmail-clean/token.json` and reused silently on subsequent runs.

## Usage

### Dry-run (default)

Preview what would be deleted without touching anything:

```bash
# Emails older than 6 months
uv run gmail-clean --older-than 6

# Emails before a specific date
uv run gmail-clean --before 2023-01-01
```

Example output:

```
Found 3,847 emails before 2023-01-01 23:59:59 EST (4.2s, dry run)
Run with --execute to delete permanently.
```

### Live deletion

Add `--execute` to perform the deletion. You'll be prompted to confirm:

```bash
uv run gmail-clean --older-than 12 --execute
```

```
Scanning... 3,847 emails found
Found 3,847 emails before 2025-02-19 14:32:11 EST.
Delete permanently [y/N]: y
Deleting... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 8/8
Deleted 3,847 emails in 12.3s.
```

Press `Ctrl-C` or type `n` at the confirmation prompt to cancel — exits cleanly with code 0.

### Options

| Option | Description |
|--------|-------------|
| `--older-than N` | Target emails older than N months (minimum: 1) |
| `--before YYYY-MM-DD` | Target emails older than a specific date |
| `--execute` | Perform live deletion (dry-run is the default) |
| `--help` | Show help and exit |

Exactly one of `--older-than` or `--before` must be provided.

## How date targeting works

**`--older-than N`**: Computes N calendar months before the current local time. Uses `relativedelta` for correct month arithmetic (e.g., 1 month before March 31 is February 29, not March 3).

**`--before YYYY-MM-DD`**: Resolves to 23:59:59 in your local timezone on that date — so `--before 2023-01-01` captures everything through the end of December 31, 2022 (the full day before Jan 1 is included).

Both flags produce a Unix epoch timestamp for the Gmail query (`before:EPOCH`), which eliminates timezone boundary ambiguity present in date-string formats.

## How deletion works

1. **Scan**: Fetches all matching message IDs via paginated `messages.list` calls (500 per page, no truncation)
2. **Confirm**: Shows the count and prompts for confirmation (with `--execute`)
3. **Delete**: Calls `messages.batchDelete` in batches of 500 IDs per API call
4. **Retry**: On HTTP 429 or 5xx, waits and retries with exponential backoff (1s → 2s → 4s … max 32s); raises immediately on 400/401/403

Deletion is **permanent** — Gmail's `batchDelete` bypasses Trash. The dry-run + confirmation gate is the safety mechanism.

## Project structure

```
gmail_cleanup/
├── auth.py          # OAuth flow, token caching (~/.config/gmail-clean/token.json)
├── main.py          # CLI entry point (typer), dry-run and execute paths
├── gmail_client.py  # Gmail API wrapper (list_message_ids with pagination)
├── cleaner.py       # Deletion logic (batch_delete with retry)
└── date_utils.py    # Date arithmetic and Gmail query building

tests/
├── test_date_utils.py    # 13 tests for date arithmetic and query format
├── test_gmail_client.py  # 7 tests for pagination (mocked API)
└── test_cleaner.py       # 6 tests for batch_delete retry behavior (mocked API)
```

## Running tests

```bash
uv run pytest tests/ -v
```

All 26 tests run offline with mocked Gmail API calls — no real credentials needed for tests.

## Credential security

The following files are covered by `.gitignore` and are **never committed**:

- `credentials.json` — your OAuth client secret (download from Google Cloud)
- `client_id`, `client_secret` — raw credential values
- `~/.config/gmail-clean/token.json` — cached access token (stored outside the repo)

If you need to re-authenticate (e.g., after revoking access or changing scopes), delete `~/.config/gmail-clean/token.json` and run the tool again.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success, or user cancelled (Ctrl-C / `n` at prompt) |
| `1` | Error (missing credentials, API failure, invalid arguments) |
| `2` | Invalid option value (e.g., bad date format for `--before`) |
