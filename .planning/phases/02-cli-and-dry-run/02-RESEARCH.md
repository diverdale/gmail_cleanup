# Phase 2: CLI and Dry-run - Research

**Researched:** 2026-02-18
**Domain:** Typer 0.24.0 CLI patterns, python-dateutil, Rich console output, dry-run architecture
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CLI-01 | User can run `gmail-clean --older-than N` to target emails older than N months | `typer.Option('--older-than', min=1)` with `Optional[int]`; dateutil `relativedelta(months=N)` for cutoff calculation |
| CLI-02 | User can run `gmail-clean --before YYYY-MM-DD` to target emails older than a specific date | `typer.Option('--before', callback=validate_date)` with `Optional[str]`; `date.fromisoformat()` + `datetime.timestamp()` for epoch |
| CLI-03 | Tool runs in dry-run mode by default; user must pass `--execute` to perform live deletion | `typer.Option('--execute')` boolean flag defaulting to `False`; conditional branch in `main()` |
| CLI-04 | Before live deletion, tool shows count and prompts "Delete permanently? [y/N]" requiring explicit confirmation | `typer.confirm('Delete permanently', default=False)` — Click renders `[y/N]` automatically; `Exit(0)` on decline |
</phase_requirements>

---

## Summary

Phase 2 builds the full CLI surface and dry-run safety contract on top of Phase 1's auth infrastructure. The key challenge is wiring four CLI requirements into a cohesive `main()` that is safe by default: both `--older-than N` and `--before YYYY-MM-DD` inputs must be validated at the CLI layer, mutually exclusive with each other, and neither triggers any write call unless `--execute` is explicitly passed.

Typer 0.24.0 (installed in the project venv) provides all required primitives directly: `Optional[int]` options with `min=` validation, `Optional[str]` options with `callback=` for date format checking, boolean flags, and `typer.confirm()` (re-exported from Click). Rich 14.1.0 is available for styled output but `typer.echo()` is sufficient for Phase 2's simple messages. The `python-dateutil` package (version 2.9.0.post0) is installed and provides `relativedelta` for calendar-correct "N months ago" arithmetic.

The stub count approach for Phase 2 is: implement a minimal `count_messages(service, query)` function in `gmail_client.py` that calls `messages().list()` with a single page (maxResults=500) and returns `len(result.get('messages', []))`. This is explicitly approximate and will be replaced by accurate paginated counting in Phase 3. The existing `list_messages()` stub (which raises `NotImplementedError`) must NOT be called in Phase 2 — a separate `count_messages()` function avoids breaking the Phase 3 contract.

**Primary recommendation:** Build `main()` with `Optional[int]` + `Optional[str]` options, manual mutual-exclusivity guard at the top of the function body, `date.fromisoformat()` validation via callback, and `typer.confirm('Delete permanently', default=False)` for the confirmation gate. Pass `dry_run: bool` explicitly through the call stack — do not use a global.

---

## Standard Stack

### Core (already installed in project venv)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| typer | 0.24.0 | CLI option/flag parsing, help generation, confirm prompt | Project decision; already installed |
| python-dateutil | 2.9.0.post0 | Calendar-correct relativedelta for "N months ago" | Already installed; handles month-boundary edge cases stdlib timedelta cannot |
| rich | 14.1.0 | Styled terminal output | Already installed; Typer uses it for help rendering automatically |

### Supporting (stdlib — no install needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime | stdlib | date objects, timestamp conversion | YYYY-MM-DD parsing and epoch calculation |
| typing | stdlib | `Annotated`, `Optional` | Typer 0.24.0 Annotated-style parameter declarations |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `typer.confirm()` | `rich.prompt.Confirm.ask()` | Rich version is prettier but typer.confirm is already available via typer's re-export; no extra import needed |
| `date.fromisoformat()` callback | `typer.Option(formats=[...])` with `datetime` type | Typer's `formats=` parameter auto-parses to `datetime` object but is harder to test and less transparent; callback approach is simpler and gives explicit error messages |
| manual mutual exclusion guard | Click's `cls=` with custom mutex group | Custom Click class adds complexity; manual guard in function body is idiomatic Typer and easier to read |

