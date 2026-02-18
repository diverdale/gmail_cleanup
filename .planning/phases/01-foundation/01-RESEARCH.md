# Phase 1: Foundation - Research

**Researched:** 2026-02-18
**Domain:** Python OAuth 2.0 / Gmail API Authentication / Project Skeleton
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Token file location**
- Claude's discretion — user deferred to implementation judgment
- Recommended: store token.json in `~/.config/gmail-clean/token.json` (standard XDG config dir convention for CLI tools, works from any invocation directory regardless of working directory)

**credentials.json location**
- Claude's discretion — user deferred to implementation judgment
- Recommended: look up credentials.json relative to the script/package location (not CWD), so the tool works from any directory

### Claude's Discretion
- Token and credential file path resolution strategy (use ~/.config/gmail-clean/ for token, script-relative for credentials.json)
- Module structure: 4-module layout (main.py, auth.py, gmail_client.py, cleaner.py) vs single file — choose what is cleanest for v1
- First-run messaging: what to print before/after browser opens for OAuth

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | Project initialized with .gitignore covering all credential files (credentials.json, token.json, client_id, client_secret) before any commit | .gitignore patterns section; note these files already exist in repo — gitignore must also retroactively remove them from tracking |
| AUTH-02 | User can authenticate with Gmail via OAuth on first run (browser prompt) with silent token refresh on subsequent runs | InstalledAppFlow + token caching pattern; Credentials.from_authorized_user_file + creds.refresh(Request()) pattern documented |
| AUTH-03 | Tool uses `https://mail.google.com/` scope to enable permanent batch deletion | Scope research confirms this is the correct and required scope; gmail.modify returns 403 on batchDelete per confirmed GitHub issue #2710 |
</phase_requirements>

---

## Summary

This phase establishes the secure project skeleton and working Gmail OAuth authentication. The locked stack (Python 3.12, google-api-python-client 2.190.0, google-auth 2.48.0, google-auth-oauthlib 1.2.4, Typer 0.24.0, Rich 14.1.0, uv) is well-supported by official documentation and Context7 research.

The critical OAuth pattern is well-established by Google's official quickstart: use `InstalledAppFlow.from_client_secrets_file()` for first-run browser auth, then serialize credentials to token.json with `creds.to_json()`. On subsequent runs, load from file with `Credentials.from_authorized_user_file()` and call `creds.refresh(Request())` if expired. The library handles all token exchange and refresh internally — there is nothing to hand-roll.

The most important security constraint is credential file protection before any code commit. The project directory already contains `credentials.json`, `client_id`, and `client_secret` files that are currently unprotected by .gitignore. The first task of this phase must create a complete .gitignore (including the future `token.json` location) and use `git rm --cached` to stop tracking any already-staged credential files.

**Primary recommendation:** Implement auth as a standalone `auth.py` module using the standard Google quickstart pattern, storing token at `~/.config/gmail-clean/token.json` via pathlib, and resolving credentials.json relative to the package using `Path(__file__).parent`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-api-python-client | 2.190.0 | Gmail API service object (`build("gmail", "v1", ...)`) | Official Google client library for Python |
| google-auth | 2.48.0 | `Credentials` class, token refresh via `Request()` | Google's auth library, required by above |
| google-auth-oauthlib | 1.2.4 | `InstalledAppFlow` — handles browser OAuth dance | Google's oauthlib integration for installed apps |
| Python | 3.12 | Runtime | Locked by user; pinned via .python-version |
| uv | latest | Package manager, virtual env, project init | Locked by user |

### Supporting (Future Phases — Install Now)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Typer | 0.24.0 | CLI framework | Phase 2+ for command parsing |
| Rich | 14.1.0 | Terminal output formatting | Phase 2+ for pretty output |
| python-dateutil | latest stable | Date parsing for email filters | Phase 3+ for date-based filtering |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `run_local_server()` | `run_console()` | run_console requires manual copy-paste of auth code; run_local_server is fully automatic. Use run_local_server. |
| `~/.config/gmail-clean/token.json` | `./token.json` in project dir | CWD-relative breaks when tool is invoked from another directory. Use XDG path. |
| `Path(__file__).parent` for credentials | `os.getcwd()` | CWD is unpredictable; `__file__` is stable for installed packages. Use `__file__`. |

