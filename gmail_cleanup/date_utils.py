"""Date arithmetic and Gmail query helpers for CLI argument processing."""

from datetime import datetime

from dateutil.relativedelta import relativedelta


def months_ago_to_cutoff(months: int) -> datetime:
    """Return local-tz-aware datetime exactly N calendar months before now.

    Uses relativedelta (not timedelta) for correct month arithmetic.
    For example, 1 month before 2024-03-31 is 2024-02-29 (not 2024-03-03).

    Returns a tz-aware datetime in the local system timezone (not UTC).
    """
    return datetime.now().astimezone() - relativedelta(months=months)


def parse_date_to_cutoff(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD string into a local-tz-aware datetime at end of day.

    Returns the datetime at 23:59:59 in the local system timezone, ensuring
    that the entire day is included before the cutoff (no UTC-boundary ambiguity).

    Raises ValueError if the string is not a valid YYYY-MM-DD date.
    """
    return (
        datetime.strptime(date_str, "%Y-%m-%d")
        .replace(hour=23, minute=59, second=59)
        .astimezone()
    )


def build_gmail_query(cutoff: datetime) -> str:
    """Convert a cutoff datetime into a Gmail search query string.

    Uses 'before:{epoch}' format with a Unix timestamp integer, which
    eliminates timezone ambiguity present in date-string formats.
    """
    return f"before:{int(cutoff.timestamp())}"