**Installation:** Nothing to install — all required libraries are in `pyproject.toml` and the `.venv` already.

---

## Architecture Patterns

### Recommended Module Structure

The Phase 2 additions touch these files:

```
gmail_cleanup/
├── main.py          # REPLACE: full CLI command with all 4 options wired
├── gmail_client.py  # ADD: count_messages(service, query) stub
└── cleaner.py       # UNCHANGED (still Phase 4 stub)
```

No new modules needed for Phase 2.

### Pattern 1: Annotated-Style Option Declaration (Typer 0.24.0 standard)

**What:** Use `Annotated[Type, typer.Option(...)]` with the default as a separate `= value` at the end. This is the current Typer-recommended style (the old `= typer.Option(default)` style is deprecated per the source docs).

**When to use:** All CLI options in this project.

**Example (verified against installed typer/params.py):**
```python
# Source: .venv/lib/python3.12/site-packages/typer/params.py
from typing import Annotated, Optional
import typer

@app.command()
def main(
    older_than: Annotated[
        Optional[int],
        typer.Option("--older-than", min=1, help="Target emails older than N months"),
    ] = None,
    before: Annotated[
        Optional[str],
        typer.Option("--before", callback=validate_date, help="Target emails before YYYY-MM-DD"),
    ] = None,
    execute: Annotated[
        bool,
        typer.Option("--execute", help="Perform live deletion (default: dry-run)"),
    ] = False,
) -> None:
    ...
```

### Pattern 2: Date Callback Validation

**What:** A Typer `callback=` function receives the raw string value, validates format, raises `typer.BadParameter` on failure.

**When to use:** `--before YYYY-MM-DD` — validates at parse time, before main() body runs.

**Example (verified by running against installed typer 0.24.0):**
```python
# Source: verified via CliRunner test in project venv
from datetime import date
import typer

def validate_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        date.fromisoformat(value)
        return value
    except ValueError:
        raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD.")
```

Output on invalid input (Rich-rendered by Typer automatically):
```
╭─ Error ──────────────────────────────────────────────────────────╮
│ Invalid value for '--before': Invalid date format. Use YYYY-MM-DD.│
╰──────────────────────────────────────────────────────────────────╯
```

### Pattern 3: Mutual Exclusion Guard

**What:** Manual validation at the top of the command function body. Typer/Click have no built-in mutually exclusive option support; the idiomatic pattern is a manual guard.

**When to use:** When two options are mutually exclusive (`--older-than` and `--before`).

**Example (verified by running against installed typer 0.24.0):**
```python
# Source: verified via CliRunner test in project venv
def main(...) -> None:
    if older_than is None and before is None:
        raise typer.BadParameter("Must specify --older-than N or --before YYYY-MM-DD")
    if older_than is not None and before is not None:
        raise typer.BadParameter("Cannot specify both --older-than and --before")
```

### Pattern 4: Epoch Cutoff Calculation

**What:** Convert CLI input to a Unix epoch timestamp for use in Gmail query. Both paths (months-ago and absolute date) normalize to midnight local time to avoid mid-day ambiguity.

**When to use:** Building the `before:EPOCH` Gmail query string.

**Example (verified by running in project venv):**
```python
# Source: verified via Python test in project venv
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

def build_cutoff_epoch(
    older_than: Optional[int],
    before: Optional[str],
) -> int:
    if older_than is not None:
        # Calendar-correct: handles month-length differences
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = now - relativedelta(months=older_than)
    else:
        # Absolute date: midnight local time
        d = date.fromisoformat(before)  # type: ignore[arg-type]
        cutoff = datetime(d.year, d.month, d.day, 0, 0, 0)
    return int(cutoff.timestamp())
```

### Pattern 5: typer.confirm() for Destructive Confirmation