**Installation:**

```bash
uv add google-api-python-client==2.190.0 google-auth==2.48.0 google-auth-oauthlib==1.2.4 typer==0.24.0 rich==14.1.0 python-dateutil
```

Note: `google-auth-httplib2` is required by google-api-python-client as a transport layer but is installed as a transitive dependency.

---

## Architecture Patterns

### Recommended Project Structure

```
gmail_cleanup/                  # project root
├── .gitignore                  # MUST exist before first commit; covers all creds
├── .python-version             # should contain "3.12" (currently wrong — see pitfalls)
├── credentials.json            # listed in .gitignore, removed from git tracking
├── pyproject.toml              # uv project config with dependencies + entry point
├── uv.lock                     # generated by uv
└── gmail_cleanup/              # Python package (src layout if uv --package)
    ├── __init__.py
    ├── main.py                 # Typer app entry point
    ├── auth.py                 # OAuth logic — the focus of this phase
    ├── gmail_client.py         # Gmail API wrapper (stub in phase 1)
    └── cleaner.py              # Email deletion logic (stub in phase 1)
```

### Pattern 1: Token-Caching OAuth Flow

**What:** Check for existing token on each startup; refresh silently if expired; only trigger browser on first run or if token is revoked.

**When to use:** Every time the tool starts — this is the auth entry point.

**Example:**

```python
# Source: https://developers.google.com/workspace/gmail/api/quickstart/python
# Adapted for XDG token path

import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://mail.google.com/"]
TOKEN_PATH = Path.home() / ".config" / "gmail-clean" / "token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"

def get_credentials() -> Credentials:
    """Load or acquire Gmail OAuth credentials with token caching."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message="",  # We print our own message
                success_message="Authentication complete. You can close this tab.",
            )
        # Persist token for next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def build_gmail_service():
    """Return authenticated Gmail API service object."""
    creds = get_credentials()
    return build("gmail", "v1", credentials=creds)
```

### Pattern 2: Credentials Path Resolution

**What:** Resolve `credentials.json` relative to the module file, not CWD, so the tool works from any directory.

**When to use:** Any time credentials.json is referenced in code.

```python
# Source: Python stdlib pathlib docs
# https://docs.python.org/3/library/pathlib.html

from pathlib import Path

# auth.py lives at: gmail_cleanup/auth.py
# credentials.json lives at: gmail_cleanup/ (project root, one level up from package)
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"
```

### Pattern 3: First-Run Messaging (Claude's Discretion)

**What:** Print clear user messaging before and after browser opens.

**Recommendation:** Print before calling `run_local_server()`, since the function blocks until auth completes.

```python
# Before calling flow.run_local_server():
print("Opening your browser for Gmail authentication...")
print("If the browser does not open, visit the URL printed below.")

creds = flow.run_local_server(
    port=0,
    open_browser=True,
    authorization_prompt_message="",   # suppress duplicate URL print
    success_message="Authentication complete. You can close this tab.",
)

print("Authentication successful. Token saved.")
```

### Pattern 4: .gitignore Credential Protection

**What:** Gitignore must cover all current and future credential files.

```gitignore
# OAuth credentials — NEVER commit these
credentials.json
token.json
client_id
client_secret
client_secret*.json

# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
dist/
.uv/

# Environment
.env
```

**Critical:** Files already tracked by git must be explicitly un-tracked:
```bash
git rm --cached credentials.json client_id client_secret
git commit -m "chore: remove credential files from git tracking"
```

### Anti-Patterns to Avoid

