"""Gmail API operations — count implemented in Phase 2, list/delete in Phase 3/4."""

from googleapiclient.errors import HttpError


def count_messages(service, query: str) -> int:
    """Return approximate count of messages matching query (up to 500).

    Uses a single API call with maxResults=500 — does not paginate.
    Phase 3 will replace this with full pagination for accurate counts over 500.

    Args:
        service: Authenticated Gmail API service object from build_gmail_service().
        query: Gmail search query string (e.g. "before:2024/01/01").

    Returns:
        Number of matching messages found (0-500).
    """
    result = service.users().messages().list(
        userId="me", q=query, maxResults=500
    ).execute()
    messages = result.get("messages", [])
    return len(messages)


def list_messages(service, query: str, max_results: int = 500) -> list[dict]:
    """Return list of message dicts matching query. Stub — Phase 3."""
    raise NotImplementedError("Implemented in Phase 3")
