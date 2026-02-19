"""Date arithmetic and Gmail query helpers for CLI argument processing."""

from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta


def months_ago_to_cutoff(months: int) -> datetime:
    """Return UTC-aware datetime exactly N calendar months before now.

    Uses relativedelta (not timedelta) for correct month arithmetic.
    For example, 1 month before 2024-03-31 is 2024-02-29 (not 2024-03-03).
    """
    return datetime.now(timezone.utc) - relativedelta(months=months)


def parse_date_to_cutoff(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD string into a UTC-aware datetime at midnight.

    Raises ValueError if the string is not a valid YYYY-MM-DD date.
    Phase 3 will refine the cutoff to epoch timestamp for timezone precision.
    """
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def build_gmail_query(cutoff: datetime) -> str:
    """Convert a cutoff datetime into a Gmail search query string.

    Uses 'before:YYYY/MM/DD' format (slash-separated per Gmail API spec).
    Phase 3 will replace this with epoch timestamp format for timezone precision.
    """
    return f"before:{cutoff.strftime('%Y/%m/%d')}"