- **Storing token.json in CWD:** The tool breaks when invoked from a different directory. Use `~/.config/gmail-clean/token.json`.
- **Using `os.getcwd()` to find credentials.json:** Use `Path(__file__).parent.parent` for package-relative resolution.
- **Opening browser with `run_console()`:** Requires manual copy-paste of auth code; `run_local_server(port=0)` is fully automatic.
- **Not creating token dir before writing:** `~/.config/gmail-clean/` may not exist; call `.mkdir(parents=True, exist_ok=True)` before writing.
- **Committing before .gitignore is in place:** Add .gitignore and remove tracked files before any other commit.
- **Using `gmail.modify` scope:** Confirmed to return 403 on `batchDelete`; must use `https://mail.google.com/`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth browser flow + token exchange | Custom HTTP server + auth code handler | `InstalledAppFlow.run_local_server()` | Handles redirect server, code exchange, error states, browser launch |
| Token refresh logic | Custom token expiry check + HTTP call | `creds.refresh(Request())` | Handles clock skew, retry, error types |
| Token serialization | Custom JSON format for credentials | `creds.to_json()` + `Credentials.from_authorized_user_file()` | Round-trips all required fields; format compatible with gcloud tooling |
| Gmail API request construction | Hand-crafted HTTP requests to Gmail API | `build("gmail", "v1", credentials=creds)` | Handles discovery document, serialization, error mapping |
| Config dir creation | `os.makedirs` + error handling | `pathlib.Path.mkdir(parents=True, exist_ok=True)` | Atomic, exception-safe, cross-platform |

**Key insight:** Google's auth libraries handle every edge case in the OAuth installed app flow. The entire auth implementation fits in ~25 lines of code. Any hand-rolled version will miss token expiry edge cases, refresh error handling, and secure redirect server behavior.

---

## Common Pitfalls

### Pitfall 1: Wrong .python-version Format

**What goes wrong:** The existing `.python-version` file contains `gmail_cleanup` (the workspace name) instead of a Python version number. uv will fail to resolve the Python interpreter.

**Why it happens:** `uv init` may have written the workspace name rather than a version in some flows, or the file was manually created incorrectly.

**How to avoid:** The file must contain only a version number:
```
3.12
```
Replace the current content with `3.12` before running `uv sync`.

**Warning signs:** uv commands fail with "No interpreter found" or similar errors.

### Pitfall 2: Wrong OAuth Scope for batchDelete

**What goes wrong:** Using `https://www.googleapis.com/auth/gmail.modify` scope causes `batchDelete` to return HTTP 403 `insufficientPermissions`, even though documentation implies it should work.

**Why it happens:** Gmail backend enforces stricter permissions for permanent deletion than the documented scope hierarchy suggests. Confirmed in GitHub issue googleapis/google-api-python-client#2710 (open as of Feb 2026, no fix).

**How to avoid:** Always use `SCOPES = ["https://mail.google.com/"]`. If the scope is ever changed, delete `token.json` and re-authenticate — the library will not automatically re-request new scopes from an existing token.

**Warning signs:** `HttpError 403` on `batchDelete` calls that otherwise succeed with list/modify operations.

### Pitfall 3: Credential Files Already Tracked by Git

**What goes wrong:** Adding `credentials.json` to `.gitignore` does NOT remove it from git tracking if it was previously committed. The file continues to be tracked and will be committed on future pushes.

**Why it happens:** `.gitignore` only prevents new untracked files from being staged. Already-tracked files are unaffected.

**How to avoid:** After creating .gitignore, run:
```bash
git rm --cached credentials.json client_id client_secret
```
Then commit the removal before making any other changes.

**Warning signs:** `git status` still shows `credentials.json` as a tracked file after adding .gitignore.

### Pitfall 4: Token Directory May Not Exist

**What goes wrong:** `~/.config/gmail-clean/` doesn't exist on a fresh machine; writing `token.json` to it raises `FileNotFoundError`.

**Why it happens:** Unlike `~/.config`, the app-specific subdirectory is never pre-created by the OS.