**What:** `typer.confirm(text, default=False)` renders `"{text} [y/N]: "` and returns `True` if user types `y`/`Y`, `False` for `n`/`N` or Enter (default=False means Enter = No). On decline, print cancellation message and raise `typer.Exit(0)`.

**Key finding:** Do NOT include `[y/N]` in the prompt text — Click appends it automatically. Using `typer.Abort()` instead of `typer.Exit(0)` sets exit code 1 (indicating error), which is wrong for a clean user cancellation.

**Example (verified by running against installed typer 0.24.0):**
```python
# Source: verified via CliRunner test in project venv
# typer.confirm is re-exported from click.termui.confirm
confirmed = typer.confirm("Delete permanently", default=False)
# Renders: "Delete permanently [y/N]: "
if not confirmed:
    typer.echo("Cancelled.")
    raise typer.Exit(0)  # exit code 0 = clean cancellation, not an error
```

### Pattern 6: Dry-run Threading via Explicit Parameter

**What:** Pass `dry_run: bool` explicitly to every function that could trigger a write. No global state. Functions that receive `dry_run=True` return counts without executing side effects.

**When to use:** This is the only safe pattern — global state breaks testability.

**Example:**
```python
# main.py
def main(..., execute: bool = False) -> None:
    dry_run = not execute
    count = count_messages(service, query)  # Phase 2 stub — always read-only

    if dry_run:
        typer.echo(f"Dry-run: found {count} emails matching filter.")
        typer.echo("No changes made. Pass --execute to delete.")
        return

    # Live path: confirm then delegate to cleaner (Phase 4)
    typer.echo(f"Found {count} emails.")
    confirmed = typer.confirm("Delete permanently", default=False)
    if not confirmed:
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    # Phase 4 wires in: batch_delete(service, message_ids)
    typer.echo("(Deletion not implemented yet — Phase 4)")
```

### Pattern 7: Phase 2 Stub Count in gmail_client.py

**What:** Add a `count_messages(service, query)` function that makes a single (non-paginated) `messages().list()` call and returns the count of IDs in the first page. This is explicitly approximate — Phase 3 replaces it with a paginated version.

**Critical:** Do NOT call or replace `list_messages()` (the Phase 3 stub). Add a separate `count_messages()` function. This keeps the Phase 3 contract clean.

**Example:**
```python
# gmail_cleanup/gmail_client.py — Phase 2 addition
def count_messages(service, query: str) -> int:
    """Return approximate count of messages matching query.

    Uses a single API call with maxResults=500. For mailboxes with
    more than 500 matching messages, this count will be truncated.
    Phase 3 replaces this with an accurate paginated implementation.
    """
    result = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=500,
    ).execute()
    return len(result.get("messages", []))
```

### Anti-Patterns to Avoid

- **Using `typer.Abort()` for user cancellation on "N" answer:** Sets exit code 1 (error). Use `typer.Exit(0)` for clean cancellation.
- **Including `[y/N]` in `typer.confirm()` text:** Click renders it automatically, resulting in `"Delete permanently [y/N] [y/N]: "` duplication.
- **Calling `list_messages()` in Phase 2:** It raises `NotImplementedError`. Use the new `count_messages()` instead.
- **Global `dry_run` state:** Makes functions impossible to unit test in isolation.
- **Using `timedelta` for month arithmetic:** `timedelta(days=30*N)` is wrong for calendar months (Feb, months with 31 days). Use `relativedelta(months=N)`.
- **Treating `--execute` absence as an implicit "force":** The name `--execute` is the correct affirmative flag; `--no-execute` or `--dry-run` should not be added.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI argument parsing | Custom `sys.argv` parser | `typer.Option()` | Handles type coercion, help text, error formatting, metavar display automatically |
| Yes/No confirmation prompt | `input("Delete? ")` + manual parsing | `typer.confirm()` | Handles empty input (default), case-insensitive y/Y, EOF handling |
| Date validation error message | Manual `try/except` + `typer.echo(err)` + `raise SystemExit` | `raise typer.BadParameter(msg)` | Typer/Rich formats the error in a styled panel with option name and usage hint automatically |
| Month arithmetic | `datetime.now() - timedelta(days=N*30)` | `relativedelta(months=N)` | `timedelta` gives wrong results for calendar months (30 days != 1 month) |
| YYYY-MM-DD parsing | `datetime.strptime(val, "%Y-%m-%d")` | `date.fromisoformat(val)` | stdlib, cleaner, same result for ISO 8601 dates |

