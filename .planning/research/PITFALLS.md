# Pitfalls Research

**Domain:** Gmail API bulk-deletion Python CLI tool
**Researched:** 2026-02-18
**Confidence:** HIGH (official API docs + verified issue tracker + multiple community sources)

---

## Critical Pitfalls

### Pitfall 1: Wrong OAuth Scope for batchDelete (403 Insufficient Permissions)

**What goes wrong:**
The `users.messages.batchDelete` endpoint returns a 403 "Request had insufficient authentication scopes" error even when using `https://www.googleapis.com/auth/gmail.modify`. This contradicts what Google's own documentation implies — `gmail.modify` sounds like it should allow deletion, and it does work for `messages.list` and `messages.modify` (label changes), but batchDelete enforces a stricter undocumented backend permission. The bug is confirmed open as of January 2026 in the googleapis/google-api-python-client issue tracker.

**Why it happens:**
There is a documented gap between what Google's docs say the scope covers and what the backend actually enforces for `batchDelete`. The operation is permanent and irreversible, so Google appears to gate it behind the full-access scope regardless of documentation.

**How to avoid:**
Request `https://mail.google.com/` as the OAuth scope from the start. Do NOT attempt `gmail.modify` and fall back — request `https://mail.google.com/` upfront. Delete any existing `token.json` / `token.pickle` if scope is changing; the cached token will not gain the new scope without a fresh auth flow.

```python
SCOPES = ['https://mail.google.com/']
```

**Warning signs:**
- HTTP 403 with "insufficientPermissions" after a successful `messages.list` call
- Auth flow completes successfully but delete calls fail

**Phase to address:**
Phase 1 (OAuth + Auth setup). Get the scope right before writing any deletion logic.

---

### Pitfall 2: Refresh Token Silently Expires in Testing Mode (7-Day Limit)

**What goes wrong:**
If the Google Cloud project's OAuth consent screen is set to "External" user type with publishing status "Testing", all issued refresh tokens expire after exactly 7 days. This is silent — no error during development, just suddenly broken auth a week later. The token looks valid in `token.json` but returns `invalid_grant` on the next refresh attempt.

**Why it happens:**
Google enforces a 7-day limit on refresh tokens for unverified/testing apps with external users, to prevent long-lived credentials from proliferating during development. This applies specifically when the app is NOT published to "Production" status in Google Cloud Console. The existing `credentials.json` in this project may have been obtained under testing-mode settings.

**How to avoid:**
In Google Cloud Console → APIs & Services → OAuth consent screen: either (a) set user type to "Internal" (Workspace accounts only) or (b) publish to "Production" status. For a personal-use CLI tool, "Internal" is the cleanest option if the account is a Workspace account; otherwise publish to Production. After changing status, revoke the old token and re-run the auth flow to get a long-lived refresh token.

Also: request `access_type=offline` and `prompt=consent` in the auth flow to guarantee a refresh token is returned.

**Warning signs:**
- `invalid_grant` error exactly ~7 days after first auth
- Token works during development but breaks after a week of no use
- Error message: "Token has been expired or revoked"

**Phase to address:**
Phase 1 (OAuth setup). Verify consent screen status before any other work.

---

### Pitfall 3: Permanent Delete Is Irreversible — No Undo Path

**What goes wrong:**
`messages.batchDelete` permanently and immediately destroys messages. They are NOT moved to Trash first. There is no undo. Google's own documentation recommends `messages.trash` over `messages.delete` for exactly this reason, but for a cleanup tool designed to delete old mail this is the intended behavior — unless the developer or user forgets and accidentally passes the wrong date cutoff.

**Why it happens:**
Developers used to "delete = trash" UX (like the Gmail web UI) don't realize that the API's `batchDelete` bypasses Trash entirely. Running without `--dry-run` on a misconfigured date cutoff causes permanent data loss.

**How to avoid:**
- Make `--dry-run` the **default mode**, requiring an explicit `--no-dry-run` or `--confirm` flag to actually delete. This inverts the danger: you must opt into destruction, not opt out.
- Print a summary of what WOULD be deleted (count, date range) in dry-run mode and require confirmation before proceeding in live mode.
- Show a "you are about to permanently delete N emails — this cannot be undone. Proceed? [y/N]:" prompt when not in dry-run.
- Log deleted message IDs to a timestamped file before deletion as a last-resort audit trail.

**Warning signs:**
- No `--dry-run` default in CLI design
- No confirmation prompt before execution
- No count shown before destructive operation begins

**Phase to address:**
Phase 2 (CLI design and dry-run mode). Dry-run must be implemented and validated before any live deletion logic is written.

---

### Pitfall 4: Date Query Timezone Ambiguity Causes Off-by-One Errors