**How to avoid:** Always call `.mkdir(parents=True, exist_ok=True)` on `TOKEN_PATH.parent` before writing the token file.

**Warning signs:** `FileNotFoundError` on first run when saving token.

### Pitfall 5: Scope Mismatch in Cached Token

**What goes wrong:** If you change SCOPES after token.json was written, the cached token has the old scope. Auth appears to succeed (token loads, valid returns True) but API calls fail with 403.

**Why it happens:** The cached token's scope is not re-validated against the requested scopes at load time by `from_authorized_user_file()`.

**How to avoid:** Document in code: "If modifying SCOPES, delete token.json". When changing scopes during development, always delete the token file first.

**Warning signs:** Auth succeeds silently but API operations return 403.

---

## Code Examples

Verified patterns from official sources:

### Complete Auth Module (Phase 1 Target)

```python
# Source: Based on https://developers.google.com/workspace/gmail/api/quickstart/python
# Adapted for XDG token path and package-relative credentials

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# https://mail.google.com/ is required for batchDelete — gmail.modify returns 403
# Source: googleapis/google-api-python-client issue #2710
SCOPES = ["https://mail.google.com/"]

# Token stored in XDG config dir — works regardless of invocation directory
TOKEN_PATH = Path.home() / ".config" / "gmail-clean" / "token.json"

# credentials.json is in the package root — resolved relative to this file
# auth.py is at: <root>/gmail_cleanup/auth.py
# credentials.json is at: <root>/credentials.json
CREDENTIALS_PATH = Path(__file__).parent.parent / "credentials.json"


def get_credentials() -> Credentials:
    """Load cached credentials or trigger OAuth browser flow."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Silent refresh — no browser needed
            creds.refresh(Request())
        else:
            # First run: open browser for user consent
            print("Opening browser for Gmail authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_PATH), SCOPES
            )
            creds = flow.run_local_server(
                port=0,
                open_browser=True,
                authorization_prompt_message="",
                success_message="Authentication complete. You can close this tab.",
            )
            print("Authentication successful.")

        # Persist token for next run
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds


def build_gmail_service():
    """Return authenticated Gmail API service object."""
    return build("gmail", "v1", credentials=get_credentials())
```

### Verifying Gmail Connection (Phase 1 Smoke Test)

```python
# Source: https://developers.google.com/workspace/gmail/api/quickstart/python
from googleapiclient.errors import HttpError

def verify_connection(service) -> bool:
    """Verify Gmail API connection by fetching user profile."""
    try:
        profile = service.users().getProfile(userId="me").execute()
        print(f"Connected as: {profile['emailAddress']}")
        return True
    except HttpError as error:
        print(f"Gmail API error: {error}")
        return False
```

### uv pyproject.toml for CLI Tool