**Key insight:** Typer's `BadParameter` + Rich error rendering gives professional-looking error output for free. Never print error messages manually for validation failures.

---

## Common Pitfalls

### Pitfall 1: typer.Abort() vs typer.Exit() for Cancellation

**What goes wrong:** Using `raise typer.Abort()` when the user answers "N" to the confirmation prompt. The terminal prints "Aborted!" and the process exits with code 1 (error), even though the user deliberately chose not to proceed.

**Why it happens:** `Abort` is designed for Ctrl-C interruption, not intentional cancellation.

**How to avoid:** Use `raise typer.Exit(0)` after printing a "Cancelled." message for user-initiated cancellation.

**Warning signs:** Exit code 1 on `n` answer in tests; "Aborted!" appearing in output.

### Pitfall 2: [y/N] Duplication in Confirm Prompt

**What goes wrong:** Passing `"Delete permanently? [y/N]"` as the confirm text produces `"Delete permanently? [y/N] [y/N]: "` in the terminal.

**Why it happens:** `typer.confirm()` delegates to `click.confirm()` which always appends the `[y/N]` suffix to the prompt text.

**How to avoid:** Pass only the question text: `typer.confirm("Delete permanently", default=False)`.

**Warning signs:** Double `[y/N]` visible in test output or terminal.

### Pitfall 3: Calling list_messages() in Phase 2

**What goes wrong:** Phase 2 calls `list_messages()` to get a count, which raises `NotImplementedError` at runtime.

**Why it happens:** The existing stub contract says "Phase 3". Calling it breaks the tool before Phase 3 is implemented.

**How to avoid:** Add a separate `count_messages()` function in `gmail_client.py` for Phase 2. Keep `list_messages()` as the Phase 3 stub.

**Warning signs:** `NotImplementedError` at runtime; Phase 3 contract violated.

### Pitfall 4: timedelta for Month Arithmetic

**What goes wrong:** `datetime.now() - timedelta(days=6*30)` computes 180 days, not 6 calendar months. On March 1, "6 months ago" via timedelta lands on Sept 2 (not Sept 1), or gives wrong results in February.

**Why it happens:** Calendar months have variable lengths; timedelta operates in fixed day counts.

**How to avoid:** Use `datetime.now() - relativedelta(months=6)` from `python-dateutil`.

**Warning signs:** Off-by-one date errors near month boundaries; Feb, Aug, or 31-day months affected.

### Pitfall 5: No Guard for Missing Both Arguments

**What goes wrong:** If neither `--older-than` nor `--before` is passed, `main()` has `None` for both and will crash or silently operate with an undefined query.

**Why it happens:** Both are `Optional[...]` with `= None` defaults; Typer will not auto-require one-of-two.

**How to avoid:** Add explicit guard at the start of `main()`:
```python
if older_than is None and before is None:
    raise typer.BadParameter("Must specify --older-than N or --before YYYY-MM-DD")
```

**Warning signs:** `AttributeError` or silent Gmail query with no filter.

### Pitfall 6: Epoch Converts in UTC Instead of Local Time

**What goes wrong:** Using `datetime.utcnow()` or `datetime(..., tzinfo=timezone.utc).timestamp()` produces UTC midnight instead of local midnight for the cutoff. A user saying "before Jan 1 2024" expects their local timezone's start of day, not UTC's.

**Why it happens:** The decision to use epoch timestamps is for API correctness (Phase 3 concern), but the conversion must use local time to match user expectations.