**What goes wrong:**
The Gmail API `q` parameter accepts date strings like `before:2024/01/15`, but Google's documentation states these are interpreted as midnight PST — not UTC, not the user's local timezone. Testing has shown the actual behavior is inconsistent (some sources observed UTC interpretation). Using date strings when the user's local timezone is not PST can cause the tool to delete emails from the wrong day — emails sent "today" in one timezone might be deleted as "yesterday's" mail.

**Why it happens:**
Developers compute a cutoff date in Python using `datetime.now()` (local timezone) and format it as `YYYY/MM/DD` without considering the API's PST interpretation. A user in UTC+5 running the tool at 2am UTC might see different results than expected.

**How to avoid:**
Use Unix epoch timestamps in the query string, not date strings. Convert the cutoff date to a UTC Unix timestamp:

```python
import datetime, calendar
cutoff_date = datetime.datetime(2024, 1, 15, tzinfo=datetime.timezone.utc)
epoch = calendar.timegm(cutoff_date.timetuple())
query = f"before:{epoch}"
```

This eliminates all timezone ambiguity. The epoch format is documented and reliable.

**Warning signs:**
- Using `f"before:{date_str}"` with a Python `datetime.strftime('%Y/%m/%d')` output
- Not explicitly working with UTC throughout date calculation
- User reports "it deleted emails from the wrong day"

**Phase to address:**
Phase 3 (Date parsing and query construction).

---

### Pitfall 5: Rate Limiting Brings Large Deletions to a Halt Without Retry Logic

**What goes wrong:**
The Gmail API enforces per-user limits of 15,000 quota units per minute. `messages.batchDelete` costs 50 quota units per call. This means a sustained deletion of 300 calls/minute (15,000 / 50) is the theoretical ceiling, but in practice Gmail returns HTTP 429 (`Too Many Requests`) or HTTP 403 (`userRateLimitExceeded`) before reaching that ceiling. Without retry logic, the script crashes mid-deletion and must be restarted manually.

**Why it happens:**
Developers loop through IDs and issue `batchDelete` calls as fast as possible without rate-limiting. For large mailboxes (tens of thousands of emails), this immediately saturates per-minute quotas.

**How to avoid:**
Implement exponential backoff with jitter for all API calls. Use `google-api-core`'s built-in retry or implement manually:

```python
import time, random

def delete_with_backoff(service, ids, max_retries=5):
    for attempt in range(max_retries):
        try:
            service.users().messages().batchDelete(
                userId='me', body={'ids': ids}
            ).execute()
            return
        except HttpError as e:
            if e.resp.status in (429, 403) and attempt < max_retries - 1:
                wait = (2 ** attempt) + random.uniform(0, 1)
                time.sleep(wait)
            else:
                raise
```

Also add a configurable `--delay` between batches to stay well below quota limits.

**Warning signs:**
- No sleep/delay between API calls in a loop
- Script crashes with "rateLimitExceeded" after processing some percentage of emails
- No retry logic in delete loop

**Phase to address:**
Phase 4 (Deletion execution). Build retry into the core deletion loop, not as an afterthought.

---

### Pitfall 6: Pagination Stops Early — Missing Emails from Large Mailboxes

**What goes wrong:**
`messages.list` returns a maximum of 500 results per page (default 100). If pagination is not implemented, the tool silently processes only the first page and reports "done" without touching the remaining thousands of emails. There is no error — the API just doesn't return more without `pageToken`. The tool appears to work but deletes only a small fraction of eligible emails.

**Why it happens:**
Developers check the first response, see messages returned, don't notice `nextPageToken` in the response, and treat the first page as the full result set. This is particularly deceptive because `resultSizeEstimate` in the response is just an estimate and may not clearly signal there are more pages.

**How to avoid:**
Always loop on `nextPageToken`:

```python
def get_all_message_ids(service, query):
    ids = []
    page_token = None
    while True:
        response = service.users().messages().list(
            userId='me', q=query, maxResults=500,
            pageToken=page_token
        ).execute()
        ids.extend([m['id'] for m in response.get('messages', [])])
        page_token = response.get('nextPageToken')
        if not page_token:
            break
    return ids
```

Use `maxResults=500` (the maximum) to minimize the number of list API calls.

**Warning signs:**
- No `while True` / `nextPageToken` loop in listing code
- Script completes instantly on a large mailbox with "0 remaining"
- `resultSizeEstimate` is much larger than emails actually processed

**Phase to address:**
Phase 3 (Message discovery). The listing phase must be correct before deletion begins.

---

### Pitfall 7: credentials.json and token.json Committed to Git

**What goes wrong:**
`credentials.json` contains the OAuth client secret. `token.json` (auto-generated) contains a long-lived refresh token granting full Gmail access. Either file committed to a public or private repository gives any viewer the ability to read, modify, or delete the account's email. The project already has `credentials.json`, `client_id`, and `client_secret` files present — these are the exact files that must stay out of version control.