```toml
# Source: https://docs.astral.sh/uv/concepts/projects/init/
[project]
name = "gmail-cleanup"
version = "0.1.0"
description = "Gmail cleanup CLI tool"
requires-python = ">=3.12"
dependencies = [
    "google-api-python-client==2.190.0",
    "google-auth==2.48.0",
    "google-auth-oauthlib==1.2.4",
    "google-auth-httplib2",
    "typer==0.24.0",
    "rich==14.1.0",
    "python-dateutil",
]

[project.scripts]
gmail-clean = "gmail_cleanup.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `oauth2client` library | `google-auth` + `google-auth-oauthlib` | ~2018-2019 | oauth2client is deprecated; all Google samples now use google-auth |
| `creds.valid` / `creds.expired` | `creds.token_state` (new API) | google-auth 2.x | `valid` and `expired` are deprecated; `token_state` is the future-facing API, but `valid`/`expired` still work and all official samples still use them |
| `flow.run_console()` | `flow.run_local_server(port=0)` | Several years | run_console requires manual copy-paste; run_local_server is fully automatic |
| Hardcoded `port=8080` | `port=0` (OS-assigned) | Best practice now | Port 8080 may be in use; `port=0` lets OS assign an available port |

**Deprecated/outdated:**
- `oauth2client`: Do not use. Replaced entirely by `google-auth`. Not installed by the locked stack.
- `flow.run_console()`: Avoid unless running in headless environment without browser access.
- `creds.valid` / `creds.expired` properties: Technically deprecated in favor of `token_state`, but still functional. Current official docs still use `valid`/`expired` in all examples, so continue using them for now.

---

## Open Questions

1. **`.python-version` file content**
   - What we know: Current file contains `gmail_cleanup` (the workspace name), not a version number
   - What's unclear: Whether this was intentional for a uv workspace setup or simply incorrect
   - Recommendation: Replace contents with `3.12` — this is the locked Python version and the correct format per uv docs

2. **pyproject.toml build backend choice**
   - What we know: uv's `--package` init uses `uv_build` as build backend; the existing project has no pyproject.toml
   - What's unclear: Whether to use `uv_build` (uv-native, newest) or `hatchling` (more widely supported)
   - Recommendation: Use `hatchling` for broader compatibility; uv supports both. The planner should pick one and document the choice.

3. **credentials.json path in installed vs dev mode**
   - What we know: `Path(__file__).parent.parent / "credentials.json"` works when running from source; behavior in `uv tool install` or zipapp distribution is less certain
   - What's unclear: Long-term distribution strategy
   - Recommendation: For this personal CLI tool, `Path(__file__).parent.parent` is sufficient. Document that credentials.json must be co-located with the package root. Not a blocker for phase 1.

---

## Sources

### Primary (HIGH confidence)
- https://developers.google.com/workspace/gmail/api/quickstart/python — Official Gmail Python quickstart; complete token caching pattern
- https://developers.google.com/workspace/gmail/api/auth/scopes — Gmail scope documentation; `https://mail.google.com/` = "Full access including permanent deletion"
- https://googleapis.dev/python/google-auth/latest/reference/google.oauth2.credentials.html — Credentials class API: `from_authorized_user_file`, `to_json`, `refresh`, `token_state`
- https://googleapis.dev/python/google-auth-oauthlib/latest/reference/google_auth_oauthlib.flow.html — InstalledAppFlow API: `run_local_server` parameters including `open_browser`, `success_message`, `authorization_prompt_message`
- https://googleapis.github.io/google-api-python-client/docs/oauth-installed.html — Installed app OAuth flow documentation
- https://docs.astral.sh/uv/concepts/projects/init/ — uv project init docs; `--package` flag, `[project.scripts]` entry points
- https://docs.astral.sh/uv/concepts/python-versions/ — `.python-version` format: must contain a version number, not a name
- https://docs.python.org/3/library/pathlib.html — `Path.home()`, `Path.mkdir(parents=True, exist_ok=True)`

### Secondary (MEDIUM confidence)
- https://github.com/googleapis/google-api-python-client/issues/2710 — Confirms batchDelete returns 403 with `gmail.modify` scope; `https://mail.google.com/` works. Issue open as of Feb 2026 with no resolution.
- https://bgstack15.ddns.net/blog/posts/2025/10/30/xdg-config-home-for-python/ — XDG config home for Python CLI tools; confirms `~/.config` pattern

### Tertiary (LOW confidence)
- WebSearch results about uv project structure — multiple tutorials consistent with official docs, not independently verified

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions explicitly locked by user; official Google libraries with stable APIs
- OAuth pattern: HIGH — copied directly from official Google quickstart; verified against google-auth API docs
- Scope requirement: HIGH — confirmed by Gmail scope documentation + verified by open GitHub issue showing empirical evidence
- Architecture (module layout): MEDIUM — 4-module layout is conventional for Python CLI tools; no single authoritative source for this structure
- .python-version issue: HIGH — uv docs explicitly state format must be a version number
- XDG path strategy: MEDIUM — well-established convention verified across multiple sources, not a formal standard for macOS

**Research date:** 2026-02-18
**Valid until:** 2026-03-20 (30 days — stable APIs, unlikely to change)