**How to avoid:** Use naive `datetime` objects (no tzinfo) with `datetime.now()` and `.timestamp()`, which Python converts using the local timezone.

**Warning signs:** Off-by-hours cutoff discrepancy; users in non-UTC timezones see wrong results.

---

## Code Examples

Verified patterns from running against installed packages in the project venv:

### Complete main() Command Skeleton

```python
# Source: verified by running in /Users/dalwrigh/dev/gmail_cleanup/.venv
"""Gmail Cleanup CLI — Phase 2: full CLI surface with dry-run default."""

from datetime import date, datetime
from typing import Annotated, Optional

import typer
from dateutil.relativedelta import relativedelta
from googleapiclient.errors import HttpError

from gmail_cleanup.auth import build_gmail_service
from gmail_cleanup.gmail_client import count_messages

app = typer.Typer(
    name="gmail-clean",
    help="Delete old Gmail messages from the command line.",
    add_completion=False,
)


def _validate_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        date.fromisoformat(value)
        return value
    except ValueError:
        raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD.")


def _build_cutoff_epoch(
    older_than: Optional[int],
    before: Optional[str],
) -> int:
    if older_than is not None:
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff = now - relativedelta(months=older_than)
    else:
        d = date.fromisoformat(before)  # type: ignore[arg-type]
        cutoff = datetime(d.year, d.month, d.day, 0, 0, 0)
    return int(cutoff.timestamp())


@app.command()
def main(
    older_than: Annotated[
        Optional[int],
        typer.Option(
            "--older-than",
            min=1,
            help="Target emails older than N months.",
            metavar="MONTHS",
        ),
    ] = None,
    before: Annotated[
        Optional[str],
        typer.Option(
            "--before",
            callback=_validate_date,
            help="Target emails older than this date.",
            metavar="YYYY-MM-DD",
        ),
    ] = None,
    execute: Annotated[
        bool,
        typer.Option(
            "--execute",
            help="Perform live deletion. Default is dry-run (no changes).",
        ),
    ] = False,
) -> None:
    """Delete old Gmail messages matching a date filter."""
    # Mutual exclusion guard
    if older_than is None and before is None:
        raise typer.BadParameter("Must specify --older-than MONTHS or --before YYYY-MM-DD")
    if older_than is not None and before is not None:
        raise typer.BadParameter("Cannot specify both --older-than and --before")

    # Build authenticated service
    try:
        service = build_gmail_service()
    except FileNotFoundError as exc:
        typer.echo(f"Error: credentials.json not found — {exc}", err=True)
        raise typer.Exit(code=1)

    # Build Gmail query
    epoch = _build_cutoff_epoch(older_than, before)
    query = f"before:{epoch}"

    # Get approximate count (Phase 2 stub — Phase 3 makes this accurate)
    try:
        count = count_messages(service, query)
    except HttpError as exc:
        typer.echo(f"Gmail API error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not execute:
        typer.echo(f"Dry-run: found {count} emails matching filter.")
        typer.echo("No changes made. Pass --execute to delete.")
        return

    # Live deletion path
    typer.echo(f"Found {count} emails.")
    confirmed = typer.confirm("Delete permanently", default=False)
    if not confirmed:
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    # Phase 4 wires deletion here
    typer.echo("(Live deletion not yet implemented — Phase 4)")
```

### count_messages() Stub in gmail_client.py

```python
# Source: verified API call shape matches Phase 1's smoke test in main.py
def count_messages(service, query: str) -> int:
    """Return approximate count of messages matching query.

    Single-page, non-paginated. Returns at most 500. Phase 3 replaces
    this with an accurate paginated implementation via list_messages().
    """
    result = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=500,
    ).execute()
    return len(result.get("messages", []))
```

### Date Callback Producing Rich Error Panel