**Why it happens:**
The Google Quickstart guide generates `credentials.json` in the working directory. Developers run `git init` without a `.gitignore`, stage all files, and commit. The token file is auto-generated on first run — developers don't realize it exists or that it's sensitive.

**How to avoid:**
Create `.gitignore` before the first commit:

```
credentials.json
token.json
token.pickle
client_id
client_secret
*.json
```

Set restrictive file permissions immediately:
```bash
chmod 600 credentials.json token.json
```

**Warning signs:**
- No `.gitignore` in project root
- `git status` shows `credentials.json` as untracked but not ignored
- `client_id` and `client_secret` files are tracked

**Phase to address:**
Phase 1 (Project setup), before any `git init` or first commit.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Deleting message IDs as fast as possible (no rate limiting) | Faster completion for small mailboxes | 429 errors on large runs, no recovery | Never — always add backoff |
| Using `before:YYYY/MM/DD` date strings instead of epoch | Simpler code | Off-by-one errors in non-PST timezones | Never — use epoch timestamps |
| Hardcoding `maxResults=100` in list calls | Works for testing | Misses 99% of a large mailbox silently | Never — use 500 and paginate |
| Skipping dry-run implementation to ship faster | Faster first build | First real run can permanently destroy wrong emails | Never — dry-run is table stakes |
| Requesting `gmail.modify` scope instead of `https://mail.google.com/` | Appears less invasive | 403 on every delete call | Never for this use case |
| Storing token.json next to code without .gitignore | Zero setup overhead | Credential leak via git | Never |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gmail OAuth flow | Using default scope (`gmail.readonly` from quickstart) | Explicitly set `SCOPES = ['https://mail.google.com/']` from day one |
| Gmail OAuth flow | Not deleting old `token.json` after changing scopes | Delete `token.json` whenever `SCOPES` changes, then re-auth |
| `messages.batchDelete` | Passing more than ~1000 IDs (undocumented limit) | Chunk ID lists into batches of 100-500 before calling batchDelete |
| `messages.list` | Trusting `resultSizeEstimate` as an accurate count | It is an estimate only — always paginate to get actual count |
| Google Cloud Console | Setting publishing status to "Testing" during development | Set to "Internal" (Workspace) or "Production" before first auth |
| HTTP batch requests | Batching more than 50 requests in one BatchHttpRequest call | Keep HTTP batch calls to ≤50; note this is distinct from `messages.batchDelete` |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No rate limiting between batchDelete calls | Works on first 20 deletions, then 429 errors | Add exponential backoff; optionally add `--delay` flag | ~300+ quota-units-per-minute sustained |
| Fetching full message details during listing phase | Slow, uses 10x more quota | Use `messages.list` for IDs only; fetch details only for dry-run preview | 1,000+ emails |
| Sequential single-message delete instead of batchDelete | 10x slower, 10x more quota used | Use `batchDelete` with chunked ID lists | Any mailbox >100 emails |
| Loading all message IDs into memory before deleting | Fine for most Gmail accounts | RAM pressure on accounts with 500k+ emails | 100k+ message IDs |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing `credentials.json` or `token.json` | Full Gmail account access for anyone with repo access | Add both to `.gitignore` before first commit; use `chmod 600` |
| Requesting `https://mail.google.com/` scope when a narrower scope might do | Broader blast radius if token is compromised | For delete-only operations, `https://mail.google.com/` is actually required; accept it, document it, and protect the token |
| Using `client_id` / `client_secret` files tracked in git | OAuth client exposed; anyone can impersonate the app | Add file names `client_id` and `client_secret` to `.gitignore` |
| Leaving `token.json` world-readable (permissions 644) | Other local users on shared machines can read the token | `chmod 600 token.json` immediately after creation |
| Not handling `invalid_grant` gracefully | Unhandled exception with unhelpful traceback instead of "please re-authenticate" | Catch `RefreshError`, delete stale token file, re-run auth flow |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No dry-run mode by default | User runs tool once and permanently deletes wrong emails | Default to dry-run; require `--execute` or `--confirm` flag for live deletion |
| No count shown before deletion starts | User has no idea if 50 or 50,000 emails will be deleted | Print "Found N emails matching criteria" before any deletion |
| No progress indicator during deletion | Large runs appear frozen; user Ctrl-C's a partial run | Use tqdm or Click's progress bar; show "Deleted X/N" |
| Cryptic Google OAuth browser redirect | First-time users don't understand the browser popup | Print clear instructions: "Opening browser for Gmail authorization. If no browser opens, visit: [URL]" |
| No summary at completion | User doesn't know how many were actually deleted | Print final count: "Deleted 1,247 emails (0 errors)" |
| Silent exit on token expiry | Tool exits with a Python traceback | Catch auth errors and print: "Authentication expired. Delete token.json and run again." |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **OAuth scope**: Verify `https://mail.google.com/` is in `SCOPES`, not `gmail.modify` — test by actually calling `batchDelete`
- [ ] **Dry-run mode**: Verify it uses `messages.list` only and makes NO write calls — confirm with API request logging
- [ ] **Pagination**: Verify all pages are fetched — test against account with >500 matching emails and confirm count matches Gmail web UI
- [ ] **Date handling**: Verify epoch timestamp is used in query, not date string — check by querying near a timezone boundary
- [ ] **Token persistence**: Verify `token.json` is written after auth and reused on next run — test by running twice without re-auth
- [ ] **Rate limit handling**: Verify retry logic fires — test by artificially throttling or monitoring for 429 responses on large runs
- [ ] **.gitignore**: Verify `credentials.json`, `token.json`, `client_id`, `client_secret` are listed before any commit
- [ ] **Confirmation prompt**: Verify live-delete mode requires explicit confirmation — test that Ctrl-C at prompt cancels safely
- [ ] **Progress display**: Verify progress bar shows during deletion and gracefully handles Ctrl-C interrupt without crashing

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong scope cached in token.json | LOW | Delete `token.json`, update `SCOPES`, re-run auth flow |
| Refresh token expired (7-day testing mode) | LOW | Fix consent screen status in GCP Console, delete `token.json`, re-run auth flow |
| Credentials committed to git | HIGH | Rotate OAuth client in GCP Console immediately; force-push git history rewrite or treat repo as compromised |
| Partial deletion due to rate limit crash | LOW | Re-run the tool — already-deleted messages are idempotent (batchDelete won't error on non-existent IDs) |
| Wrong date cutoff deleted too many emails | NONE | Emails deleted via `batchDelete` are permanently gone; no recovery possible — prevention is the only option |
| Pagination bug missed emails on first run | LOW | Re-run the tool with corrected pagination logic; any already-deleted IDs are safely no-ops |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Wrong OAuth scope for batchDelete | Phase 1: OAuth + Auth | Call `batchDelete` with one test ID in a dry-run auth test |
| 7-day token expiry (testing mode) | Phase 1: OAuth + Auth | Confirm GCP Console consent screen shows correct status |
| Credentials committed to git | Phase 1: Project setup | `git status` shows credential files as ignored before first commit |
| Permanent delete irreversibility | Phase 2: CLI + dry-run design | Dry-run mode makes zero write calls (verify with API logging) |
| Date timezone ambiguity | Phase 3: Query construction | Unit test date-to-epoch conversion for UTC boundaries |
| Pagination missing emails | Phase 3: Message discovery | Integration test: account with >500 matching emails |
| Rate limiting crash | Phase 4: Deletion execution | Test backoff by simulating 429 response; verify retry fires |
| Missing progress indicator | Phase 4: Deletion execution | Manual test: watch progress bar during >100-email deletion |

---

## Sources

- [Gmail API Usage Limits (official)](https://developers.google.com/workspace/gmail/api/reference/quota) — HIGH confidence, quota unit costs per method
- [Method: users.messages.batchDelete (official)](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/batchDelete) — HIGH confidence, scope requirement confirmed as `https://mail.google.com/`
- [Method: users.messages.list (official)](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list) — HIGH confidence, maxResults cap of 500
- [Gmail API Error Handling (official)](https://developers.google.com/workspace/gmail/api/guides/handle-errors) — HIGH confidence, 429/403 error codes and backoff recommendation
- [Searching for Messages / Date Filtering (official)](https://developers.google.com/workspace/gmail/api/guides/filtering) — HIGH confidence, PST timezone warning for date strings
- [Gmail API Batching (official)](https://developers.google.com/workspace/gmail/api/guides/batch) — HIGH confidence, 100-call limit, execution order not guaranteed
- [batchDelete returns 403 with gmail.modify scope (Issue #2710, googleapis/google-api-python-client)](https://github.com/googleapis/google-api-python-client/issues/2710) — HIGH confidence, open issue confirmed Jan 2026
- [Google OAuth invalid_grant causes (Nango blog)](https://nango.dev/blog/google-oauth-invalid-grant-token-has-been-expired-or-revoked) — MEDIUM confidence, comprehensive but third-party source
- [Refresh token expires in 7 days (Google Groups)](https://groups.google.com/g/adwords-api/c/Z_kihrf6VCE) — MEDIUM confidence, community-verified pattern

---

*Pitfalls research for: Gmail API bulk-deletion Python CLI*
*Researched: 2026-02-18*