```python
# typer.BadParameter produces a Rich-styled error automatically:
# ╭─ Error ─────────────────────────────────────────────────────────╮
# │ Invalid value for '--before': Invalid date format. Use YYYY-MM-DD│
# ╰─────────────────────────────────────────────────────────────────╯
raise typer.BadParameter("Invalid date format. Use YYYY-MM-DD.")
```

---

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| `typer.Option(default)` positional default | `Annotated[Type, typer.Option()] = default` | Old style deprecated per Typer source docs; new style is current |
| `datetime.utcnow()` | `datetime.now()` (naive, local tz) | `utcnow()` deprecated in Python 3.12+ |
| `timedelta(days=N*30)` | `relativedelta(months=N)` | Calendar-correct month arithmetic |

**Deprecated/outdated:**
- `typer.Option(default_value)` positional-default syntax: Deprecated per Typer params.py docs. Use `Annotated[Type, typer.Option()] = default` instead.
- `datetime.utcnow()`: Deprecated in Python 3.12. Use `datetime.now()` for naive local time or `datetime.now(timezone.utc)` for timezone-aware UTC.

---

## Open Questions

1. **Should both `--older-than` and `--before` be allowed simultaneously?**
   - What we know: The requirements specify two separate flags (CLI-01, CLI-02) with no explicit "either/or" statement.
   - What's unclear: Whether the user might ever want both (no meaningful use case found).
   - Recommendation: Treat as mutually exclusive — providing both is a user error. The manual guard pattern handles this cleanly. **Decision was made implicitly in prior decisions**: the two flags describe different ways to specify the same cutoff date, so only one makes sense at a time.

2. **Exit code when user declines the `--execute` confirmation?**
   - What we know: `typer.Exit(0)` = clean exit, `typer.Abort()` = exit code 1 (error). Prior decisions do not specify.
   - What's unclear: Whether scripting use cases (v2 CLI-V2-02) need a distinct exit code for "user cancelled".
   - Recommendation: Use `typer.Exit(0)` for Phase 2 (user cancellation is not an error). Phase 4 can revisit for v2 scripting requirements.

3. **Should `count_messages()` cap be visible to the user?**
   - What we know: The stub returns at most 500. A user with 1,500 matching emails will see "42" or "500" as the count.
   - What's unclear: Whether we should add "(approximate)" to the dry-run output.
   - Recommendation: Add `"(count may be truncated — Phase 3 will show accurate count)"` to the dry-run output, or at minimum note "up to 500". Makes the limitation explicit and sets user expectations.

---

## Sources

### Primary (HIGH confidence)
- `/Users/dalwrigh/dev/gmail_cleanup/.venv/lib/python3.12/site-packages/typer/params.py` — `Option()` and `Argument()` full signatures with inline docs
- `/Users/dalwrigh/dev/gmail_cleanup/.venv/lib/python3.12/site-packages/typer/__init__.py` — confirms `typer.confirm`, `typer.BadParameter`, `typer.Abort`, `typer.Exit` all re-exported
- `/Users/dalwrigh/dev/gmail_cleanup/.venv/lib/python3.12/site-packages/dateutil/relativedelta.py` — `relativedelta` class and `months=` parameter
- Live Python execution in project venv — all code examples tested and output verified

### Secondary (MEDIUM confidence)
- `/Users/dalwrigh/dev/gmail_cleanup/gmail_cleanup/main.py` — Phase 1 patterns (typer app setup, HttpError handling, `add_completion=False`) carried forward
- `/Users/dalwrigh/dev/gmail_cleanup/gmail_cleanup/auth.py` — `build_gmail_service()` interface unchanged

### Tertiary (LOW confidence)
- None — all findings verified against installed source or live execution.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from `importlib.metadata` in project venv
- Architecture patterns: HIGH — all patterns verified by running code in project venv with CliRunner
- Pitfalls: HIGH — each pitfall was reproduced and verified by running failing/passing variants in project venv

**Research date:** 2026-02-18
**Valid until:** 2026-04-18 (stable libraries; Typer 0.24.0 is pinned in pyproject.toml)
